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

import logging
import time
from typing import Any

import pandas as pd

from .frame_constants import (
    CALLCHAIN_ANALYSIS_TIME_THRESHOLD,
    FRAME_ANALYSIS_TIME_THRESHOLD,
    VSYNC_EVENT_COUNT_THRESHOLD,
    VSYNC_SYMBOL_HANDLE,
    VSYNC_SYMBOL_ON_READABLE,
)
from .frame_core_cache_manager import FrameCacheManager


class FrameLoadCalculator:
    """帧负载计算器

    负责计算帧的负载和调用链分析，包括：
    1. 帧负载计算
    2. 调用链分析
    3. 样本调用链构建
    4. VSync过滤
    """

    def __init__(self, debug_vsync_enabled: bool = False, cache_manager: FrameCacheManager = None):
        """
        初始化帧负载计算器

        Args:
            debug_vsync_enabled: VSync调试开关，True时正常判断，False时永远不触发VSync条件
            cache_manager: 缓存管理器实例
        """
        self.debug_vsync_enabled = debug_vsync_enabled
        self.cache_manager = cache_manager

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
        filter_start = time.time()
        mask = (
            (perf_df['timestamp_trace'] >= frame_start_time_ts)
            & (perf_df['timestamp_trace'] <= frame_end_time_ts)
            & (perf_df['thread_id'] == frame['tid'])
        )
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

        # 样本分析
        sample_analysis_start = time.time()
        callchain_analysis_total = 0
        vsync_filter_total = 0
        sample_count = 0

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
                        try:
                            sample_load_percentage = (sample['event_count'] / frame_load) * 100
                            sample_callchains.append(
                                {
                                    'timestamp': int(sample['timestamp_trace']),
                                    'event_count': int(sample['event_count']),
                                    'load_percentage': float(sample_load_percentage),
                                    'callchain': callchain_info,
                                }
                            )
                        except Exception as e:
                            logging.error(
                                '处理样本时出错: %s, sample: %s, frame_load: %s', str(e), sample.to_dict(), frame_load
                            )
                            continue

            except Exception as e:
                logging.error('分析调用链时出错: %s', str(e))
                continue

        sample_analysis_time = time.time() - sample_analysis_start

        # 保存帧负载数据到缓存
        cache_save_start = time.time()
        frame_load_data = {
            'ts': frame.get('ts', frame.get('start_time', 0)),
            'dur': frame.get('dur', frame.get('end_time', 0) - frame.get('start_time', 0)),
            'frame_load': frame_load,
            'thread_id': frame.get('tid'),
            'thread_name': frame.get('thread_name', 'unknown'),
            'process_name': frame.get('process_name', 'unknown'),
            'type': frame.get('type', 0),
            'vsync': frame.get('vsync', 'unknown'),
            'flag': frame.get('flag'),
            'sample_callchains': sample_callchains,
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

    def calculate_frame_load_simple(self, frame: dict[str, Any], perf_df: pd.DataFrame) -> int:
        """简单计算帧负载（不包含调用链分析）

        Args:
            frame: 帧数据字典，必须包含 'ts', 'dur', 'tid' 字段
            perf_df: perf样本DataFrame

        Returns:
            int: 帧负载
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

    def calculate_all_frame_loads_fast(self, frames: pd.DataFrame, perf_df: pd.DataFrame) -> list[dict[str, Any]]:
        """快速计算所有帧的负载值，不分析调用链

        Args:
            frames: 帧数据DataFrame
            perf_df: perf样本DataFrame

        Returns:
            List[Dict]: 帧负载数据列表
        """
        frame_loads = []

        # 批量计算开始
        for i, (_, frame) in enumerate(frames.iterrows()):
            # 使用现有的简单方法，只计算负载值
            frame_load = self.calculate_frame_load_simple(frame, perf_df)

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
            frame_loads.append(
                {
                    'ts': int(frame['ts']) if pd.notna(frame['ts']) else 0,  # 确保时间戳是整数
                    'dur': int(frame['dur']) if pd.notna(frame['dur']) else 0,  # 确保持续时间是整数
                    'frame_load': frame_load,
                    'thread_id': int(frame['tid']) if pd.notna(frame['tid']) else 0,  # 确保线程ID是整数
                    'thread_name': frame.get('thread_name', 'unknown'),
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
