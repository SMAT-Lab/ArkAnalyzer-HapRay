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
import sqlite3
import traceback
from typing import Optional

import pandas as pd

from .frame_constants import TOP_FRAMES_FOR_CALLCHAIN
from .frame_core_load_calculator import (
    FrameLoadCalculator,
    calculate_process_instructions,
    calculate_thread_instructions,
)
from .frame_time_utils import FrameTimeUtils
from .frame_utils import clean_frame_data, is_system_thread

logger = logging.getLogger(__name__)

"""空刷帧负载分析公共模块

包含：
1. CPU计算工具函数（线程级、进程级、应用帧级）
2. 空刷帧分析公共模块类（CPU计算、调用链分析、结果构建）

用于EmptyFrameAnalyzer和RSSkipFrameAnalyzer复用。
"""

logger = logging.getLogger(__name__)


# ============================================================================
# CPU计算工具函数
# ============================================================================


def calculate_app_frame_cpu_waste(
    trace_conn: sqlite3.Connection,
    perf_conn: Optional[sqlite3.Connection],
    app_frame: dict,
    perf_sample_cache: Optional[dict] = None,
    perf_timestamp_field: Optional[str] = None,
    tid_to_info_cache: Optional[dict] = None,
    use_process_level: bool = True,
) -> dict:
    """计算应用帧浪费的CPU指令数

    Args:
        trace_conn: trace数据库连接
        perf_conn: perf数据库连接（可为None）
        app_frame: 应用帧信息字典，包含frame_ts, frame_dur, thread_id, app_pid等
        perf_sample_cache: perf_sample缓存
        perf_timestamp_field: perf_sample时间戳字段名
        tid_to_info_cache: tid到线程信息的缓存（tid可以直接用于perf_sample.thread_id）
        use_process_level: 是否使用进程级统计（推荐，默认True）
            - True: 直接统计应用进程所有线程的CPU指令数（简单、完整、性能好）
            - False: 只计算帧对应线程的CPU指令数（向后兼容）

    Returns:
        包含CPU指令数信息的字典
    """
    if not perf_conn:
        return {'wasted_instructions': 0, 'system_instructions': 0, 'has_perf_data': False}

    try:
        frame_start = app_frame.get('frame_ts', 0)
        frame_dur = app_frame.get('frame_dur', 0)
        frame_end = frame_start + frame_dur

        # 推荐方式：进程级统计（直接统计应用进程所有线程的CPU）
        if use_process_level:
            app_pid = app_frame.get('app_pid')
            if app_pid:
                app_instructions, system_instructions = calculate_process_instructions(
                    perf_conn=perf_conn,
                    trace_conn=trace_conn,
                    app_pid=app_pid,
                    frame_start=frame_start,
                    frame_end=frame_end,
                    perf_sample_cache=perf_sample_cache,
                    perf_timestamp_field=perf_timestamp_field,
                    tid_to_info_cache=tid_to_info_cache,
                )
                return {
                    'wasted_instructions': app_instructions,
                    'system_instructions': system_instructions,
                    'has_perf_data': True,
                }
            logger.warning('use_process_level=True 但 app_frame 中没有 app_pid，回退到线程级统计')

        # 向后兼容：线程级统计（只计算帧对应线程的CPU）
        itid = app_frame.get('thread_id')
        if not itid:
            return {'wasted_instructions': 0, 'system_instructions': 0, 'has_perf_data': False}

        # 从itid获取tid
        tid = None
        if tid_to_info_cache:
            # 从缓存中查找：tid_to_info_cache的键是tid，值包含itid
            # 需要反向查找：从itid找到tid
            for tid_key, info in tid_to_info_cache.items():
                if info.get('itid') == itid:
                    tid = tid_key
                    break
        else:
            # 查询数据库：itid就是thread.id
            cursor = trace_conn.cursor()
            cursor.execute('SELECT tid FROM thread WHERE id = ?', (itid,))
            result = cursor.fetchone()
            if result:
                tid = result[0]

        if not tid:
            logger.warning(f'无法从itid {itid} 获取tid')
            return {'wasted_instructions': 0, 'system_instructions': 0, 'has_perf_data': False}

        # 计算线程在帧时间范围内的CPU指令数
        # tid可以直接用于perf_sample.thread_id
        thread_ids = {tid}
        app_instructions, system_instructions = calculate_thread_instructions(
            perf_conn=perf_conn,
            trace_conn=trace_conn,
            thread_ids=thread_ids,
            frame_start=frame_start,
            frame_end=frame_end,
            tid_to_info_cache=tid_to_info_cache,
            perf_sample_cache=perf_sample_cache,
            perf_timestamp_field=perf_timestamp_field,
        )

        wasted_instructions = app_instructions.get(tid, 0)
        sys_instructions = system_instructions.get(tid, 0)

        return {
            'wasted_instructions': wasted_instructions,
            'system_instructions': sys_instructions,
            'has_perf_data': True,
        }
    except Exception as e:
        logger.warning(f'计算CPU指令数失败: {e}')
        return {'wasted_instructions': 0, 'system_instructions': 0, 'has_perf_data': False, 'error': str(e)}


# ============================================================================
# 空刷帧分析公共模块类
# ============================================================================


