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
from typing import Any, Optional, Dict, Set, Tuple

import pandas as pd

"""帧分析工具函数模块

提供帧分析中常用的工具函数，避免代码重复。
"""

logger = logging.getLogger(__name__)


def clean_frame_data(frame_data: dict[str, Any]) -> dict[str, Any]:
    """清理帧数据中的NaN值，确保JSON序列化安全

    Args:
        frame_data: 原始帧数据字典

    Returns:
        dict: 清理后的帧数据字典
    """
    cleaned_data: dict[str, Any] = {}
    skip_fields = {'frame_samples', 'index'}

    for key, value in frame_data.items():
        if key in skip_fields:
            continue
        cleaned_data[key] = clean_single_value(value)

    return cleaned_data


def clean_single_value(value: Any) -> Any:
    """清理单个值，确保JSON序列化安全

    Args:
        value: 待清理的值

    Returns:
        清理后的值
    """
    if hasattr(value, 'dtype') and hasattr(value, 'item'):
        return clean_numpy_value(value)
    return clean_regular_value(value)


def clean_numpy_value(value: Any) -> Any:
    """清理numpy/pandas类型的值

    Args:
        value: numpy/pandas类型的值

    Returns:
        清理后的值
    """
    try:
        if hasattr(pd.isna(value), 'any'):
            if pd.isna(value).any():
                return 0
            return value.item()

        if pd.isna(value):
            return 0
        return value.item()
    except (ValueError, TypeError):
        return None


def clean_regular_value(value: Any) -> Any:
    """清理普通类型的值

    Args:
        value: 普通类型的值

    Returns:
        清理后的值
    """
    try:
        if pd.isna(value):
            if isinstance(value, (int, float)):
                return 0
            return None
        return value
    except (ValueError, TypeError):
        return value


def validate_app_pids(app_pids: Optional[list]) -> list[int]:
    """验证并过滤应用进程ID列表

    Args:
        app_pids: 应用进程ID列表

    Returns:
        list: 有效的进程ID列表
    """
    if not app_pids or not isinstance(app_pids, (list, tuple)) or len(app_pids) == 0:
        return []

    return [int(pid) for pid in app_pids if pd.notna(pid) and isinstance(pid, (int, float))]


def is_system_thread(process_name: Optional[str], thread_name: Optional[str]) -> bool:
    """判断线程是否为系统线程（参考RN实现）
    
    系统线程包括：
    - hiperf（性能采集工具）
    - render_service（渲染服务）
    - sysmgr-main（系统管理）
    - OS_开头的线程
    - ohos.开头的线程
    - pp.开头的线程
    - 其他系统服务
    
    Args:
        process_name: 进程名
        thread_name: 线程名
        
    Returns:
        True 如果是系统线程，False 如果是应用线程
    """
    if not process_name:
        process_name = ""
    if not thread_name:
        thread_name = ""
    
    # 系统进程名模式
    system_process_patterns = [
        'hiperf',
        'render_service',
        'sysmgr-main',
        'OS_%',
        'ohos.%',
        'pp.%',
        'hilogd',
        'hiprofiler',
        'hiprofiler_cmd',
        'hiprofiler_plug',
        'hiprofilerd',
        'kworker',
        'hdcd',
        'hiview',
        'foundation',
        'resource_schedu',
        'netmanager',
        'wifi_manager',
        'telephony',
        'sensors',
        'multimodalinput',
        'accountmgr',
        'accesstoken_ser',
        'samgr',
        'memmgrservice',
        'distributeddata',
        'privacy_service',
        'security_guard',
        'time_service',
        'bluetooth_servi',
        'media_service',
        'audio_server',
        'rmrenderservice',
        'ohos.sceneboard',
    ]
    
    # 系统线程名模式
    system_thread_patterns = [
        'OS_%',
        'ohos.%',
        'pp.%',
        'hiperf',
        'hiprofiler',
        'hiprofiler_cmd',
        'hiprofiler_plug',
        'hiprofilerd',
        'HmTraceReader',
        'kworker',
        'hilogd',
        'render_service',
        'VSyncGenerator',
        'RSUniRenderThre',
        'RSHardwareThrea',
        'RSBackgroundThr',
        'Present Fence',
        'Acquire Fence',
        'Release Fence',
        'gpu-work-server',
        'tppmgr-sched-in',
        'tppmgr-misc',
        'fs-kmsgfd',
        'dh-irq-bind',
        'dpu_gfx_primary',
        'display_engine_',
        'gpu-pm-release',
        'hisi_frw',
        'rcu_sched',
        'effect thread',
        'gpu-wq-id',
        'gpu-token-id',
        'irq/',
        'ksoftirqd',
        'netlink_handle',
        'hisi_tx_sch',
        'hisi_hcc',
        'hisi_rxdata',
        'spi',
        'gpufreq',
        'npu_excp',
        'dra_thread',
        'agent_vltmm',
        'tuid',
        'hw_kstate',
        'pci_ete_rx0',
        'wlan_bus_rx',
        'bbox_main',
        'kthread-joind',
        'dmabuf-deferred',
        'chr_web_thread',
        'ldk-kallocd',
    ]
    
    # 检查进程名
    for pattern in system_process_patterns:
        if pattern.endswith('%'):
            if process_name.startswith(pattern[:-1]):
                return True
        elif pattern.endswith('.'):
            if process_name.startswith(pattern):
                return True
        else:
            if pattern in process_name or process_name == pattern:
                return True
    
    # 检查线程名
    for pattern in system_thread_patterns:
        if pattern.endswith('%'):
            if thread_name.startswith(pattern[:-1]):
                return True
        elif pattern.endswith('_'):
            if thread_name.startswith(pattern):
                return True
        else:
            if pattern in thread_name or thread_name == pattern:
                return True
    
    return False


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
