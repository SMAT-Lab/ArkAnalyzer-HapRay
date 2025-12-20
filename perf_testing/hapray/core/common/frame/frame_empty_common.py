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

import sqlite3
import logging
import traceback
from typing import Optional, Dict, Set, Tuple

import pandas as pd

from .frame_utils import is_system_thread, clean_frame_data

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


def calculate_thread_instructions(
    perf_conn: sqlite3.Connection,
    trace_conn: sqlite3.Connection,
    thread_ids: Set[int],
    frame_start: int,
    frame_end: int,
    tid_to_info_cache: Optional[Dict] = None,
    perf_sample_cache: Optional[Dict] = None,
    perf_timestamp_field: Optional[str] = None
) -> Tuple[Dict[int, int], Dict[int, int]]:
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
            import bisect
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
        perf_cursor.execute("PRAGMA table_info(perf_sample)")
        columns = [row[1] for row in perf_cursor.fetchall()]
        timestamp_field = perf_timestamp_field if perf_timestamp_field else ('timestamp_trace' if 'timestamp_trace' in columns else 'timeStamp')
        
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
            trace_cursor.execute(f"""
                SELECT DISTINCT t.tid, t.name as thread_name, p.name as process_name
                FROM thread t
                INNER JOIN process p ON t.ipid = p.ipid
                WHERE t.tid IN ({placeholders})
            """, thread_ids_list)
            
            for tid, thread_name, process_name in trace_cursor.fetchall():
                thread_info_map[tid] = {
                    'thread_name': thread_name,
                    'process_name': process_name
                }
        
        # 优化：使用索引提示，批量查询所有线程的指令数
        # 使用EXPLAIN QUERY PLAN优化查询性能
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
        
        for thread_id, instruction_count in results:
            thread_info = thread_info_map.get(thread_id, {})
            process_name = thread_info.get('process_name')
            thread_name = thread_info.get('thread_name')
            
            if is_system_thread(process_name, thread_name):
                system_thread_instructions[thread_id] = instruction_count
            else:
                app_thread_instructions[thread_id] = instruction_count
        
        return app_thread_instructions, system_thread_instructions
        
    except Exception as e:
        logger.error('计算线程指令数失败: %s', str(e))
        logger.error('异常堆栈跟踪:\n%s', traceback.format_exc())
        return {}, {}


def calculate_process_instructions(
    perf_conn: sqlite3.Connection,
    trace_conn: sqlite3.Connection,
    app_pid: int,
    frame_start: int,
    frame_end: int,
    perf_sample_cache: Optional[Dict] = None,
    perf_timestamp_field: Optional[str] = None,
    tid_to_info_cache: Optional[Dict] = None
) -> Tuple[int, int]:
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
        extended_start = frame_start - 1_000_000  # 1ms before
        extended_end = frame_end + 1_000_000  # 1ms after
        
        # 步骤1: 查找应用进程的所有线程ID（tid）
        trace_cursor = trace_conn.cursor()
        trace_cursor.execute("""
            SELECT DISTINCT t.tid
            FROM thread t
            INNER JOIN process p ON t.ipid = p.ipid
            WHERE p.pid = ?
        """, (app_pid,))
        
        thread_tids = [row[0] for row in trace_cursor.fetchall()]
        
        if not thread_tids:
            logger.debug(f'进程 {app_pid} 没有找到任何线程')
            return 0, 0
        
        # 步骤2: 计算这些线程在帧时间范围内的CPU指令数
        # 注意：calculate_thread_instructions内部会使用扩展时间窗口（±1ms），
        # 所以这里直接传递原始的frame_start和frame_end即可
        thread_ids = set(thread_tids)
        app_instructions_dict, system_instructions_dict = calculate_thread_instructions(
            perf_conn=perf_conn,
            trace_conn=trace_conn,
            thread_ids=thread_ids,
            frame_start=frame_start,
            frame_end=frame_end,
            tid_to_info_cache=tid_to_info_cache,
            perf_sample_cache=perf_sample_cache,
            perf_timestamp_field=perf_timestamp_field
        )
        
        # 步骤3: 汇总所有线程的指令数
        app_instructions = sum(app_instructions_dict.values())
        system_instructions = sum(system_instructions_dict.values())
        
        logger.debug(f'进程 {app_pid} CPU统计: 应用线程={app_instructions:,} 指令, 系统线程={system_instructions:,} 指令')
        
        return app_instructions, system_instructions
        
    except Exception as e:
        logger.error(f'计算进程CPU指令数失败 (PID={app_pid}): {e}')
        logger.error('异常堆栈跟踪:\n%s', traceback.format_exc())
        return 0, 0