class EmptyFrameCPUCalculator:
    """空刷帧CPU计算模块

    统一处理EmptyFrameAnalyzer和RSSkipFrameAnalyzer的应用进程CPU计算。
    追溯成功后，两个analyzer的app_frames格式完全一致，可以使用同一个CPU计算模块。
    """

    def __init__(self, cache_manager):
        """初始化CPU计算器

        Args:
            cache_manager: FrameCacheManager实例
        """
        self.cache_manager = cache_manager

    def calculate_frame_loads(
        self, frames: pd.DataFrame | list[dict], perf_df: Optional[pd.DataFrame] = None
    ) -> list[dict]:
        """计算帧负载（统一接口）

        这是统一的CPU计算接口，可以被EmptyFrameAnalyzer和RSSkipFrameAnalyzer复用。

        Args:
            frames: 帧数据（DataFrame或字典列表）
            perf_df: perf样本DataFrame（可选，如果为None则从cache_manager获取）

        Returns:
            list[dict]: 帧负载数据列表，每个元素包含frame_load字段
        """
        # 转换为DataFrame（如果需要）
        if isinstance(frames, list):
            if not frames:
                return []
            frames_df = pd.DataFrame(frames)
        else:
            frames_df = frames

        if frames_df.empty:
            return []

        # 获取perf数据
        if perf_df is None:
            perf_df = self.cache_manager.get_perf_samples() if self.cache_manager else pd.DataFrame()

        # 使用FrameLoadCalculator统一计算
        load_calculator = FrameLoadCalculator(cache_manager=self.cache_manager)
        return load_calculator.calculate_all_frame_loads_fast(frames_df, perf_df)

    def extract_cpu_from_traced_results(self, traced_results: list[dict]) -> list[dict]:
        """从追溯结果中提取CPU数据（RSSkipFrameAnalyzer专用）

        RSSkipFrameAnalyzer的追溯结果中，CPU数据已经由backtrack模块计算并嵌入到app_frame中。
        这个方法提取这些数据并转换为统一的frame_load格式。

        Args:
            traced_results: 追溯结果列表，格式为：
                [
                    {
                        'skip_frame': {...},
                        'trace_result': {
                            'app_frame': {
                                'cpu_waste': {
                                    'wasted_instructions': int,
                                    'system_instructions': int,
                                    'has_perf_data': bool
                                },
                                ...其他帧信息
                            }
                        }
                    },
                    ...
                ]

        Returns:
            list[dict]: 统一的帧负载数据列表，每个元素包含frame_load字段
        """
        frame_loads = []

        for result in traced_results:
            if not result.get('trace_result') or not result['trace_result'].get('app_frame'):
                continue

            app_frame = result['trace_result']['app_frame']
            cpu_waste = app_frame.get('cpu_waste', {})

            if not cpu_waste.get('has_perf_data'):
                continue

            # 转换格式：cpu_waste → frame_load
            frame_data = {
                'frame_id': app_frame.get('frame_id'),
                'ts': app_frame.get('frame_ts'),
                'dur': app_frame.get('frame_dur'),
                'thread_id': app_frame.get('thread_id'),
                'thread_name': app_frame.get('thread_name', 'N/A'),
                'is_main_thread': app_frame.get('is_main_thread', 0),
                'pid': app_frame.get('pid'),
                'process_name': app_frame.get('process_name', 'N/A'),
                'frame_load': cpu_waste.get('wasted_instructions', 0),  # 统一为frame_load
                'system_instructions': cpu_waste.get('system_instructions', 0),
            }

            frame_loads.append(frame_data)

        return frame_loads


