# pylint: disable=R0917
"""
Copyright (c) 2025 Huawei Device Co., Ltd.
Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

 http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

import bisect
import logging
import sqlite3
import time
import traceback
from collections import defaultdict
from typing import TYPE_CHECKING, Any, Optional

import pandas as pd

from .frame_constants import (
    CALLCHAIN_ANALYSIS_TIME_THRESHOLD,
    FRAME_ANALYSIS_TIME_THRESHOLD,
    VSYNC_EVENT_COUNT_THRESHOLD,
    VSYNC_SYMBOL_HANDLE,
    VSYNC_SYMBOL_ON_READABLE,
)
from .frame_utils import is_system_thread

if TYPE_CHECKING:
    from .frame_core_cache_manager import FrameCacheManager


# ============================================================================
# CPU计算工具函数
# ============================================================================


def calculate_thread_instructions(
    perf_conn: sqlite3.Connection,
    trace_conn: sqlite3.Connection,
    thread_ids: set[int],
    frame_start: int,
    frame_end: int,
    tid_to_info_cache: Optional[dict] = None,
    perf_sample_cache: Optional[dict] = None,
    perf_timestamp_field: Optional[str] = None,
    return_callchain_ids: bool = False,
) -> tuple[dict[int, int], dict[int, int]] | tuple[dict[int, int], dict[int, int], list[dict]]:
    """计算线程在帧时间范围内的 CPU 指令数（区分应用线程和系统线程）

    参考RN实现：只计算应用线程的指令数，排除系统线程
    注意：扩展时间范围（前后各扩展1ms）以包含时间戳对齐问题导致的perf_sample

    Args:
        perf_conn: perf 数据库连接
        trace_conn: trace 数据库连接（用于获取线程信息）
        thread_ids: 线程 ID 集合（perf_thread 表的 thread_id，对应trace thread.tid）
        frame_start: 帧开始时间
        frame_end: 帧结束时间
        tid_to_info_cache: tid到线程信息的缓存
        perf_sample_cache: perf_sample缓存
        perf_timestamp_field: perf_sample时间戳字段名

    Returns:
        (app_thread_instructions, system_thread_instructions)
        - app_thread_instructions: 应用线程的指令数字典 {thread_id: instruction_count}
        - system_thread_instructions: 系统线程的指令数字典 {thread_id: instruction_count}
    """
    if not perf_conn or not trace_conn:
        return {}, {}

    try:
        perf_cursor = perf_conn.cursor()
        trace_cursor = trace_conn.cursor()

        if not thread_ids:
            return {}, {}

        # 性能优化：使用预加载的缓存，避免数据库查询
        extended_start = frame_start - 1_000_000  # 1ms before
        extended_end = frame_end + 1_000_000  # 1ms after

        # 如果提供了缓存，从缓存中查询
        if perf_sample_cache is not None and perf_timestamp_field:
            # 从缓存中查找和聚合（使用二分查找优化）
            thread_instruction_map = {}
            for thread_id in thread_ids:
                if thread_id in perf_sample_cache:
                    # 在缓存中查找时间范围内的数据
                    samples = perf_sample_cache[thread_id]
                    if not samples:
                        continue

                    # 使用二分查找找到起始位置
                    # samples是(timestamp, event_count)的列表，已按timestamp排序
                    timestamps = [s[0] for s in samples]
                    start_idx = bisect.bisect_left(timestamps, extended_start)
                    end_idx = bisect.bisect_right(timestamps, extended_end)

                    # 聚合范围内的event_count
                    total_instructions = sum(samples[i][1] for i in range(start_idx, end_idx))

                    if total_instructions > 0:
                        thread_instruction_map[thread_id] = total_instructions

            # 区分应用线程和系统线程
            app_thread_instructions = {}
            system_thread_instructions = {}

            for thread_id, instruction_count in thread_instruction_map.items():
                thread_info = tid_to_info_cache.get(thread_id, {}) if tid_to_info_cache else {}
                process_name = thread_info.get('process_name')
                thread_name = thread_info.get('thread_name')

                if is_system_thread(process_name, thread_name):
                    system_thread_instructions[thread_id] = instruction_count
                else:
                    app_thread_instructions[thread_id] = instruction_count

            return app_thread_instructions, system_thread_instructions

        # 向后兼容：如果没有缓存，查询数据库
        # 检查 perf_sample 表字段名（只检查一次，可以缓存）
        perf_cursor.execute('PRAGMA table_info(perf_sample)')
        columns = [row[1] for row in perf_cursor.fetchall()]
        timestamp_field = (
            perf_timestamp_field
            if perf_timestamp_field
            else ('timestamp_trace' if 'timestamp_trace' in columns else 'timeStamp')
        )

        # 获取线程信息（进程名和线程名），用于判断是否为系统线程
        thread_ids_list = list(thread_ids)
        if not thread_ids_list:
            return {}, {}

        # 定义placeholders（在后续查询中使用）
        placeholders = ','.join('?' * len(thread_ids_list))

        # 性能优化：使用预加载的缓存，避免数据库查询
        thread_info_map = {}
        if tid_to_info_cache:
            # 从缓存中查找
            for tid in thread_ids_list:
                if tid in tid_to_info_cache:
                    thread_info_map[tid] = tid_to_info_cache[tid]
        else:
            # 向后兼容：如果没有缓存，查询数据库
            trace_cursor.execute(
                f"""
                SELECT DISTINCT t.tid, t.name as thread_name, p.name as process_name
                FROM thread t
                INNER JOIN process p ON t.ipid = p.ipid
                WHERE t.tid IN ({placeholders})
            """,
                thread_ids_list,
            )

            for tid, thread_name, process_name in trace_cursor.fetchall():
                thread_info_map[tid] = {'thread_name': thread_name, 'process_name': process_name}

        # 优化：使用索引提示，批量查询所有线程的指令数
        # 使用EXPLAIN QUERY PLAN优化查询性能
        if return_callchain_ids:
            # 如果需要返回callchain_id，查询所有样本（不GROUP BY），在Python中处理
            instructions_query = f"""
            SELECT
                ps.thread_id,
                ps.event_count,
                ps.callchain_id
            FROM perf_sample ps
            WHERE ps.thread_id IN ({placeholders})
            AND ps.{timestamp_field} >= ? AND ps.{timestamp_field} <= ?
            """
        else:
            # 原有逻辑：只查询汇总结果
            instructions_query = f"""
            SELECT
                ps.thread_id,
                SUM(ps.event_count) as total_instructions
            FROM perf_sample ps
            WHERE ps.thread_id IN ({placeholders})
            AND ps.{timestamp_field} >= ? AND ps.{timestamp_field} <= ?
            GROUP BY ps.thread_id
            """

        params = thread_ids_list + [extended_start, extended_end]
        perf_cursor.execute(instructions_query, params)

        results = perf_cursor.fetchall()

        app_thread_instructions = {}
        system_thread_instructions = {}
        sample_details = []  # 保存所有样本的详细信息：thread_id, event_count, callchain_id

        if return_callchain_ids:
            # 一轮遍历：累加event_count，同时保存每个样本的详细信息
            for thread_id, event_count, callchain_id in results:
                # 保存样本详细信息（只保存有callchain_id的样本，用于后续调用链分析）
                if callchain_id is not None:
                    sample_details.append(
                        {'thread_id': thread_id, 'event_count': event_count, 'callchain_id': callchain_id}
                    )

                # 累加event_count（区分应用线程和系统线程）
                thread_info = thread_info_map.get(thread_id, {})
                process_name = thread_info.get('process_name')
                thread_name = thread_info.get('thread_name')

                if is_system_thread(process_name, thread_name):
                    system_thread_instructions[thread_id] = system_thread_instructions.get(thread_id, 0) + event_count
                else:
                    app_thread_instructions[thread_id] = app_thread_instructions.get(thread_id, 0) + event_count

            # 打印保存的样本详细信息（用于调试）
            if sample_details:
                # logging.info(
                # f'[第一轮筛选] 保存样本详细信息: 总样本数={len(sample_details)}, '
                # f'涉及线程数={len(set(s["thread_id"] for s in sample_details))}, '
                # f'唯一callchain_id数={len(set(s["callchain_id"] for s in sample_details))}, '
                # f'时间范围=[{extended_start}, {extended_end}]'
                # )
                # 打印前5个样本的详细信息
                for _i, _sample in enumerate(sample_details[:5], 1):
                    # logging.info(
                    # f'[第一轮筛选] 样本{i}: thread_id={sample["thread_id"]}, '
                    # f'event_count={sample["event_count"]}, callchain_id={sample["callchain_id"]}'
                    # )
                    pass
                if len(sample_details) > 5:
                    # logging.info(f'[第一轮筛选] ... 还有 {len(sample_details) - 5} 个样本')
                    pass
        else:
            # 原有逻辑：直接使用汇总结果
            for thread_id, instruction_count in results:
                thread_info = thread_info_map.get(thread_id, {})
                process_name = thread_info.get('process_name')
                thread_name = thread_info.get('thread_name')

                if is_system_thread(process_name, thread_name):
                    system_thread_instructions[thread_id] = instruction_count
                else:
                    app_thread_instructions[thread_id] = instruction_count

        if return_callchain_ids:
            return app_thread_instructions, system_thread_instructions, sample_details
        return app_thread_instructions, system_thread_instructions

    except Exception as e:
        logging.error('计算线程指令数失败: %s', str(e))
        logging.error('异常堆栈跟踪:\n%s', traceback.format_exc())
        return {}, {}


def calculate_process_instructions(
    perf_conn: sqlite3.Connection,
    trace_conn: sqlite3.Connection,
    app_pid: int,
    frame_start: int,
    frame_end: int,
    perf_sample_cache: Optional[dict] = None,
    perf_timestamp_field: Optional[str] = None,
    tid_to_info_cache: Optional[dict] = None,
    return_callchain_ids: bool = False,
) -> tuple[int, int] | tuple[int, int, list[dict]]:
    """计算应用进程在帧时间范围内的所有CPU指令数（进程级统计）

    这是推荐的CPU计算方式：直接统计应用进程所有线程的CPU指令数，简单、完整、性能好。
    不需要通过唤醒链分析找到相关线程，直接统计进程级别的CPU。

    Args:
        perf_conn: perf数据库连接
        trace_conn: trace数据库连接（用于获取进程的线程列表）
        app_pid: 应用进程ID（process.pid）
        frame_start: 帧开始时间
        frame_end: 帧结束时间
        perf_sample_cache: perf_sample缓存（可选，用于性能优化）
        perf_timestamp_field: perf_sample时间戳字段名（可选）
        tid_to_info_cache: tid到线程信息的缓存（可选）

    Returns:
        (app_instructions, system_instructions)
        - app_instructions: 应用线程的总指令数
        - system_instructions: 系统线程的总指令数（通常为0，因为已过滤系统线程）
    """
    if not perf_conn or not trace_conn:
        return 0, 0

    try:
        # 扩展时间范围（前后各扩展1ms）以包含时间戳对齐问题导致的perf_sample
        frame_start - 1_000_000  # 1ms before
        frame_end + 1_000_000  # 1ms after

        # 步骤1: 查找应用进程的所有线程ID（tid）
        trace_cursor = trace_conn.cursor()
        trace_cursor.execute(
            """
            SELECT DISTINCT t.tid
            FROM thread t
            INNER JOIN process p ON t.ipid = p.ipid
            WHERE p.pid = ?
        """,
            (app_pid,),
        )

        thread_tids = [row[0] for row in trace_cursor.fetchall()]

        if not thread_tids:
            logging.debug(f'进程 {app_pid} 没有找到任何线程')
            return 0, 0

        # 步骤2: 计算这些线程在帧时间范围内的CPU指令数
        # 注意：calculate_thread_instructions内部会使用扩展时间窗口（±1ms），
        # 所以这里直接传递原始的frame_start和frame_end即可
        thread_ids = set(thread_tids)
        result = calculate_thread_instructions(
            perf_conn=perf_conn,
            trace_conn=trace_conn,
            thread_ids=thread_ids,
            frame_start=frame_start,
            frame_end=frame_end,
            tid_to_info_cache=tid_to_info_cache,
            perf_sample_cache=perf_sample_cache,
            perf_timestamp_field=perf_timestamp_field,
            return_callchain_ids=return_callchain_ids,
        )

        if return_callchain_ids:
            app_instructions_dict, system_instructions_dict, sample_details = result
        else:
            app_instructions_dict, system_instructions_dict = result
            sample_details = []

        # 步骤3: 汇总所有线程的指令数
        app_instructions = sum(app_instructions_dict.values())
        system_instructions = sum(system_instructions_dict.values())

        logging.debug(
            f'进程 {app_pid} CPU统计: 应用线程={app_instructions:,} 指令, 系统线程={system_instructions:,} 指令'
        )

        if return_callchain_ids:
            return app_instructions, system_instructions, sample_details
        return app_instructions, system_instructions

    except Exception as e:
        logging.error(f'计算进程CPU指令数失败 (PID={app_pid}): {e}')
        logging.error('异常堆栈跟踪:\n%s', traceback.format_exc())
        return 0, 0


class FrameLoadCalculator:
    """帧负载计算器

    负责计算帧的负载和调用链分析，包括：
    1. 帧负载计算
    2. 调用链分析
    3. 样本调用链构建
    4. VSync过滤
    """

    def __init__(self, debug_vsync_enabled: bool = False, cache_manager: 'FrameCacheManager' = None):
        """
        初始化帧负载计算器

        Args:
            debug_vsync_enabled: VSync调试开关，True时正常判断，False时永远不触发VSync条件
            cache_manager: 缓存管理器实例
        """
        self.debug_vsync_enabled = debug_vsync_enabled
        self.cache_manager = cache_manager
        # 新增：进程级CPU计算开关（默认启用）
        self.use_process_level_cpu = True

    def analyze_perf_callchain(
        self,
        callchain_id: int,
        callchain_cache: pd.DataFrame = None,
        files_cache: pd.DataFrame = None,
        step_id: str = None,
    ) -> list[dict[str, Any]]:
        """分析perf样本的调用链信息

        Args:
            callchain_id: 调用链ID
            callchain_cache: 缓存的callchain数据
            files_cache: 缓存的文件数据
            step_id: 步骤ID，用于缓存key

        Returns:
            List[Dict]: 调用链信息列表，每个元素包含symbol和path信息
        """
        callchain_start_time = time.time()

        try:
            # 如果没有缓存，先获取缓存
            cache_check_start = time.time()
            if callchain_cache is None or callchain_cache.empty:
                callchain_cache = self.cache_manager.get_callchain_cache() if self.cache_manager else pd.DataFrame()
            if files_cache is None or files_cache.empty:
                files_cache = self.cache_manager.get_files_cache() if self.cache_manager else pd.DataFrame()
            cache_check_time = time.time() - cache_check_start

            # 检查缓存是否为空
            cache_validate_start = time.time()
            if (
                not self.cache_manager
                or self.cache_manager._callchain_cache is None
                or self.cache_manager._callchain_cache.empty
                or self.cache_manager._files_cache is None
                or self.cache_manager._files_cache.empty
            ):
                logging.warning('缓存数据为空，无法分析调用链')
                return []
            cache_validate_time = time.time() - cache_validate_start

            # 从缓存中获取callchain数据
            callchain_lookup_start = time.time()
            callchain_cache = self.cache_manager._callchain_cache
            callchain_records = (
                callchain_cache[callchain_cache['callchain_id'] == callchain_id]  # pylint: disable=protected-access
            )
            callchain_lookup_time = time.time() - callchain_lookup_start

            if callchain_records.empty:
                total_time = time.time() - callchain_start_time
                if total_time > CALLCHAIN_ANALYSIS_TIME_THRESHOLD:  # 只记录耗时超过阈值的调用链分析
                    logging.debug(
                        '[%s] 调用链分析耗时: %.6f秒 (无记录), 缓存检查%.6f秒, 缓存验证%.6f秒, 记录查找%.6f秒',
                        step_id,
                        total_time,
                        cache_check_time,
                        cache_validate_time,
                        callchain_lookup_time,
                    )
                return []

            # 构建调用链信息
            build_start = time.time()
            callchain_info = []
            file_lookup_total = 0

            for _, record in callchain_records.iterrows():
                # 从缓存中获取文件信息
                file_start = time.time()
                files_cache = self.cache_manager._files_cache
                file_mask = (files_cache['file_id'] == record['file_id']) & (
                    files_cache['serial_id'] == record['symbol_id']
                )
                file_info = files_cache[file_mask]  # pylint: disable=protected-access
                file_time = time.time() - file_start
                file_lookup_total += file_time

                symbol = file_info['symbol'].iloc[0] if not file_info.empty else 'unknown'
                path = file_info['path'].iloc[0] if not file_info.empty else 'unknown'

                callchain_info.append(
                    {
                        'depth': int(record['depth']),
                        'file_id': int(record['file_id']),
                        'path': str(path),
                        'symbol_id': int(record['symbol_id']),
                        'symbol': str(symbol),
                    }
                )

            build_time = time.time() - build_start

            # 总耗时统计
            total_time = time.time() - callchain_start_time

            # 只记录耗时较长的调用链分析（超过0.01秒）
            if total_time > 0.01:
                logging.debug(
                    '[%s] 调用链分析耗时: %.6f秒, callchain_id: %s, 记录数: %d',
                    step_id,
                    total_time,
                    callchain_id,
                    len(callchain_records),
                )
                logging.debug(
                    '[%s] 各阶段耗时: 缓存检查%.6f秒, 缓存验证%.6f秒, 记录查找%.6f秒, 构建%.6f秒, 文件查找%.6f秒',
                    step_id,
                    cache_check_time,
                    cache_validate_time,
                    callchain_lookup_time,
                    build_time,
                    file_lookup_total,
                )

            return callchain_info

        except Exception as e:
            logging.error('分析调用链失败: %s', str(e))
            return []

    def analyze_single_frame(self, frame, perf_df, perf_conn, step_id):
        """分析单个帧的负载和调用链，返回frame_load和sample_callchains

        这是从原始FrameAnalyzer.analyze_single_frame方法迁移的代码
        """
        frame_start_time = time.time()

        # 在函数内部获取缓存
        cache_start = time.time()
        if self.cache_manager:
            callchain_cache = self.cache_manager.get_callchain_cache()
            files_cache = self.cache_manager.get_files_cache()
        else:
            callchain_cache = pd.DataFrame()
            files_cache = pd.DataFrame()
        cache_time = time.time() - cache_start

        frame_load = 0
        sample_callchains = []

        # 计算帧的开始和结束时间
        time_calc_start = time.time()
        frame_start_time_ts = frame.get('start_time', frame.get('ts', 0))
        frame_end_time_ts = frame.get('end_time', frame.get('ts', 0) + frame.get('dur', 0))
        time_calc_time = time.time() - time_calc_start

        # 数据过滤
        # 注意：一帧可能包含多个线程的样本，每个样本都有自己的callchain_id和thread_id
        # 因此只按时间范围过滤，不限制线程，确保能分析该帧时间范围内所有线程的样本
        filter_start = time.time()
        mask = (perf_df['timestamp_trace'] >= frame_start_time_ts) & (perf_df['timestamp_trace'] <= frame_end_time_ts)
        # 如果提供了app_pid，可以进一步过滤应用进程的样本（可选优化）
        if 'app_pid' in frame and frame['app_pid']:
            # 这里可以添加进程过滤，但需要perf_df中有pid字段
            # 暂时只按时间范围过滤，因为perf_df中可能没有pid字段
            pass
        frame_samples = perf_df[mask]
        filter_time = time.time() - filter_start

        if frame_samples.empty:
            total_time = time.time() - frame_start_time
            if total_time > FRAME_ANALYSIS_TIME_THRESHOLD:  # 只记录耗时超过阈值的帧
                logging.debug(
                    '[%s] 空帧分析耗时: %.6f秒 (无样本), 缓存%.6f秒, 时间计算%.6f秒, 过滤%.6f秒',
                    step_id,
                    total_time,
                    cache_time,
                    time_calc_time,
                    filter_time,
                )
            return frame_load, sample_callchains

        # 样本分析：收集所有调用链
        sample_analysis_start = time.time()
        callchain_analysis_total = 0
        vsync_filter_total = 0
        sample_count = 0

        # 存储每个sample的调用链信息
        sample_callchain_list = []

        for _, sample in frame_samples.iterrows():
            sample_count += 1
            if not pd.notna(sample['callchain_id']):
                continue

            try:
                # 调用链分析
                callchain_start = time.time()
                callchain_info = self.analyze_perf_callchain(
                    int(sample['callchain_id']), callchain_cache, files_cache, step_id
                )
                callchain_time = time.time() - callchain_start
                callchain_analysis_total += callchain_time

                if callchain_info and len(callchain_info) > 0:
                    # VSync过滤
                    vsync_start = time.time()
                    is_vsync_chain = False
                    for i in range(len(callchain_info) - 1):
                        current_symbol = callchain_info[i]['symbol']
                        next_symbol = callchain_info[i + 1]['symbol']
                        event_count = sample['event_count']

                        if not current_symbol or not next_symbol:
                            continue

                        if self.debug_vsync_enabled and (
                            VSYNC_SYMBOL_ON_READABLE in current_symbol
                            and VSYNC_SYMBOL_HANDLE in next_symbol
                            and event_count < VSYNC_EVENT_COUNT_THRESHOLD
                        ):
                            is_vsync_chain = True
                            break
                    vsync_time = time.time() - vsync_start
                    vsync_filter_total += vsync_time

                    if not is_vsync_chain:
                        frame_load += sample['event_count']

                        # 直接保存sample信息，每个深度的value就是sample的event_count
                        # 火焰图的宽度差异来自于前端合并不同调用栈时的累加
                        sample_callchain_list.append(
                            {
                                'timestamp': int(sample['timestamp_trace']),
                                'event_count': int(sample['event_count']),
                                'thread_id': int(sample['thread_id']),
                                'callchain_info': callchain_info,
                            }
                        )

            except Exception as e:
                logging.error('分析调用链时出错: %s', str(e))
                continue

        # 获取thread_id到thread_name的映射（从缓存中获取，避免重复查询）
        tid_to_info = {}
        if self.cache_manager:
            tid_to_info = self.cache_manager.get_tid_to_info()

        # 为每个sample的调用链添加负载信息和thread_name
        for sample_data in sample_callchain_list:
            try:
                sample_load_percentage = (sample_data['event_count'] / frame_load) * 100 if frame_load > 0 else 0

                # 每个深度的value都是sample的event_count
                # 火焰图会在前端合并时自动累加
                callchain_with_load = []
                for call in sample_data['callchain_info']:
                    call_with_load = call.copy()
                    call_with_load['value'] = sample_data['event_count']
                    callchain_with_load.append(call_with_load)

                # 从缓存中获取thread_name
                thread_id = sample_data['thread_id']
                thread_info = tid_to_info.get(thread_id, {})
                thread_name = thread_info.get('thread_name', 'unknown')

                sample_callchains.append(
                    {
                        'timestamp': sample_data['timestamp'],
                        'event_count': sample_data['event_count'],
                        'load_percentage': float(sample_load_percentage),
                        'thread_id': thread_id,
                        'thread_name': thread_name,  # 添加thread_name
                        'callchain': callchain_with_load,
                    }
                )
            except Exception as e:
                logging.error('处理样本时出错: %s, sample: %s, frame_load: %s', str(e), sample_data, frame_load)
                continue

        sample_analysis_time = time.time() - sample_analysis_start

        # 对sample_callchains按event_count降序排序（与stuttered frame保持一致）
        sample_callchains = sorted(sample_callchains, key=lambda x: x['event_count'], reverse=True)

        # 保存帧负载数据到缓存
        # 注意：一帧是针对整个进程的，不是某个线程，因此不保存thread_id
        # 每个sample_callchain都有自己的thread_id
        cache_save_start = time.time()
        frame_load_data = {
            'ts': frame.get('ts', frame.get('start_time', 0)),
            'dur': frame.get('dur', frame.get('end_time', 0) - frame.get('start_time', 0)),
            'frame_load': frame_load,
            'empty_frame_thread': frame.get('thread_name', 'unknown'),  # 空刷产生的线程（区分sample_callchains中的thread_name）
            'process_name': frame.get('process_name', 'unknown'),
            'type': frame.get('type', 0),
            'vsync': frame.get('vsync', 'unknown'),
            'flag': frame.get('flag'),
            'sample_callchains': sample_callchains,  # 每个callchain都有自己的thread_id
        }
        if self.cache_manager:
            self.cache_manager.add_frame_load(frame_load_data)
        cache_save_time = time.time() - cache_save_start

        # 总耗时统计
        total_time = time.time() - frame_start_time

        # 只记录耗时较长的帧分析（超过阈值）
        if total_time > FRAME_ANALYSIS_TIME_THRESHOLD:
            logging.debug(
                '[%s] 单帧分析耗时: %.6f秒, 样本数: %d, 有效样本: %d',
                step_id,
                total_time,
                len(frame_samples),
                sample_count,
            )
            logging.debug(
                '[%s] 各阶段耗时: 缓存获取%.6f秒, 时间计算%.6f秒, 数据过滤%.6f秒, 样本分析%.6f秒, 缓存保存%.6f秒',
                step_id,
                cache_time,
                time_calc_time,
                filter_time,
                sample_analysis_time,
                cache_save_time,
            )
            logging.debug(
                '[%s] 样本分析详情: 调用链分析%.6f秒, VSync过滤%.6f秒',
                step_id,
                callchain_analysis_total,
                vsync_filter_total,
            )

        return frame_load, sample_callchains

    def calculate_frame_load_multi_process(
        self, frame: dict[str, Any], trace_conn, perf_conn, app_pids: list[int]
    ) -> int:
        """使用进程级统计计算帧负载，支持多进程（如ArkWeb）

        Args:
            frame: 帧数据字典，必须包含 'ts', 'dur' 字段
            trace_conn: trace数据库连接
            perf_conn: perf数据库连接
            app_pids: 应用进程ID列表（支持多个进程，如ArkWeb的主进程+render进程）

        Returns:
            int: 帧负载（多进程级统计，包含系统线程）
        """
        frame_start = frame['ts']
        frame_end = frame['ts'] + frame['dur']

        total_cpu = 0

        # 对每个进程分别计算CPU，然后汇总
        for pid in app_pids:
            # 使用进程级统计（包含系统线程，如OS_VSyncThread）
            app_instructions, sys_instructions = calculate_process_instructions(
                perf_conn=perf_conn, trace_conn=trace_conn, app_pid=pid, frame_start=frame_start, frame_end=frame_end
            )

            # 包含系统线程CPU（OS_VSyncThread等系统线程也在应用进程中运行）
            total_cpu += app_instructions + sys_instructions

        return int(total_cpu)

    def calculate_frame_load_process_level(self, frame: dict[str, Any], trace_conn, perf_conn, app_pid: int) -> int:
        """使用进程级统计计算帧负载（单进程版本，兼容旧代码）

        Args:
            frame: 帧数据字典，必须包含 'ts', 'dur' 字段
            trace_conn: trace数据库连接
            perf_conn: perf数据库连接
            app_pid: 应用进程ID

        Returns:
            int: 帧负载（进程级统计，包含系统线程）
        """
        return self.calculate_frame_load_multi_process(frame, trace_conn, perf_conn, [app_pid])

    def _calculate_single_thread_load(self, frame: dict[str, Any], perf_df: pd.DataFrame) -> int:
        """单线程CPU计算（旧方法，用于回退）

        Args:
            frame: 帧数据字典，必须包含 'ts', 'dur', 'tid' 字段
            perf_df: perf样本DataFrame

        Returns:
            int: 帧负载（单线程）
        """
        frame_start_time = frame['ts']
        frame_end_time = frame['ts'] + frame['dur']

        # 使用向量化操作进行过滤
        mask = (
            (perf_df['timestamp_trace'] >= frame_start_time)
            & (perf_df['timestamp_trace'] <= frame_end_time)
            & (perf_df['thread_id'] == frame['tid'])
        )
        frame_samples = perf_df[mask]

        if frame_samples.empty:
            return 0

        return int(frame_samples['event_count'].sum())

    def calculate_frame_load_simple(self, frame: dict[str, Any], perf_df: pd.DataFrame) -> int:
        """简单计算帧负载（支持进程级统计）

        Args:
            frame: 帧数据字典，必须包含 'ts', 'dur', 'tid' 字段
            perf_df: perf样本DataFrame

        Returns:
            int: 帧负载
        """
        # 如果启用了进程级CPU计算，且有cache_manager，则使用进程级统计
        if self.use_process_level_cpu and self.cache_manager:
            app_pid = frame.get('app_pid') or frame.get('pid')
            # 如果frame中没有app_pid，尝试从cache_manager获取
            if not app_pid and self.cache_manager.app_pids:
                app_pid = self.cache_manager.app_pids[0]

            if app_pid and self.cache_manager.trace_conn and self.cache_manager.perf_conn:
                try:
                    return self.calculate_frame_load_process_level(
                        frame, self.cache_manager.trace_conn, self.cache_manager.perf_conn, app_pid
                    )
                except Exception as e:
                    logging.warning(f'进程级CPU计算失败，回退到单线程计算: {e}')
                    # 继续执行单线程计算

        # 向后兼容：使用原有的单线程计算方式
        return self._calculate_single_thread_load(frame, perf_df)

    def calculate_all_frame_loads_fast(self, frames: pd.DataFrame, perf_df: pd.DataFrame) -> list[dict[str, Any]]:
        """快速计算所有帧的负载值，不分析调用链

        注意：如果启用了进程级CPU计算，将使用数据库查询而不是perf_df
        优化：使用批量查询，一次性获取所有帧的perf_sample数据，在内存中按帧分组计算

        Args:
            frames: 帧数据DataFrame
            perf_df: perf样本DataFrame

        Returns:
            List[Dict]: 帧负载数据列表
        """
        frame_loads = []

        # 检查是否使用进程级CPU计算
        use_process_level = (
            self.use_process_level_cpu
            and self.cache_manager
            and self.cache_manager.trace_conn
            and self.cache_manager.perf_conn
            and self.cache_manager.app_pids
        )

        if use_process_level:
            app_pids = self.cache_manager.app_pids
            logging.info(f'使用进程级CPU计算（PIDs={app_pids}），共{len(frames)}帧')
            
            # 优化：使用批量查询方法
            try:
                frame_loads = self._calculate_all_frame_loads_batch(frames, app_pids)
                logging.info(f'批量查询完成，共计算{len(frame_loads)}帧的负载')
                return frame_loads
            except Exception as e:
                logging.warning(f'批量查询失败，回退到逐帧查询: {e}')
                # 回退到原有的逐帧查询方法
                pass
        else:
            logging.info(f'使用单线程CPU计算，共{len(frames)}帧')

        # 批量计算开始（原有方法或回退方法）
        for i, (_, frame) in enumerate(frames.iterrows()):
            # 根据配置选择计算方法
            if use_process_level:
                try:
                    # 计算所有app_pids的CPU总和（支持ArkWeb的多进程架构）
                    frame_load = self.calculate_frame_load_multi_process(
                        frame, self.cache_manager.trace_conn, self.cache_manager.perf_conn, app_pids
                    )
                except Exception as e:
                    if i < 5:  # 只记录前5个错误，避免日志过多
                        logging.warning(f'帧{i}进程级CPU计算失败，回退到单线程: {e}')
                    frame_load = self._calculate_single_thread_load(frame, perf_df)
            else:
                # 使用单线程计算（快速但不准确）
                frame_load = self._calculate_single_thread_load(frame, perf_df)

            # 检查并记录NaN值
            nan_fields = []
            if pd.isna(frame['ts']):
                nan_fields.append('ts')
            if pd.isna(frame['dur']):
                nan_fields.append('dur')
            if pd.isna(frame['tid']):
                nan_fields.append('tid')
            if pd.isna(frame.get('type')):
                nan_fields.append('type')
            if pd.isna(frame.get('flag')):
                nan_fields.append('flag')
            if pd.isna(frame.get('is_main_thread')):
                nan_fields.append('is_main_thread')

            if nan_fields:
                logging.warning(
                    '帧数据包含NaN值，字段: %s, 索引: %d, 进程: %s, 线程: %s',
                    ', '.join(nan_fields),
                    i,
                    frame.get('process_name', 'unknown'),
                    frame.get('thread_name', 'unknown'),
                )

            # 确保时间戳字段正确，处理NaN值
            # 注意：一帧是针对整个进程的，不是某个线程，因此不保存thread_id
            # 每个sample_callchain都有自己的thread_id
            frame_loads.append(
                {
                    'ts': int(frame['ts']) if pd.notna(frame['ts']) else 0,  # 确保时间戳是整数
                    'dur': int(frame['dur']) if pd.notna(frame['dur']) else 0,  # 确保持续时间是整数
                    'frame_load': frame_load,
                    'thread_id': int(frame['tid']) if pd.notna(frame['tid']) else 0,  # 添加thread_id字段，用于帧匹配
                    'empty_frame_thread': frame.get('thread_name', 'unknown'),  # 空刷产生的线程（区分sample_callchains中的thread_name）
                    'process_name': frame.get('process_name', 'unknown'),
                    'type': int(frame.get('type', 0)) if pd.notna(frame.get('type')) else 0,  # 确保类型是整数
                    'vsync': frame.get('vsync', 'unknown'),
                    'flag': int(frame.get('flag', 0)) if pd.notna(frame.get('flag')) else 0,  # 确保flag是整数
                    'is_main_thread': int(frame.get('is_main_thread', 0))
                    if pd.notna(frame.get('is_main_thread'))
                    else 0,  # 确保主线程标志是整数
                    'sample_callchains': [],  # 空列表，不保存调用链
                }
            )

        return frame_loads

    def _calculate_all_frame_loads_batch(
        self, frames: pd.DataFrame, app_pids: list[int]
    ) -> list[dict[str, Any]]:
        """批量计算所有帧的负载（优化方法：一次性查询所有perf_sample数据）

        Args:
            frames: 帧数据DataFrame
            app_pids: 应用进程ID列表

        Returns:
            List[Dict]: 帧负载数据列表
        """
        if frames.empty:
            return []

        trace_conn = self.cache_manager.trace_conn
        perf_conn = self.cache_manager.perf_conn

        # 步骤1：计算所有帧的时间范围（扩展±1ms）
        min_ts = int(frames['ts'].min()) - 1_000_000  # 1ms before
        max_ts = int((frames['ts'] + frames['dur']).max()) + 1_000_000  # 1ms after

        # 步骤2：一次性获取所有进程的线程ID，并建立PID到线程ID的映射
        trace_cursor = trace_conn.cursor()
        placeholders = ','.join('?' * len(app_pids))
        trace_cursor.execute(
            f"""
            SELECT DISTINCT p.pid, t.tid
            FROM thread t
            INNER JOIN process p ON t.ipid = p.ipid
            WHERE p.pid IN ({placeholders})
        """,
            app_pids,
        )
        
        # 建立PID到线程ID列表的映射
        pid_to_threads = defaultdict(list)
        all_thread_tids = set()
        for pid, tid in trace_cursor.fetchall():
            pid_to_threads[pid].append(tid)
            all_thread_tids.add(tid)

        if not all_thread_tids:
            logging.warning('未找到进程的线程，返回空结果')
            return []

        # 步骤3：获取线程信息（用于区分系统线程）
        tid_to_info = self.cache_manager.get_tid_to_info() if self.cache_manager else {}

        # 步骤4：一次性查询所有线程在时间范围内的perf_sample数据
        perf_cursor = perf_conn.cursor()
        
        # 检查perf_sample表的时间戳字段名
        perf_cursor.execute('PRAGMA table_info(perf_sample)')
        columns = [row[1] for row in perf_cursor.fetchall()]
        timestamp_field = 'timestamp_trace' if 'timestamp_trace' in columns else 'timeStamp'

        thread_placeholders = ','.join('?' * len(all_thread_tids))
        batch_query = f"""
            SELECT
                ps.thread_id,
                ps.{timestamp_field} as ts,
                ps.event_count
            FROM perf_sample ps
            WHERE ps.thread_id IN ({thread_placeholders})
            AND ps.{timestamp_field} >= ? AND ps.{timestamp_field} <= ?
        """
        params = list(all_thread_tids) + [min_ts, max_ts]
        perf_cursor.execute(batch_query, params)
        
        # 步骤5：在内存中构建perf_sample索引（按thread_id和时间戳）
        # 使用字典存储：{thread_id: [(ts, event_count), ...]}
        perf_samples_by_thread = defaultdict(list)
        for thread_id, ts, event_count in perf_cursor.fetchall():
            perf_samples_by_thread[thread_id].append((ts, event_count))
        
        # 对每个线程的样本按时间戳排序（用于后续二分查找）
        for thread_id in perf_samples_by_thread:
            perf_samples_by_thread[thread_id].sort(key=lambda x: x[0])

        # 步骤6：对每个帧计算负载（在内存中分组计算）
        frame_loads = []
        for i, (_, frame) in enumerate(frames.iterrows()):
            frame_start = int(frame['ts'])
            frame_end = int(frame['ts']) + int(frame['dur'])
            # 注意：不使用时间扩展，直接使用原始时间范围，避免负载偏高

            total_load = 0

            # 对每个进程分别计算（使用预加载的PID到线程映射）
            for pid in app_pids:
                pid_thread_tids = pid_to_threads.get(pid, [])

                # 计算该进程所有线程的负载
                for thread_id in pid_thread_tids:
                    if thread_id not in perf_samples_by_thread:
                        continue

                    # 使用二分查找找到时间范围内的样本
                    samples = perf_samples_by_thread[thread_id]
                    if not samples:
                        continue

                    timestamps = [s[0] for s in samples]
                    start_idx = bisect.bisect_left(timestamps, frame_start)
                    end_idx = bisect.bisect_right(timestamps, frame_end)

                    # 累加该线程在时间范围内的event_count
                    thread_load = sum(samples[j][1] for j in range(start_idx, end_idx))
                    total_load += thread_load

            # 构建帧负载数据
            frame_loads.append(
                {
                    'ts': int(frame['ts']) if pd.notna(frame['ts']) else 0,
                    'dur': int(frame['dur']) if pd.notna(frame['dur']) else 0,
                    'frame_load': int(total_load),
                    'thread_id': int(frame['tid']) if pd.notna(frame['tid']) else 0,
                    'empty_frame_thread': frame.get('thread_name', 'unknown'),  # 空刷产生的线程（区分sample_callchains中的thread_name）
                    'process_name': frame.get('process_name', 'unknown'),
                    'type': int(frame.get('type', 0)) if pd.notna(frame.get('type')) else 0,
                    'vsync': frame.get('vsync', 'unknown'),
                    'flag': int(frame.get('flag', 0)) if pd.notna(frame.get('flag')) else 0,
                    'is_main_thread': int(frame.get('is_main_thread', 0))
                    if pd.notna(frame.get('is_main_thread'))
                    else 0,
                    'sample_callchains': [],
                }
            )

        return frame_loads