def calculate_app_frame_cpu_waste(
    trace_conn: sqlite3.Connection,
    perf_conn: Optional[sqlite3.Connection],
    app_frame: Dict,
    perf_sample_cache: Optional[Dict] = None,
    perf_timestamp_field: Optional[str] = None,
    tid_to_info_cache: Optional[Dict] = None,
    use_process_level: bool = True
) -> Dict:
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
        return {
            'wasted_instructions': 0,
            'system_instructions': 0,
            'has_perf_data': False
        }
    
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
                    tid_to_info_cache=tid_to_info_cache
                )
                return {
                    'wasted_instructions': app_instructions,
                    'system_instructions': system_instructions,
                    'has_perf_data': True
                }
            else:
                logger.warning('use_process_level=True 但 app_frame 中没有 app_pid，回退到线程级统计')
        
        # 向后兼容：线程级统计（只计算帧对应线程的CPU）
        itid = app_frame.get('thread_id')
        if not itid:
            return {
                'wasted_instructions': 0,
                'system_instructions': 0,
                'has_perf_data': False
            }
        
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
            cursor.execute("SELECT tid FROM thread WHERE id = ?", (itid,))
            result = cursor.fetchone()
            if result:
                tid = result[0]
        
        if not tid:
            logger.warning(f'无法从itid {itid} 获取tid')
            return {
                'wasted_instructions': 0,
                'system_instructions': 0,
                'has_perf_data': False
            }
        
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
            perf_timestamp_field=perf_timestamp_field
        )
        
        wasted_instructions = app_instructions.get(tid, 0)
        sys_instructions = system_instructions.get(tid, 0)
        
        return {
            'wasted_instructions': wasted_instructions,
            'system_instructions': sys_instructions,
            'has_perf_data': True
        }
    except Exception as e:
        logger.warning(f'计算CPU指令数失败: {e}')
        return {
            'wasted_instructions': 0,
            'system_instructions': 0,
            'has_perf_data': False,
            'error': str(e)
        }


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
        self, 
        frames: pd.DataFrame | list[dict],
        perf_df: Optional[pd.DataFrame] = None
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
        from .frame_core_load_calculator import FrameLoadCalculator
        load_calculator = FrameLoadCalculator(cache_manager=self.cache_manager)
        frame_loads = load_calculator.calculate_all_frame_loads_fast(frames_df, perf_df)
        
        return frame_loads
    
    def extract_cpu_from_traced_results(
        self, 
        traced_results: list[dict]
    ) -> list[dict]:
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
        from .frame_core_load_calculator import FrameLoadCalculator
        self.load_calculator = FrameLoadCalculator(cache_manager=cache_manager)
    
    def analyze_callchains(
        self,
        frame_loads: list[dict],
        trace_df: pd.DataFrame,
        perf_df: pd.DataFrame,
        perf_conn,
        top_n: int = 10
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
            return
        
        from .frame_constants import TOP_FRAMES_FOR_CALLCHAIN
        
        # 对Top N帧进行调用链分析
        sorted_frames = sorted(frame_loads, key=lambda x: x.get('frame_load', 0), reverse=True)
        top_n_frames = sorted_frames[:min(top_n, TOP_FRAMES_FOR_CALLCHAIN)]
        
        for frame_data in top_n_frames:
            # 找到对应的原始帧数据
            frame_mask = (
                (trace_df['ts'] == frame_data['ts'])
                & (trace_df['dur'] == frame_data['dur'])
                & (trace_df['tid'] == frame_data['thread_id'])
            )
            original_frame = trace_df[frame_mask].iloc[0] if not trace_df[frame_mask].empty else None
            
            if original_frame is not None:
                try:
                    _, sample_callchains = self.load_calculator.analyze_single_frame(
                        original_frame, perf_df, perf_conn, None
                    )
                    frame_data['sample_callchains'] = sample_callchains
                except Exception as e:
                    logger.warning(f'帧调用链分析失败: ts={frame_data["ts"]}, error={e}')
                    frame_data['sample_callchains'] = []
            else:
                frame_data['sample_callchains'] = []
        
        # 对于非Top N帧，设置空的调用链信息
        for frame_data in frame_loads:
            if frame_data not in top_n_frames:
                if 'sample_callchains' not in frame_data:
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
        detection_stats: Optional[Dict] = None
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
        
        # === 通用处理：区分主线程/后台线程 ===
        result_df = pd.DataFrame(frame_loads)
        
        main_thread_frames = (
            result_df[result_df['is_main_thread'] == 1]
            .sort_values('frame_load', ascending=False)
            .head(5)
        )
        background_thread_frames = (
            result_df[result_df['is_main_thread'] == 0]
            .sort_values('frame_load', ascending=False)
            .head(5)
        )
        
        # 处理时间戳
        processed_main = self._process_frame_timestamps(main_thread_frames, first_frame_time)
        processed_bg = self._process_frame_timestamps(background_thread_frames, first_frame_time)
        
        # === 通用统计 ===
        empty_frame_load = int(sum(f['frame_load'] for f in frame_loads))
        background_thread_load = int(sum(f['frame_load'] for f in frame_loads if f.get('is_main_thread') != 1))
        
        if total_load > 0:
            empty_frame_percentage = (empty_frame_load / total_load) * 100
            background_thread_percentage = (background_thread_load / total_load) * 100
        else:
            empty_frame_percentage = 0.0
            background_thread_percentage = 0.0
        
        # 严重程度评估
        severity_level, severity_description = self._assess_severity(
            empty_frame_percentage, detection_stats
        )
        
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
                'background_thread_load': int(background_thread_load),
                'background_thread_percentage': float(background_thread_percentage),
                'severity_level': severity_level,
                'severity_description': severity_description,
            },
            'top_frames': {
                'main_thread_empty_frames': processed_main,
                'background_thread': processed_bg,
            }
        }
        
        # === RS特有字段（如果有）===
        if detection_stats:
            # 追溯统计
            if 'total_skip_frames' in detection_stats:
                result['summary'].update({
                    'total_skip_frames': detection_stats.get('total_skip_frames', 0),
                    'total_skip_events': detection_stats.get('total_skip_events', 0),
                    'trace_accuracy': detection_stats.get('trace_accuracy', 0.0),
                    'traced_success_count': detection_stats.get('traced_success_count', 0),
                    'rs_api_success': detection_stats.get('rs_api_success', 0),
                    'nativewindow_success': detection_stats.get('nativewindow_success', 0),
                    'failed': detection_stats.get('failed', 0),
                })
                
                # 追溯成功率低的警告
                if detection_stats.get('trace_accuracy', 100.0) < 50.0:
                    trace_warning = (
                        f"警告：RS Skip帧追溯成功率较低({detection_stats['trace_accuracy']:.1f}%)，"
                        f"可能导致CPU浪费统计不准确。"
                    )
                    result['summary']['trace_warning'] = trace_warning
            
            # RS进程CPU统计（新增）
            if 'rs_skip_cpu' in detection_stats:
                result['summary'].update({
                    'rs_skip_cpu': detection_stats.get('rs_skip_cpu', 0),
                    'rs_skip_percentage': detection_stats.get('rs_skip_percentage', 0.0),
                    'app_empty_cpu': empty_frame_load,  # 应用进程CPU = empty_frame_load
                    'app_empty_percentage': empty_frame_percentage,
                    'total_wasted_cpu': detection_stats.get('total_wasted_cpu', 0),
                })
        
        # 占比超过100%的警告
        if empty_frame_percentage > 100.0:
            percentage_warning = (
                f"注意：空刷帧占比超过100% ({empty_frame_percentage:.2f}%)，"
                f"这是因为时间窗口扩展（±1ms）导致多个帧的CPU计算存在重叠。"
            )
            result['summary']['percentage_warning'] = percentage_warning
        
        return result
    
    def _build_empty_result(self, detection_stats: Optional[Dict] = None) -> dict:
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
                'severity_description': '正常：未检测到空刷帧。'
            },
            'top_frames': {
                'main_thread_empty_frames': [],
                'background_thread': [],
            },
        }
        
        # RS特有字段
        if detection_stats and 'total_skip_frames' in detection_stats:
            result['summary'].update({
                'total_skip_frames': 0,
                'total_skip_events': 0,
                'traced_success_count': 0,
                'trace_accuracy': 0.0,
                'rs_api_success': 0,
                'nativewindow_success': 0,
                'failed': 0,
            })
        
        return result
    
    def _assess_severity(
        self, 
        empty_frame_percentage: float,
        detection_stats: Optional[Dict] = None
    ) -> Tuple[str, str]:
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
                return ("critical", 
                       f"严重：RS Skip帧追溯成功率仅{trace_accuracy:.1f}%，"
                       f"数据质量差，无法准确评估CPU浪费。")
        
        # 根据占比判断严重程度
        if empty_frame_percentage < 3.0:
            return ("normal", "正常：空刷帧CPU占比小于3%，属于正常范围。")
        elif empty_frame_percentage < 10.0:
            return ("moderate", "较为严重：空刷帧CPU占比在3%-10%之间，建议关注并优化。")
        elif empty_frame_percentage <= 100.0:
            return ("severe", "严重：空刷帧CPU占比超过10%，需要优先优化。")
        else:  # > 100%
            return ("extreme", 
                   f"极端异常：空刷帧CPU占比超过100% ({empty_frame_percentage:.2f}%)。"
                   f"这是因为时间窗口扩展（±1ms）导致多个帧的CPU计算存在重叠。")
    
    def _process_frame_timestamps(self, frames_df: pd.DataFrame, first_frame_time: int) -> list:
        """处理帧时间戳，转换为相对时间
        
        Args:
            frames_df: 帧数据DataFrame
            first_frame_time: 第一帧时间戳
        
        Returns:
            list: 处理后的帧数据列表
        """
        from .frame_time_utils import FrameTimeUtils
        
        processed_frames = []
        for _, frame in frames_df.iterrows():
            frame_dict = clean_frame_data(frame.to_dict())
            # 转换时间戳为相对时间
            frame_dict['ts'] = FrameTimeUtils.convert_to_relative_nanoseconds(
                frame.get('ts', 0), first_frame_time
            )
            processed_frames.append(frame_dict)
        
        return processed_frames