class EmptyFrameCallchainAnalyzer:
    """空刷帧调用链分析模块

    统一处理EmptyFrameAnalyzer和RSSkipFrameAnalyzer的调用链分析。
    追溯成功后，两个analyzer的app_frames格式完全一致，可以使用同一个调用链分析模块。
    """

    def __init__(self, cache_manager):
        """初始化调用链分析器

        Args:
            cache_manager: FrameCacheManager实例
        """
        self.cache_manager = cache_manager
        self.load_calculator = FrameLoadCalculator(cache_manager=cache_manager)

    def analyze_callchains(
        self, frame_loads: list[dict], trace_df: pd.DataFrame, perf_df: pd.DataFrame, perf_conn, top_n: int = 10
    ) -> None:
        """分析调用链（统一接口）

        只对Top N帧进行调用链分析（性能考虑）。
        直接修改frame_loads，添加sample_callchains字段。

        Args:
            frame_loads: 帧负载数据列表（会被修改，添加sample_callchains字段）
            trace_df: 原始帧数据DataFrame（用于匹配）
            perf_df: perf样本DataFrame
            perf_conn: perf数据库连接
            top_n: Top N帧数量（默认10）

        Returns:
            None（直接修改frame_loads）
        """
        if not frame_loads or trace_df.empty:
            logger.warning('analyze_callchains: frame_loads为空或trace_df为空')
            return

        if perf_df is None or perf_df.empty:
            logger.warning('analyze_callchains: perf_df为空，尝试从cache_manager重新加载')
            # 尝试从cache_manager重新加载perf_df
            if self.cache_manager:
                perf_df = self.cache_manager.get_perf_samples()
                if perf_df is None or perf_df.empty:
                    logger.warning('analyze_callchains: 从cache_manager加载的perf_df仍为空，无法进行调用链分析')
                    # 即使perf_df为空，也要设置空的sample_callchains
                    for frame_data in frame_loads:
                        if 'sample_callchains' not in frame_data:
                            frame_data['sample_callchains'] = []
                    return
            else:
                logger.warning('analyze_callchains: cache_manager为空，无法重新加载perf_df')
                for frame_data in frame_loads:
                    if 'sample_callchains' not in frame_data:
                        frame_data['sample_callchains'] = []
                return

        # 对所有空刷帧按frame_load排序，取Top N（不区分主线程和后台线程）
        # 但排除系统线程（系统线程不计入占比，也不应该分析callchain）
        # 规则：由于frame_loads已经通过app_pids过滤，所有帧都属于应用进程
        # 因此，只排除进程名本身是系统进程的情况
        # 对于应用进程内的线程，即使名称像系统线程（如OS_VSyncThread），也不排除
        non_system_frames = [
            f
            for f in frame_loads
            if not is_system_thread(f.get('process_name'), None)  # 只检查进程名
        ]
        sorted_frames = sorted(non_system_frames, key=lambda x: x.get('frame_load', 0), reverse=True)
        top_n_frames = sorted_frames[: min(top_n, TOP_FRAMES_FOR_CALLCHAIN)]

        # logger.info(f'analyze_callchains: 开始分析Top {len(top_n_frames)}帧的调用链, 总帧数={len(frame_loads)}')
        # logger.info(f'analyze_callchains: Top N帧详情: {[(f.get("ts"), f.get("thread_id"), f.get("is_main_thread"), f.get("frame_load", 0), f.get("vsync")) for f in top_n_frames[:10]]}')
        for _i, frame_data in enumerate(top_n_frames):
            # logger.info(f'analyze_callchains: 处理第{i+1}帧: ts={frame_data.get("ts")}, tid={frame_data.get("thread_id")}, '
            #            f'is_main_thread={frame_data.get("is_main_thread")}, frame_load={frame_data.get("frame_load", 0)}, vsync={frame_data.get("vsync")}')
            # 找到对应的原始帧数据
            # 优先使用vsync匹配（如果有vsync，一定能匹配到frame_slice中的帧）
            vsync = frame_data.get('vsync')
            matching_frames = pd.DataFrame()  # 初始化为空DataFrame

            # 确保vsync不是'unknown'字符串，并且trace_df中有vsync列
            if vsync is not None and vsync != 'unknown' and 'vsync' in trace_df.columns:
                try:
                    # 确保vsync是数值类型（可能是int或str）
                    vsync_value = int(vsync) if not isinstance(vsync, (int, float)) else vsync
                    # 使用vsync匹配（最可靠的方式）
                    # 只匹配type=0的真实帧，不要期望帧
                    # 确保trace_df中的vsync也是数值类型
                    trace_vsync = pd.to_numeric(trace_df['vsync'], errors='coerce')
                    # 只匹配type=0的真实帧
                    type_mask = (
                        (trace_df['type'] == 0)
                        if 'type' in trace_df.columns
                        else pd.Series([True] * len(trace_df), index=trace_df.index)
                    )
                    frame_mask = (trace_vsync == vsync_value) & type_mask
                    matching_frames = trace_df[frame_mask]
                    if not matching_frames.empty:
                        # logger.info(f'使用vsync匹配成功: vsync={vsync_value}, ts={frame_data["ts"]}, 找到{len(matching_frames)}个匹配帧（type=0）')
                        pass
                    else:
                        logger.warning(
                            f'vsync匹配失败: vsync={vsync_value}, ts={frame_data["ts"]}, trace_df中vsync范围={sorted(trace_vsync.dropna().unique().astype(int))[:10] if not trace_vsync.empty else []}, type=0的帧数={len(trace_df[type_mask]) if "type" in trace_df.columns else len(trace_df)}'
                        )
                except (ValueError, TypeError) as e:
                    logger.warning(f'vsync类型转换失败: vsync={vsync}, error={e}, 使用备用匹配方式')
                    matching_frames = pd.DataFrame()  # 重置为空

            # 如果vsync匹配失败，使用ts、dur、tid匹配
            if matching_frames.empty:
                # 如果没有vsync或vsync匹配失败，使用ts、dur、tid匹配
                frame_mask = (
                    (trace_df['ts'] == frame_data['ts'])
                    & (trace_df['dur'] == frame_data['dur'])
                    & (trace_df['tid'] == frame_data['thread_id'])
                )
                matching_frames = trace_df[frame_mask]

                # 如果精确匹配失败，尝试只匹配ts和tid（dur可能有微小差异）
                if matching_frames.empty:
                    logger.debug(
                        f'精确匹配失败，尝试宽松匹配: ts={frame_data["ts"]}, dur={frame_data["dur"]}, tid={frame_data.get("thread_id")}'
                    )
                    loose_mask = (trace_df['ts'] == frame_data['ts']) & (trace_df['tid'] == frame_data['thread_id'])
                    matching_frames = trace_df[loose_mask]
                    if not matching_frames.empty:
                        logger.info(f'宽松匹配成功: ts={frame_data["ts"]}, 找到{len(matching_frames)}个匹配帧')

            if not matching_frames.empty:
                original_frame = matching_frames.iloc[0]
                # 确保original_frame转换为字典格式，包含所有必要字段
                if isinstance(original_frame, pd.Series):
                    frame_dict = original_frame.to_dict()
                else:
                    frame_dict = dict(original_frame) if not isinstance(original_frame, dict) else original_frame

                # 确保有所有必要字段（analyze_single_frame需要）
                if 'start_time' not in frame_dict:
                    frame_dict['start_time'] = frame_dict.get('ts', 0)
                if 'end_time' not in frame_dict:
                    frame_dict['end_time'] = frame_dict.get('ts', 0) + frame_dict.get('dur', 0)
                # 确保有tid字段（analyze_single_frame需要用于过滤perf样本）
                if 'tid' not in frame_dict:
                    frame_dict['tid'] = frame_data.get('thread_id')
                # 确保有其他必要字段（进程级查询需要pid）
                if 'pid' not in frame_dict:
                    frame_dict['pid'] = frame_data.get('pid') or frame_data.get('process_id')
                if 'app_pid' not in frame_dict and 'pid' in frame_dict:
                    frame_dict['app_pid'] = frame_dict['pid']
                if 'thread_name' not in frame_dict:
                    frame_dict['thread_name'] = frame_data.get('thread_name', 'unknown')
                if 'process_name' not in frame_dict:
                    frame_dict['process_name'] = frame_data.get('process_name', 'unknown')
                # 确保vsync字段被传递（frame_slice表必须包含vsync，用于日志和调试）
                if 'vsync' not in frame_dict or frame_dict.get('vsync') is None:
                    frame_dict['vsync'] = (
                        frame_data.get('vsync') or original_frame.get('vsync')
                        if hasattr(original_frame, 'get')
                        else None
                    )

                # 关键：将frame_data中的_sample_details传递到frame_dict中，以便analyze_single_frame使用
                if '_sample_details' in frame_data:
                    frame_dict['_sample_details'] = frame_data['_sample_details']
                    # logger.info(f'传递_sample_details到frame_dict: vsync={frame_dict.get("vsync")}, 样本数={len(frame_data["_sample_details"])}')

                try:
                    # 确保perf_df不为空（调用链分析需要）
                    if (perf_df is None or perf_df.empty) and self.cache_manager:
                        perf_df = self.cache_manager.get_perf_samples()
                        logger.info(
                            f'重新加载perf_df用于调用链分析: size={len(perf_df) if perf_df is not None and not perf_df.empty else 0}'
                        )

                    if perf_df is None or perf_df.empty:
                        logger.warning(f'perf_df仍为空，无法进行调用链分析: ts={frame_data["ts"]}')
                        frame_data['sample_callchains'] = []
                    else:
                        _, sample_callchains = self.load_calculator.analyze_single_frame(
                            frame_dict, perf_df, perf_conn, None
                        )
                        frame_data['sample_callchains'] = sample_callchains if sample_callchains else []
                        if sample_callchains:
                            # 记录成功获取调用链
                            # logger.info(f'帧调用链分析成功: ts={frame_data["ts"]}, tid={frame_dict.get("tid")}, '
                            #            f'调用链数={len(sample_callchains)}, frame_load={frame_data.get("frame_load", 0)}')
                            pass
                        else:
                            # 使用info级别，确保能看到日志
                            logger.info(
                                f'帧调用链为空: ts={frame_data["ts"]}, tid={frame_dict.get("tid")}, '
                                f'frame_start={frame_dict.get("start_time")}, frame_end={frame_dict.get("end_time")}, '
                                f'perf_df_size={len(perf_df)}, perf_df_columns={list(perf_df.columns) if not perf_df.empty else []}, '
                                f'frame_load={frame_data.get("frame_load", 0)}'
                            )
                except Exception as e:
                    logger.warning(
                        f'帧调用链分析失败: ts={frame_data["ts"]}, error={e}, frame_dict_keys={list(frame_dict.keys())}'
                    )
                    logger.debug(f'异常堆栈: {traceback.format_exc()}')
                    frame_data['sample_callchains'] = []
            else:
                logger.warning(
                    f'未找到匹配的原始帧: ts={frame_data["ts"]}, dur={frame_data["dur"]}, '
                    f'thread_id={frame_data.get("thread_id")}, is_main_thread={frame_data.get("is_main_thread")}, '
                    f'frame_load={frame_data.get("frame_load", 0)}, '
                    f'trace_df中有{len(trace_df)}帧, trace_df的tid范围={sorted(trace_df["tid"].unique())[:10] if not trace_df.empty and "tid" in trace_df.columns else []}, '
                    f'trace_df中该ts的帧数={len(trace_df[trace_df["ts"] == frame_data["ts"]]) if not trace_df.empty and "ts" in trace_df.columns else 0}'
                )
                frame_data['sample_callchains'] = []

        # 对于非Top N帧，设置空的调用链信息
        for frame_data in frame_loads:
            if frame_data not in top_n_frames and 'sample_callchains' not in frame_data:
                frame_data['sample_callchains'] = []


class EmptyFrameResultBuilder:
    """空刷帧结果构建模块（统一输出格式）

    统一构建EmptyFrameAnalyzer和RSSkipFrameAnalyzer的分析结果。
    支持RS特有的追溯统计和双重CPU统计。
    """

    def __init__(self, cache_manager):
        """初始化结果构建器

        Args:
            cache_manager: FrameCacheManager实例
        """
        self.cache_manager = cache_manager

    def build_result(
        self,
        frame_loads: list[dict],
        total_load: int = 0,
        detection_stats: Optional[dict] = None,
        deduplicated_empty_frame_load: Optional[int] = None,
        deduplicated_main_thread_load: Optional[int] = None,
        deduplicated_background_thread_load: Optional[int] = None,
        deduplicated_thread_loads: Optional[dict[int, int]] = None,
        tid_to_info: Optional[dict] = None,
    ) -> dict:
        """构建统一的分析结果

        Args:
            frame_loads: 帧负载数据列表（格式完全一致，无论来自哪个analyzer）
            total_load: 总负载（用于计算占比）
            detection_stats: 检测统计信息（可选）
                - EmptyFrameAnalyzer：可以为空
                - RSSkipFrameAnalyzer：包含追溯统计和RS进程CPU统计

        Returns:
            dict: 统一格式的分析结果
        """
        if not frame_loads:
            return self._build_empty_result(detection_stats)

        # 获取第一帧时间戳
        first_frame_time = self.cache_manager.get_first_frame_timestamp() if self.cache_manager else 0

        # === 通用处理：统一显示全局Top 10帧（与sample_callchains分析保持一致）===
        result_df = pd.DataFrame(frame_loads)

        # 排除系统线程，按frame_load排序，取全局Top 10（不区分主线程和后台线程）
        # 规则：由于frame_loads已经通过app_pids过滤，所有帧都属于应用进程
        # 因此，只排除进程名本身是系统进程的情况
        # 对于应用进程内的线程，即使名称像系统线程（如OS_VSyncThread），也不排除
        non_system_frames = result_df[
            ~result_df.apply(
                lambda row: is_system_thread(
                    row.get('process_name'),
                    None,  # 只检查进程名，不检查线程名
                ),
                axis=1,
            )
        ]

        # 全局Top 10帧（与sample_callchains分析的帧保持一致）
        # 不再区分主线程和后台线程，统一为一个列表
        top_frames_global = non_system_frames.sort_values('frame_load', ascending=False).head(TOP_FRAMES_FOR_CALLCHAIN)

        # 处理时间戳（统一处理，不区分主线程和后台线程）
        processed_all = self._process_frame_timestamps(top_frames_global, first_frame_time)

        # === 通用统计 ===
        # 如果提供了去重后的 empty_frame_load，使用它（去除重叠区域）
        # 否则使用累加的方式（包含重叠区域）
        if deduplicated_empty_frame_load is not None:
            empty_frame_load = int(deduplicated_empty_frame_load)
        else:
            empty_frame_load = int(sum(f['frame_load'] for f in frame_loads))

        # 计算主线程负载：使用去重后的值（如果提供）
        if deduplicated_main_thread_load is not None:
            main_thread_load = int(deduplicated_main_thread_load)
        else:
            # 回退到未去重的方式（从_sample_details累加）
            main_thread_load = 0

            # 构建tid到线程信息的映射（用于判断线程是否为主线程）
            if tid_to_info is None:
                tid_to_info = {}
                if self.cache_manager and self.cache_manager.trace_conn:
                    try:
                        trace_cursor = self.cache_manager.trace_conn.cursor()
                        app_pids = self.cache_manager.app_pids or []
                        if app_pids:
                            placeholders = ','.join('?' * len(app_pids))
                            trace_cursor.execute(
                                f"""
                                SELECT DISTINCT t.tid, t.name as thread_name, p.name as process_name
                                FROM thread t
                                INNER JOIN process p ON t.ipid = p.ipid
                                WHERE p.pid IN ({placeholders})
                            """,
                                app_pids,
                            )

                            for tid, thread_name, process_name in trace_cursor.fetchall():
                                tid_to_info[tid] = {
                                    'thread_name': thread_name,
                                    'process_name': process_name,
                                    'is_main_thread': 1 if thread_name == process_name else 0,
                                }
                    except Exception:
                        # logging.warning(f'查询线程信息失败: {e}')
                        pass

            # 从所有空刷帧的_sample_details中提取主线程的CPU
            for f in frame_loads:
                # 排除系统进程
                if is_system_thread(f.get('process_name'), None):
                    continue

                # 从_sample_details中提取该帧的主线程CPU
                sample_details = f.get('_sample_details', [])
                if sample_details:
                    # 累加所有主线程的event_count（不区分帧是主线程还是后台线程的帧）
                    for sample in sample_details:
                        tid = sample.get('thread_id')
                        if tid is None:
                            continue

                        # 判断该线程是否为主线程
                        thread_info = tid_to_info.get(tid, {})
                        thread_is_main = thread_info.get('is_main_thread', 0)

                        # 只累加主线程的CPU（无论这个帧是主线程还是后台线程的帧）
                        if thread_is_main == 1:
                            event_count = sample.get('event_count', 0)
                            main_thread_load += event_count

        # 计算后台线程负载：使用去重后的值（如果提供）
        if deduplicated_background_thread_load is not None:
            background_thread_load = int(deduplicated_background_thread_load)
        else:
            # 回退到未去重的方式（从_sample_details累加）
            background_thread_load = 0

            # 构建tid到线程信息的映射（用于判断线程是否为主线程）
            if tid_to_info is None:
                tid_to_info = {}
                if self.cache_manager and self.cache_manager.trace_conn:
                    try:
                        trace_cursor = self.cache_manager.trace_conn.cursor()
                        app_pids = self.cache_manager.app_pids or []
                        if app_pids:
                            placeholders = ','.join('?' * len(app_pids))
                            trace_cursor.execute(
                                f"""
                                SELECT DISTINCT t.tid, t.name as thread_name, p.name as process_name
                                FROM thread t
                                INNER JOIN process p ON t.ipid = p.ipid
                                WHERE p.pid IN ({placeholders})
                            """,
                                app_pids,
                            )

                            for tid, thread_name, process_name in trace_cursor.fetchall():
                                tid_to_info[tid] = {
                                    'thread_name': thread_name,
                                    'process_name': process_name,
                                    'is_main_thread': 1 if thread_name == process_name else 0,
                                }
                    except Exception:
                        # logging.warning(f'查询线程信息失败: {e}')
                        pass

            # 从所有空刷帧的_sample_details中提取后台线程的CPU
            for f in frame_loads:
                # 排除系统进程
                if is_system_thread(f.get('process_name'), None):
                    continue

                # 从_sample_details中提取该帧的后台线程CPU
                sample_details = f.get('_sample_details', [])
                if sample_details:
                    # 累加所有后台线程的event_count（不区分帧是主线程还是后台线程的帧）
                    for sample in sample_details:
                        tid = sample.get('thread_id')
                        if tid is None:
                            continue

                        # 判断该线程是否为主线程
                        thread_info = tid_to_info.get(tid, {})
                        thread_is_main = thread_info.get('is_main_thread', 0)

                        # 只累加后台线程的CPU（无论这个帧是主线程还是后台线程的帧）
                        if thread_is_main == 0:
                            event_count = sample.get('event_count', 0)
                            background_thread_load += event_count

        # === 阶段3：统计整个trace浪费指令数占比 ===
        # empty_frame_percentage = empty_frame_load / total_load * 100
        # 表示空刷帧的CPU浪费占整个trace总CPU的百分比
        if total_load > 0:
            empty_frame_percentage = (empty_frame_load / total_load) * 100
            main_thread_percentage = (main_thread_load / total_load) * 100
            background_thread_percentage = (background_thread_load / total_load) * 100
        else:
            empty_frame_percentage = 0.0
            main_thread_percentage = 0.0
            background_thread_percentage = 0.0

        # === 线程级别统计 ===
        # 使用去重后的线程负载（如果提供），否则回退到未去重的方式
        if deduplicated_thread_loads is not None and tid_to_info is not None:
            # 从去重后的线程负载构建 thread_statistics
            thread_loads = {}
            for tid, load in deduplicated_thread_loads.items():
                thread_info = tid_to_info.get(tid, {})
                thread_name = thread_info.get('thread_name', f'thread_{tid}')
                process_name = thread_info.get('process_name', 'N/A')

                # 排除系统进程
                if is_system_thread(process_name, None):
                    continue

                thread_key = (tid, thread_name, process_name)
                thread_loads[thread_key] = {
                    'thread_id': tid,
                    'thread_name': thread_name,
                    'process_name': process_name,
                    'total_load': load,
                    'frame_count': 0,  # 去重后无法直接统计帧数，需要从frame_loads统计
                }

            # 统计涉及该线程的帧数（从frame_loads中统计）
            for f in frame_loads:
                sample_details = f.get('_sample_details', [])
                if sample_details:
                    frame_tids = set(sample.get('thread_id') for sample in sample_details if sample.get('thread_id'))
                    for tid in frame_tids:
                        if tid in deduplicated_thread_loads:
                            thread_info = tid_to_info.get(tid, {})
                            thread_name = thread_info.get('thread_name', f'thread_{tid}')
                            process_name = thread_info.get('process_name', 'N/A')

                            if is_system_thread(process_name, None):
                                continue

                            thread_key = (tid, thread_name, process_name)
                            if thread_key in thread_loads:
                                thread_loads[thread_key]['frame_count'] += 1
        else:
            # 回退到未去重的方式（从_sample_details累加）
            thread_loads = {}

            # 构建tid到线程信息的映射（用于从_sample_details中获取线程信息）
            if tid_to_info is None:
                tid_to_info = {}
                if self.cache_manager and self.cache_manager.trace_conn:
                    try:
                        trace_cursor = self.cache_manager.trace_conn.cursor()
                        # 查询所有应用进程的线程信息
                        app_pids = self.cache_manager.app_pids or []
                        if app_pids:
                            placeholders = ','.join('?' * len(app_pids))
                            trace_cursor.execute(
                                f"""
                                SELECT DISTINCT t.tid, t.name as thread_name, p.name as process_name
                                FROM thread t
                                INNER JOIN process p ON t.ipid = p.ipid
                                WHERE p.pid IN ({placeholders})
                            """,
                                app_pids,
                            )

                            for tid, thread_name, process_name in trace_cursor.fetchall():
                                tid_to_info[tid] = {'thread_name': thread_name, 'process_name': process_name}
                    except Exception:
                        # logging.warning(f'查询线程信息失败: {e}')
                        pass

            # 从_sample_details中统计所有线程的负载
            # 遍历所有空刷帧，从每个帧的_sample_details中提取线程负载
            for f in frame_loads:
                sample_details = f.get('_sample_details', [])
                if not sample_details:
                    continue

                # 按thread_id分组，累加event_count
                thread_event_counts = {}
                for sample in sample_details:
                    tid = sample.get('thread_id')
                    if tid is None:
                        continue

                    event_count = sample.get('event_count', 0)
                    if tid not in thread_event_counts:
                        thread_event_counts[tid] = 0
                    thread_event_counts[tid] += event_count

                # 将每个线程的负载添加到thread_loads中
                for tid, event_count in thread_event_counts.items():
                    # 从tid_to_info获取线程信息
                    thread_info = tid_to_info.get(tid, {})
                    thread_name = thread_info.get('thread_name', f'thread_{tid}')
                    process_name = thread_info.get('process_name', 'N/A')

                    # 排除系统进程
                    if is_system_thread(process_name, None):
                        continue

                    # 使用(thread_id, thread_name, process_name)作为唯一标识
                    thread_key = (tid, thread_name, process_name)
                    if thread_key not in thread_loads:
                        thread_loads[thread_key] = {
                            'thread_id': tid,
                            'thread_name': thread_name,
                            'process_name': process_name,
                            'total_load': 0,
                            'frame_count': 0,
                        }
                    # 累加该线程在这个帧中的负载
                    thread_loads[thread_key]['total_load'] += event_count
                    # 统计涉及该线程的帧数（每个帧只统计一次）
                    thread_loads[thread_key]['frame_count'] += 1

        # 找出负载最多的线程
        top_threads = sorted(thread_loads.values(), key=lambda x: x['total_load'], reverse=True)[:10]  # Top 10线程

        # 计算每个线程的占比
        for thread_info in top_threads:
            if total_load > 0:
                thread_info['percentage'] = (thread_info['total_load'] / total_load) * 100
            else:
                thread_info['percentage'] = 0.0

        # 严重程度评估
        severity_level, severity_description = self._assess_severity(empty_frame_percentage, detection_stats)

        # === 构建结果（统一格式）===
        result = {
            'status': 'success',
            'summary': {
                # 通用字段
                'total_load': int(total_load),
                'empty_frame_load': int(empty_frame_load),
                'empty_frame_percentage': float(empty_frame_percentage),
                'total_empty_frames': int(len(frame_loads)),
                'empty_frames_with_load': int(len([f for f in frame_loads if f.get('frame_load', 0) > 0])),
                'main_thread_load': int(main_thread_load),
                'main_thread_percentage': float(main_thread_percentage),
                'background_thread_load': int(background_thread_load),
                'background_thread_percentage': float(background_thread_percentage),
                'severity_level': severity_level,
                'severity_description': severity_description,
            },
            'top_frames': processed_all,  # 统一列表，不再区分主线程和后台线程
            'thread_statistics': {
                'top_threads': [
                    {
                        'thread_id': t.get('thread_id'),
                        'tid': t.get('thread_id'),  # tid与thread_id相同（frame_loads中的thread_id就是tid）
                        'thread_name': t.get('thread_name'),
                        'process_name': t.get('process_name'),
                        'total_load': int(t.get('total_load', 0)),
                        'percentage': float(t.get('percentage', 0.0)),
                        'frame_count': int(t.get('frame_count', 0)),
                    }
                    for t in top_threads
                ]
            },
        }

        # === 三个检测器的原始检测结果（在合并去重之前，不处理 overlap）===
        # 无论 detection_stats 是否存在，都设置这三个字段（确保总是存在）
        if detection_stats:
            # 1. flag=2 检测器的原始检测数量
            direct_count = detection_stats.get('direct_detected_count', 0)
            result['summary']['direct_detected_count'] = direct_count

            # 2. RS skip 检测器的原始检测数量
            rs_count = detection_stats.get('rs_detected_count', 0)
            result['summary']['rs_detected_count'] = rs_count

            # 3. 框架特定检测器的原始检测数量
            framework_counts = detection_stats.get('framework_detected_counts')
            framework_counts = framework_counts if framework_counts is not None else {}
            result['summary']['framework_detection_counts'] = framework_counts
        else:
            # 如果没有 detection_stats，设置默认值
            result['summary']['direct_detected_count'] = 0
            result['summary']['rs_detected_count'] = 0
            result['summary']['framework_detection_counts'] = {}

        # === RS特有字段（如果有）===
        if detection_stats:
            # 追溯统计
            if 'total_skip_frames' in detection_stats:
                result['summary'].update(
                    {
                        'total_skip_frames': detection_stats.get('total_skip_frames', 0),
                        'total_skip_events': detection_stats.get('total_skip_events', 0),
                        'trace_accuracy': detection_stats.get('trace_accuracy', 0.0),
                        'traced_success_count': detection_stats.get('traced_success_count', 0),
                        'rs_api_success': detection_stats.get('rs_api_success', 0),
                        'nativewindow_success': detection_stats.get('nativewindow_success', 0),
                        'failed': detection_stats.get('failed', 0),
                    }
                )

                # 追溯成功率低的警告
                if detection_stats.get('trace_accuracy', 100.0) < 50.0:
                    trace_warning = (
                        f'警告：RS Skip帧追溯成功率较低({detection_stats["trace_accuracy"]:.1f}%)，'
                        f'可能导致CPU浪费统计不准确。'
                    )
                    result['summary']['trace_warning'] = trace_warning

            # RS进程CPU统计（新增）
            if 'rs_skip_cpu' in detection_stats:
                result['summary'].update(
                    {
                        'rs_skip_cpu': detection_stats.get('rs_skip_cpu', 0),
                        'rs_skip_percentage': detection_stats.get('rs_skip_percentage', 0.0),
                        'app_empty_cpu': empty_frame_load,  # 应用进程CPU = empty_frame_load
                        'app_empty_percentage': empty_frame_percentage,
                        'total_wasted_cpu': detection_stats.get('total_wasted_cpu', 0),
                    }
                )

        # 占比超过100%的警告
        if empty_frame_percentage > 100.0:
            percentage_warning = (
                f'注意：空刷帧占比超过100% ({empty_frame_percentage:.2f}%)，'
                f'这是因为时间窗口扩展（±1ms）导致多个帧的CPU计算存在重叠。'
            )
            result['summary']['percentage_warning'] = percentage_warning

        return result

    def _build_empty_result(self, detection_stats: Optional[dict] = None) -> dict:
        """构建空结果（当没有空刷帧时）

        Args:
            detection_stats: 检测统计信息（可选）

        Returns:
            dict: 空结果字典
        """
        result = {
            'status': 'success',
            'summary': {
                'total_load': 0,
                'empty_frame_load': 0,
                'empty_frame_percentage': 0.0,
                'total_empty_frames': 0,
                'empty_frames_with_load': 0,
                'background_thread_load': 0,
                'background_thread_percentage': 0.0,
                'severity_level': 'normal',
                'severity_description': '正常：未检测到空刷帧。',
            },
            'top_frames': [],  # 统一列表，不再区分主线程和后台线程
            'thread_statistics': {'top_threads': []},
        }

        # === 三个检测器的原始检测结果（在合并去重之前，不处理 overlap）===
        # 同时添加到 summary 和最外层（双重保障）
        if detection_stats:
            direct_count = detection_stats.get('direct_detected_count', 0)
            rs_count = detection_stats.get('rs_detected_count', 0)
            framework_counts = detection_stats.get('framework_detected_counts', {})
            framework_counts = framework_counts if framework_counts is not None else {}

            result['summary']['direct_detected_count'] = direct_count
            result['summary']['rs_detected_count'] = rs_count
            result['summary']['framework_detection_counts'] = framework_counts
        else:
            # 如果没有 detection_stats，设置默认值
            result['summary']['direct_detected_count'] = 0
            result['summary']['rs_detected_count'] = 0
            result['summary']['framework_detection_counts'] = {}

        # RS特有字段
        if detection_stats and 'total_skip_frames' in detection_stats:
            result['summary'].update(
                {
                    'total_skip_frames': 0,
                    'total_skip_events': 0,
                    'traced_success_count': 0,
                    'trace_accuracy': 0.0,
                    'rs_api_success': 0,
                    'nativewindow_success': 0,
                    'failed': 0,
                }
            )

        return result

    def _assess_severity(
        self, empty_frame_percentage: float, detection_stats: Optional[dict] = None
    ) -> tuple[str, str]:
        """评估严重程度

        Args:
            empty_frame_percentage: 空刷帧CPU占比
            detection_stats: 检测统计信息（可选）

        Returns:
            (severity_level, severity_description)
        """
        # 如果是RS checker且追溯成功率低，优先标记为critical
        if detection_stats and 'trace_accuracy' in detection_stats:
            trace_accuracy = detection_stats.get('trace_accuracy', 100.0)
            if trace_accuracy < 50.0:
                return (
                    'critical',
                    f'严重：RS Skip帧追溯成功率仅{trace_accuracy:.1f}%，数据质量差，无法准确评估CPU浪费。',
                )

        # 根据占比判断严重程度
        if empty_frame_percentage < 3.0:
            return ('normal', '正常：空刷帧CPU占比小于3%，属于正常范围。')
        if empty_frame_percentage < 10.0:
            return ('moderate', '较为严重：空刷帧CPU占比在3%-10%之间，建议关注并优化。')
        if empty_frame_percentage <= 100.0:
            return ('severe', '严重：空刷帧CPU占比超过10%，需要优先优化。')
        # > 100%
        return (
            'extreme',
            f'极端异常：空刷帧CPU占比超过100% ({empty_frame_percentage:.2f}%)。'
            f'这是因为时间窗口扩展（±1ms）导致多个帧的CPU计算存在重叠。',
        )

    def _process_frame_timestamps(self, frames_df: pd.DataFrame, first_frame_time: int) -> list:
        """处理帧时间戳，转换为相对时间

        Args:
            frames_df: 帧数据DataFrame
            first_frame_time: 第一帧时间戳

        Returns:
            list: 处理后的帧数据列表
        """
        processed_frames = []
        for _, frame in frames_df.iterrows():
            frame_dict = clean_frame_data(frame.to_dict())
            # 转换时间戳为相对时间
            frame_dict['ts'] = FrameTimeUtils.convert_to_relative_nanoseconds(frame.get('ts', 0), first_frame_time)
            processed_frames.append(frame_dict)

        return processed_frames
