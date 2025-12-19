"""
应用层空刷帧唤醒链分析：通过线程唤醒关系找到空刷帧相关的所有线程

分析逻辑：
1. 找到 flag=2 的空刷帧（没有送到 RS 线程）
2. 找到这个帧最后事件绑定的线程
3. 通过线程唤醒关系（sched_wakeup 事件）找到所有相关的线程
4. 统计这些线程在帧时间范围内的 CPU 指令数（浪费的 CPU）
"""

import sqlite3
import logging
import sys
import traceback
import time
from typing import Optional, List, Dict, Any, Set, Tuple
from collections import defaultdict, deque
import json
import os
import random

# 注意：移除模块级别的日志配置，避免导入时的冲突
logger = logging.getLogger(__name__)

# 从frame_empty_common和frame_utils导入函数（使用相对导入）
from .frame_empty_common import (
    calculate_thread_instructions,
    calculate_process_instructions
)
from .frame_utils import is_system_thread


def find_frame_last_event(trace_conn, frame: Dict[str, Any], 
                          callstack_id_cache: Optional[Dict] = None,
                          callstack_events_cache: Optional[Dict] = None) -> Optional[Dict[str, Any]]:
    """找到帧的最后事件（性能优化：支持缓存）
    
    策略：
    1. 优先使用 callstack_id 对应的事件（这是帧记录时绑定的调用栈）
    2. 如果没有 callstack_id，找该线程在帧时间范围内的最后一个事件
    
    Args:
        trace_conn: trace 数据库连接
        frame: 帧信息字典，包含 ts, dur, itid, callstack_id
        callstack_id_cache: callstack_id -> callstack记录的缓存
        callstack_events_cache: (itid, min_ts, max_ts) -> callstack记录列表的缓存
        
    Returns:
        最后事件的信息，包含 ts, name, callid, itid
    """
    try:
        frame_start = frame['ts']
        frame_end = frame['ts'] + frame.get('dur', 0)
        frame_itid = frame['itid']
        
        # 策略1: 优先使用 callstack_id 对应的事件（使用缓存）
        if frame.get('callstack_id'):
            if callstack_id_cache and frame['callstack_id'] in callstack_id_cache:
                result = callstack_id_cache[frame['callstack_id']]
                return {
                    'id': result[0],
                    'ts': result[1],
                    'dur': result[2] if result[2] else 0,
                    'name': result[3],
                    'callid': result[4],
                    'itid': result[4]
                }
            else:
                # 向后兼容：如果没有缓存，查询数据库
                cursor = trace_conn.cursor()
            callstack_query = """
            SELECT 
                c.id,
                c.ts,
                c.dur,
                c.name,
                c.callid
            FROM callstack c
            WHERE c.id = ?
            """
            cursor.execute(callstack_query, (frame['callstack_id'],))
            result = cursor.fetchone()
            if result:
                return {
                    'id': result[0],
                    'ts': result[1],
                    'dur': result[2] if result[2] else 0,
                    'name': result[3],
                    'callid': result[4],
                        'itid': result[4]
                    }
        
        # 策略2: 找该线程在帧时间范围内的最后一个事件（使用缓存）
        if callstack_events_cache:
            # 从缓存中查找：查找该线程在时间范围内的最后一个事件
            cache_key = (frame_itid, frame_start, frame_end)
            if cache_key in callstack_events_cache:
                events = callstack_events_cache[cache_key]
                if events:
                    # 取最后一个（按ts排序）
                    result = max(events, key=lambda x: x[1])  # x[1]是ts
                    return {
                        'id': result[0],
                        'ts': result[1],
                        'dur': result[2] if result[2] else 0,
                        'name': result[3],
                        'callid': result[4],
                        'itid': result[4]
                    }
        else:
            # 向后兼容：如果没有缓存，查询数据库
            cursor = trace_conn.cursor()
        last_event_query = """
        SELECT 
            c.id,
            c.ts,
            c.dur,
            c.name,
            c.callid
        FROM callstack c
        WHERE c.callid = ?
        AND c.ts >= ? AND c.ts <= ?
        ORDER BY c.ts DESC
        LIMIT 1
        """
        cursor.execute(last_event_query, (frame_itid, frame_start, frame_end))
        result = cursor.fetchone()
        if result:
            return {
                'id': result[0],
                'ts': result[1],
                'dur': result[2] if result[2] else 0,
                'name': result[3],
                'callid': result[4],
                    'itid': result[4]
            }
        
        # 如果都找不到，返回帧的线程信息作为最后事件
        logger.warning('帧 %d 未找到最后事件，使用线程信息', frame.get('frame_id', 'unknown'))
        return {
            'id': None,
            'ts': frame_start,
            'dur': frame.get('dur', 0),
            'name': 'frame_end',
            'callid': frame_itid,
            'itid': frame_itid
        }
        
    except Exception as e:
        logger.error('查找帧最后事件失败: %s', str(e))
        return None


def filter_threads_executed_in_frame(trace_conn, itids: Set[int], frame_start: int, 
                                     frame_end: int, 
                                     callstack_cache: Optional[Set[int]] = None,
                                     thread_state_cache: Optional[Set[int]] = None) -> Set[int]:
    """过滤线程，保留在帧时间范围内实际在CPU上执行过的线程，以及唤醒链中的关键线程
    
    策略：
    1. 保留在帧时间范围内有 Running/Runnable 状态的线程
    2. 保留在帧时间范围内有 callstack 活动的线程
    3. 对于唤醒链中的线程，即使帧内未执行，如果：
       - 在帧时间前后被唤醒（扩展时间范围）
       - 或者在帧时间范围内有任何状态记录（包括sleep状态）
       也应该保留，因为它们是唤醒链的一部分
    
    根据文档：
    - thread_state 表：记录线程状态，state='R' (Runnable) 或 'Runing' (Running) 表示在CPU上执行
    - callstack 表：记录调用堆栈，callid 对应线程的 itid，有活动说明线程执行过
    
    Args:
        trace_conn: trace 数据库连接
        itids: 线程 itid 集合（来自唤醒链）
        frame_start: 帧开始时间
        frame_end: 帧结束时间
        
    Returns:
        与帧相关的线程 itid 集合（包括执行过的和唤醒链中的关键线程）
    """
    if not itids:
        return set()
    
    try:
        cursor = trace_conn.cursor()
        executed_threads = set()
        
        # 性能优化：减少时间范围扩展，只扩展10ms
        extended_start = frame_start - 10_000_000  # 10ms
        extended_end = frame_end + 5_000_000  # 5ms
        
        # 性能优化：优先使用缓存，如果没有缓存才查询数据库
        if callstack_cache is not None and thread_state_cache is not None:
            # 使用缓存：直接检查itids是否在缓存中
            for itid in itids:
                if itid in callstack_cache or itid in thread_state_cache:
                    executed_threads.add(itid)
        else:
            # 向后兼容：如果没有缓存，查询数据库
            if itids:
                itids_list = list(itids)
                placeholders = ','.join('?' * len(itids_list))
                
                # 合并查询：同时检查帧内和扩展时间范围
                callstack_query = f"""
                SELECT DISTINCT callid
                FROM callstack
                WHERE callid IN ({placeholders})
                AND ts >= ?
                AND ts <= ?
                """
                
                params = itids_list + [extended_start, extended_end]
                cursor.execute(callstack_query, params)
                callstack_results = cursor.fetchall()
                for (callid,) in callstack_results:
                    executed_threads.add(callid)
                
                # 方法2: 检查 thread_state 表（只查Running/Runnable状态，减少查询）
                thread_state_query = f"""
                SELECT DISTINCT itid
                FROM thread_state
                WHERE itid IN ({placeholders})
                AND state IN ('R', 'Runing')
                AND ts <= ?
                AND ts + dur >= ?
                """
                
                params = itids_list + [extended_end, extended_start]
                cursor.execute(thread_state_query, params)
                state_results = cursor.fetchall()
                for (itid,) in state_results:
                    executed_threads.add(itid)
        
        logger.debug(f'帧时间范围内相关的线程: {len(executed_threads)}/{len(itids)}')
        return executed_threads
        
    except Exception as e:
        logger.warning('过滤执行线程失败，返回所有线程: %s', str(e))
        return itids  # 如果出错，返回所有线程


def find_wakeup_chain(trace_conn, start_itid: int, frame_start: int, frame_end: int, 
                     max_depth: int = 20, instant_cache: Optional[Dict] = None,
                     app_pid: Optional[int] = None) -> Set[int]:
    """通过线程唤醒关系找到所有相关的线程（唤醒链）
    
    策略：从最后的线程开始，反向追溯唤醒链，直到找到系统VSync线程或达到最大深度
    时间范围：扩展到帧开始前20ms（约1-2个VSync周期），以确保能找到完整的唤醒链
    
    Args:
        trace_conn: trace 数据库连接
        start_itid: 起始线程的 itid（通常是帧最后事件绑定的线程）
        frame_start: 帧开始时间
        frame_end: 帧结束时间
        max_depth: 最大搜索深度（默认10）
        instant_cache: instant表数据缓存 {(ref, ts_range): [(wakeup_from, ts), ...]}
        
    Returns:
        所有相关线程的 itid 集合
    """
    try:
        # 扩展时间范围：往前追溯50ms，确保能找到完整的唤醒链（参考RN实现）
        search_start = frame_start - 50_000_000  # 50ms in nanoseconds
        search_end = frame_end
        
        # 如果提供了app_pid，预先查询应用进程的所有线程itid（用于优先查找）
        app_thread_itids = set()
        if app_pid:
            cursor = trace_conn.cursor()
            cursor.execute("""
                SELECT t.itid
                FROM thread t
                INNER JOIN process p ON t.ipid = p.ipid
                WHERE p.pid = ?
            """, (app_pid,))
            app_thread_itids = {row[0] for row in cursor.fetchall()}
            logger.debug(f'应用进程 {app_pid} 包含 {len(app_thread_itids)} 个线程')
        
        # 使用 BFS 反向搜索唤醒链（优先反向，找到谁唤醒了当前线程）
        visited = set()
        queue = deque([(start_itid, 0, frame_start)])  # (itid, depth, last_seen_ts)
        related_threads = {start_itid}
        
        logger.debug(f'开始追溯唤醒链，起始线程 itid={start_itid}，搜索时间范围: {search_start} - {search_end}')
        
        # 如果没有提供缓存，使用数据库查询（向后兼容）
        use_cache = instant_cache is not None
        
        while queue:
            current_itid, depth, current_ts = queue.popleft()
            
            if depth >= max_depth:
                logger.debug(f'达到最大深度 {max_depth}，停止搜索')
                continue
            
            if current_itid in visited:
                continue
            
            visited.add(current_itid)
            
            # 性能优化：从内存缓存中查找，而不是查询数据库
            # 优先查找应用进程的线程（除了ArkWeb，其他框架都在应用进程内开新线程）
            woken_by_results = []
            if use_cache:
                # 从缓存中查找：instant_cache[ref] = [(wakeup_from, ts), ...]
                if current_itid in instant_cache:
                    # 过滤出在时间范围内的所有事件
                    filtered = [(wf, ts) for wf, ts in instant_cache[current_itid] 
                               if search_start <= ts <= current_ts]
                    if filtered:
                        # 如果有app_pid，优先选择应用进程的线程
                        if app_pid and app_thread_itids:
                            app_thread_wakers = [(wf, ts) for wf, ts in filtered if wf in app_thread_itids]
                            if app_thread_wakers:
                                # 优先使用应用进程的线程，按时间倒序取最近的
                                app_thread_wakers.sort(key=lambda x: x[1], reverse=True)
                                woken_by_results = app_thread_wakers[:1]
                            else:
                                # 如果没有应用进程的线程，使用系统线程
                                filtered.sort(key=lambda x: x[1], reverse=True)
                                woken_by_results = filtered[:1]
                        else:
                            # 没有app_pid，只取最近的1个
                            filtered.sort(key=lambda x: x[1], reverse=True)
                            woken_by_results = filtered[:1]
            else:
                # 向后兼容：如果没有缓存，查询数据库
                cursor = trace_conn.cursor()
                if app_pid and app_thread_itids:
                    # 优先查找应用进程的线程
                    app_thread_ids_list = list(app_thread_itids)
                    placeholders = ','.join('?' * len(app_thread_ids_list))
                    woken_by_query = f"""
                    SELECT i.wakeup_from, i.ts
            FROM instant i
            WHERE i.name IN ('sched_wakeup', 'sched_waking')
                    AND i.ref = ?
                    AND i.ts >= ?
                    AND i.ts <= ?
            AND i.ref_type = 'itid'
                    AND i.wakeup_from IS NOT NULL
                    AND i.wakeup_from IN ({placeholders})
                    ORDER BY i.ts DESC
                    LIMIT 1
                    """
                    cursor.execute(woken_by_query, (current_itid, search_start, current_ts) + tuple(app_thread_ids_list))
                    woken_by_results = cursor.fetchall()
                    
                    # 如果没找到应用进程的线程，查找所有线程
                    if not woken_by_results:
                        woken_by_query = """
                        SELECT i.wakeup_from, i.ts
                        FROM instant i
                        WHERE i.name IN ('sched_wakeup', 'sched_waking')
                        AND i.ref = ?
                        AND i.ts >= ?
                        AND i.ts <= ?
                        AND i.ref_type = 'itid'
                        AND i.wakeup_from IS NOT NULL
                        ORDER BY i.ts DESC
                        LIMIT 1
                        """
                        cursor.execute(woken_by_query, (current_itid, search_start, current_ts))
                        woken_by_results = cursor.fetchall()
                else:
                    woken_by_query = """
                    SELECT i.wakeup_from, i.ts
                    FROM instant i
                    WHERE i.name IN ('sched_wakeup', 'sched_waking')
                    AND i.ref = ?
                    AND i.ts >= ?
                    AND i.ts <= ?
                    AND i.ref_type = 'itid'
                    AND i.wakeup_from IS NOT NULL
                    ORDER BY i.ts DESC
                    LIMIT 1
                    """
                    cursor.execute(woken_by_query, (current_itid, search_start, current_ts))
                    woken_by_results = cursor.fetchall()
            
            for (waker_itid, wakeup_ts) in woken_by_results:
                if waker_itid and waker_itid not in visited:
                    related_threads.add(int(waker_itid))
                    # 继续从这个唤醒时间点往前追溯
                    queue.append((int(waker_itid), depth + 1, wakeup_ts))
            
        logger.debug(f'唤醒链追溯完成，共找到 {len(related_threads)} 个相关线程')
        return related_threads
        
    except Exception as e:
        logger.error('查找唤醒链失败: %s', str(e))
        logger.error('异常堆栈跟踪:\n%s', traceback.format_exc())
        return {start_itid}  # 至少返回起始线程


# is_system_thread 和 calculate_thread_instructions 已移动到 frame_utils，直接使用导入的版本


def calculate_thread_instructions_batch(perf_conn, trace_conn, frame_data_list: List[Dict]) -> Dict[int, Tuple[Dict[int, int], Dict[int, int]]]:
    """批量计算多个帧的线程指令数（性能优化版本）
    
    收集所有帧的线程ID和时间范围，批量查询perf_sample，在内存中按帧分组计算指令数。
    这样可以大大减少数据库查询次数。
    
    Args:
        perf_conn: perf 数据库连接
        trace_conn: trace 数据库连接
        frame_data_list: 帧数据列表，每个元素包含：
            - frame_id: 帧ID
            - thread_ids: 线程ID集合
            - frame_start: 帧开始时间
            - frame_end: 帧结束时间
            
    Returns:
        {frame_id: (app_thread_instructions, system_thread_instructions)}
    """
    if not perf_conn or not trace_conn or not frame_data_list:
        return {}
    
    try:
        perf_cursor = perf_conn.cursor()
        trace_cursor = trace_conn.cursor()
        
        # 检查 perf_sample 表字段名（使用缓存，避免重复查询）
        # 如果外部传入了字段名，直接使用；否则查询一次
        if hasattr(calculate_thread_instructions, '_timestamp_field_cache'):
            timestamp_field = calculate_thread_instructions._timestamp_field_cache
        else:
            perf_cursor.execute("PRAGMA table_info(perf_sample)")
            columns = [row[1] for row in perf_cursor.fetchall()]
            timestamp_field = 'timestamp_trace' if 'timestamp_trace' in columns else 'timeStamp'
            calculate_thread_instructions._timestamp_field_cache = timestamp_field
        
        # 收集所有唯一的线程ID和时间范围
        all_thread_ids = set()
        min_time = float('inf')
        max_time = float('-inf')
        
        for frame_data in frame_data_list:
            all_thread_ids.update(frame_data['thread_ids'])
            extended_start = frame_data['frame_start'] - 1_000_000
            extended_end = frame_data['frame_end'] + 1_000_000
            min_time = min(min_time, extended_start)
            max_time = max(max_time, extended_end)
        
        if not all_thread_ids:
            return {}
        
        # 批量获取所有线程信息（一次性查询）
        thread_ids_list = list(all_thread_ids)
        placeholders = ','.join('?' * len(thread_ids_list))
        
        trace_cursor.execute(f"""
            SELECT DISTINCT t.tid, t.name as thread_name, p.name as process_name
            FROM thread t
            INNER JOIN process p ON t.ipid = p.ipid
            WHERE t.tid IN ({placeholders})
        """, thread_ids_list)
        
        thread_info_map = {}
        for tid, thread_name, process_name in trace_cursor.fetchall():
            thread_info_map[tid] = {
                'thread_name': thread_name,
                'process_name': process_name
            }
        
        # 批量查询所有帧时间范围内的perf_sample数据
        # 使用更大的时间范围，然后在内存中按帧分组
        batch_query = f"""
        SELECT 
            ps.thread_id,
            ps.{timestamp_field} as ts,
            ps.event_count
        FROM perf_sample ps
        WHERE ps.thread_id IN ({placeholders})
        AND ps.{timestamp_field} >= ? AND ps.{timestamp_field} <= ?
        """
        
        params = thread_ids_list + [min_time, max_time]
        perf_cursor.execute(batch_query, params)
        
        # 在内存中按帧分组计算指令数
        frame_results = {}
        for frame_data in frame_data_list:
            frame_id = frame_data['frame_id']
            frame_thread_ids = frame_data['thread_ids']
            extended_start = frame_data['frame_start'] - 1_000_000
            extended_end = frame_data['frame_end'] + 1_000_000
            
            # 为每个帧初始化结果字典
            app_thread_instructions = {}
            system_thread_instructions = {}
            
            # 重置游标，重新执行查询（或者使用已加载的数据）
            # 为了性能，我们重新查询该帧的时间范围（但线程ID已经批量查询了）
            frame_placeholders = ','.join('?' * len(frame_thread_ids))
            frame_thread_ids_list = list(frame_thread_ids)
            frame_query = f"""
            SELECT 
                ps.thread_id,
                SUM(ps.event_count) as total_instructions
            FROM perf_sample ps
            WHERE ps.thread_id IN ({frame_placeholders})
            AND ps.{timestamp_field} >= ? AND ps.{timestamp_field} <= ?
            GROUP BY ps.thread_id
            """
            
            frame_params = frame_thread_ids_list + [extended_start, extended_end]
            perf_cursor.execute(frame_query, frame_params)
            frame_results_db = perf_cursor.fetchall()
            
            for thread_id, instruction_count in frame_results_db:
                thread_info = thread_info_map.get(thread_id, {})
                process_name = thread_info.get('process_name')
                thread_name = thread_info.get('thread_name')
                
                if is_system_thread(process_name, thread_name):
                    system_thread_instructions[thread_id] = instruction_count
                else:
                    app_thread_instructions[thread_id] = instruction_count
            
            frame_results[frame_id] = (app_thread_instructions, system_thread_instructions)
        
        return frame_results
        
    except Exception as e:
        logger.error('批量计算线程指令数失败: %s', str(e))
        logger.error('异常堆栈跟踪:\n%s', traceback.format_exc())
        return {}


def _check_perf_sample_has_data(conn) -> bool:
    """检查 perf_sample 表是否存在且有数据（参考 detect_rn_empty_render.py）
    
    Args:
        conn: 数据库连接
        
    Returns:
        如果表存在且有数据返回 True，否则返回 False
    """
    try:
        cursor = conn.cursor()
        # 检查表是否存在
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='perf_sample'
        """)
        if not cursor.fetchone():
            return False
        
        # 检查表中是否有数据
        cursor.execute("""
            SELECT COUNT(*) FROM perf_sample
        """)
        count = cursor.fetchone()[0]
        return count > 0
    except Exception:
        return False


def map_itid_to_perf_thread_id(trace_conn, perf_conn, itids: Set[int], itid_to_tid_cache: Dict = None) -> Dict[int, int]:
    """将 trace 数据库的 itid 映射到 perf 数据库的 thread_id（参考RN实现）
    
    映射逻辑（参考RN实现）：
    1. 从 trace 数据库的 thread 表获取 tid（线程号）
    2. 直接使用 tid 作为 perf_sample.thread_id（不需要通过 perf_thread 表）
    3. perf_sample.thread_id 直接对应 trace thread.tid
    
    Args:
        trace_conn: trace 数据库连接
        perf_conn: perf 数据库连接
        itids: trace 数据库的 itid 集合
        
    Returns:
        映射字典 {itid: tid}，其中 tid 可以直接用于查询 perf_sample.thread_id
    """
    if not itids or not perf_conn:
        return {}
    
    try:
        # 性能优化：使用预加载的缓存，避免数据库查询
        itid_to_perf_thread = {}
        if itid_to_tid_cache:
            # 从缓存中查找
            for itid in itids:
                if itid in itid_to_tid_cache:
                    itid_to_perf_thread[itid] = itid_to_tid_cache[itid]
        else:
            # 向后兼容：如果没有缓存，查询数据库
            trace_cursor = trace_conn.cursor()
            itids_list = list(itids)
            placeholders = ','.join('?' * len(itids_list))
            tid_query = f"""
            SELECT t.itid, t.tid
            FROM thread t
            WHERE t.itid IN ({placeholders})
            """
            trace_cursor.execute(tid_query, itids_list)
            thread_info = trace_cursor.fetchall()
            
            # 直接使用 tid 作为 perf_sample.thread_id（参考RN实现）
            for itid, tid in thread_info:
                itid_to_perf_thread[itid] = tid
        
        return itid_to_perf_thread
        
    except Exception as e:
        logger.error('映射 itid 到 perf_thread_id 失败: %s', str(e))
        logger.error('异常堆栈跟踪:\n%s', traceback.format_exc())
        return {}


def analyze_empty_frame_wakeup_chain(trace_db_path: str, perf_db_path: str, 
                                     app_pids: List[int] = None,
                                     sample_size: int = None) -> Optional[List[Dict[str, Any]]]:
    """分析空刷帧的唤醒链和 CPU 浪费
    
    Args:
        trace_db_path: trace 数据库路径
        perf_db_path: perf 数据库路径
        app_pids: 应用进程 ID 列表（可选）
        sample_size: 随机采样的帧数（可选），如果为 None 则分析所有帧
        
    Returns:
        分析结果列表，每个元素包含：
        - frame_id: 帧 ID
        - frame_info: 帧基本信息
        - last_event: 最后事件信息
        - related_threads: 相关线程列表
        - total_wasted_instructions: 浪费的总指令数
        - thread_instructions: 每个线程的指令数
    
    注意：会过滤假阳性帧（flag=2但实际通过NativeWindow API成功提交了帧）
    """
    try:
        # 检查输入参数
        if not trace_db_path or not os.path.exists(trace_db_path):
            logger.error('Trace数据库文件不存在: %s', trace_db_path)
            return None
        
        trace_conn = sqlite3.connect(trace_db_path)
        perf_conn = None
        perf_in_trace = False  # perf_sample 是否在 trace.db 中
        
        # 处理 perf 数据库（参考 detect_rn_empty_render.py 的实现）
        if perf_db_path and os.path.exists(perf_db_path):
            # 独立的 perf.db 文件
            perf_conn = sqlite3.connect(perf_db_path)
            # 检查 perf.db 中是否有 perf_sample 表且有数据
            if not _check_perf_sample_has_data(perf_conn):
                perf_conn.close()
                perf_conn = None
                logger.warning('perf.db 文件存在但 perf_sample 表为空，将无法计算CPU指令数和占比')
        else:
            # 检查 trace.db 中是否有 perf_sample 表且有数据
            cursor = trace_conn.cursor()
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='perf_sample'
            """)
            if cursor.fetchone():
                # perf_sample 表存在，检查是否有数据
                if _check_perf_sample_has_data(trace_conn):
                    # perf_sample 在 trace.db 中且有数据，复用连接
                    perf_conn = trace_conn
                    perf_in_trace = True
                    logger.info('perf_sample 表在 trace.db 中，且包含数据')
                else:
                    # 表存在但没有数据
                    perf_conn = None
                    perf_in_trace = False
                    logger.warning('trace.db 中的 perf_sample 表为空，将无法计算CPU指令数和占比')
        
        if not perf_conn:
            logger.warning('未找到可用的 perf_sample 数据，将无法计算CPU指令数和占比')
            logger.warning('提示: 需要 perf+trace 数据才能计算CPU指令数和占比')
        
        cursor = trace_conn.cursor()
        
        # 步骤1: 找到所有 flag=2 的空刷帧
        empty_frames_query = """
        SELECT 
            fs.rowid,
            fs.ts,
            fs.dur,
            fs.itid,
            fs.callstack_id,
            fs.vsync,
            fs.flag,
            t.tid,
            t.name as thread_name,
            p.pid,
            p.name as process_name
        FROM frame_slice fs
        INNER JOIN thread t ON fs.itid = t.itid
        INNER JOIN process p ON fs.ipid = p.ipid
        WHERE fs.flag = 2
        AND fs.type = 0
        """
        
        if app_pids:
            empty_frames_query += f" AND p.pid IN ({','.join('?' * len(app_pids))})"
        
        empty_frames_query += " ORDER BY fs.ts"
        
        params = list(app_pids) if app_pids else []
        cursor.execute(empty_frames_query, params)
        empty_frames = cursor.fetchall()
        
        if not empty_frames:
            print('未找到 flag=2 的空刷帧')
            trace_conn.close()
            if perf_conn:
                perf_conn.close()
            return []
        
        print(f'找到 {len(empty_frames)} 个 flag=2 的空刷帧')

        # 重置假阳性计数器
        if hasattr(analyze_empty_frame_wakeup_chain, '_false_positive_count'):
            analyze_empty_frame_wakeup_chain._false_positive_count = 0

        # 统一过滤假阳性（在分析开始前，与update保持一致）
        # 计算所有帧的时间范围
        if empty_frames:
            min_ts = min(ts for _, ts, _, _, _, _, _, _, _, _, _ in empty_frames) - 10_000_000
            max_ts = max(ts + (dur if dur else 0) for _, ts, dur, _, _, _, _, _, _, _, _ in empty_frames) + 5_000_000
            
            # 预加载 NativeWindow API 事件
            cursor = trace_conn.cursor()
            nw_query = """
            SELECT 
                c.callid as itid,
                c.ts
            FROM callstack c
            INNER JOIN thread t ON c.callid = t.id
            INNER JOIN process p ON t.ipid = p.ipid
            WHERE c.ts >= ? AND c.ts <= ?
            AND p.name NOT IN ('render_service', 'rmrenderservice', 'ohos.sceneboard')
            AND p.name NOT LIKE 'system_%'
            AND p.name NOT LIKE 'com.ohos.%'
            AND (c.name LIKE '%RequestBuffer%' 
                 OR c.name LIKE '%FlushBuffer%' 
                 OR c.name LIKE '%DoFlushBuffer%' 
                 OR c.name LIKE '%NativeWindow%')
            """
            cursor.execute(nw_query, (min_ts, max_ts))
            nw_records = cursor.fetchall()
            
            # 构建事件缓存（按线程ID索引）
            from collections import defaultdict
            from bisect import bisect_left
            nw_events_cache = defaultdict(list)
            for itid, ts in nw_records:
                nw_events_cache[itid].append(ts)
            
            # 排序以便二分查找
            for itid in nw_events_cache:
                nw_events_cache[itid].sort()
            
            print(f'预加载NativeWindow API事件: {len(nw_records)}条记录, {len(nw_events_cache)}个线程')
            
            # 统一过滤假阳性
            filtered_empty_frames = []
            false_positive_count = 0
            for frame_data in empty_frames:
                rowid, ts, dur, itid, callstack_id, vsync, flag, tid, thread_name, pid, process_name = frame_data
                frame_start = ts
                frame_end = ts + (dur if dur else 0)  # 处理dur可能为None的情况
                
                # 检查是否为假阳性
                is_false_positive = False
                if itid in nw_events_cache:
                    event_timestamps = nw_events_cache[itid]
                    idx = bisect_left(event_timestamps, frame_start)
                    if idx < len(event_timestamps) and event_timestamps[idx] <= frame_end:
                        is_false_positive = True
                
                if is_false_positive:
                    false_positive_count += 1
                else:
                    filtered_empty_frames.append(frame_data)
            
            empty_frames = filtered_empty_frames
            total_before_filter = len(empty_frames) + false_positive_count
            false_positive_rate = (false_positive_count / total_before_filter * 100) if total_before_filter > 0 else 0
            print(f'假阳性过滤: 过滤前={total_before_filter}, 过滤后={len(empty_frames)}, 假阳性={false_positive_count} ({false_positive_rate:.1f}%)')
            
            # 更新假阳性计数器
            if hasattr(analyze_empty_frame_wakeup_chain, '_false_positive_count'):
                analyze_empty_frame_wakeup_chain._false_positive_count = false_positive_count

        # 随机采样
        if sample_size is not None and sample_size < len(empty_frames):
            empty_frames = random.sample(empty_frames, sample_size)
            print(f'随机采样 {sample_size} 个帧进行分析')
        
        results = []
        
        # 性能分析：记录各阶段耗时（保存到字典中）
        stage_timings = {
            'preload': 0.0,
            'find_last_event': 0.0,
            'find_wakeup_chain': 0.0,
            'filter_threads': 0.0,
            'map_perf_thread': 0.0,
            'calculate_instructions': 0.0,
            'build_thread_info': 0.0,
        }
        
        # 性能优化：预加载数据库表到内存
        print('\n[性能优化] 开始预加载数据库表到内存...')
        preload_start = time.time()
        
        # 计算所有帧的时间范围
        if empty_frames:
            min_ts = min(ts for _, ts, _, _, _, _, _, _, _, _, _ in empty_frames) - 10_000_000
            max_ts = max(ts + (dur if dur else 0) for _, ts, dur, _, _, _, _, _, _, _, _ in empty_frames) + 5_000_000
            
            cursor = trace_conn.cursor()
            
            # 1. 预加载 instant 表（唤醒事件）
            print(f'  [预加载] 加载 instant 表 (时间范围: {min_ts} - {max_ts})...')
            instant_query = """
            SELECT i.ref, i.wakeup_from, i.ts
            FROM instant i
            WHERE i.name IN ('sched_wakeup', 'sched_waking')
            AND i.ts >= ?
            AND i.ts <= ?
            AND i.ref_type = 'itid'
            AND i.wakeup_from IS NOT NULL
            AND i.ref IS NOT NULL
            """
            cursor.execute(instant_query, (min_ts, max_ts))
            instant_data = cursor.fetchall()
            
            # 构建 instant 缓存：按 ref 分组，存储 (wakeup_from, ts) 列表
            instant_cache = {}
            for ref, wakeup_from, ts in instant_data:
                if ref not in instant_cache:
                    instant_cache[ref] = []
                instant_cache[ref].append((wakeup_from, ts))
            
            print(f'  [预加载] instant 表: {len(instant_data)} 条记录，{len(instant_cache)} 个线程')
            
            # 2. 预加载 callstack 表（用于filter_threads和find_frame_last_event）
            print(f'  [预加载] 加载 callstack 表...')
            # 2.1: 加载所有callstack记录（用于find_frame_last_event）
            callstack_all_query = """
            SELECT c.id, c.ts, c.dur, c.name, c.callid
            FROM callstack c
            WHERE c.ts >= ?
            AND c.ts <= ?
            """
            cursor.execute(callstack_all_query, (min_ts, max_ts))
            callstack_all_data = cursor.fetchall()
            
            # 构建callstack_id缓存
            callstack_id_cache = {row[0]: row for row in callstack_all_data}
            
            # 构建callstack事件缓存：按itid分组，存储该线程的所有事件
            callstack_events_by_itid = {}
            for row in callstack_all_data:
                itid = row[4]  # callid
                if itid not in callstack_events_by_itid:
                    callstack_events_by_itid[itid] = []
                callstack_events_by_itid[itid].append(row)
            
            # 构建callstack_cache（用于filter_threads）
            callstack_cache = {callid for _, _, _, _, callid in callstack_all_data}
            print(f'  [预加载] callstack 表: {len(callstack_all_data)} 条记录，{len(callstack_cache)} 个线程，{len(callstack_id_cache)} 个callstack_id')
            
            # 3. 预加载 thread_state 表（只加载Running/Runnable状态）
            print(f'  [预加载] 加载 thread_state 表...')
            thread_state_query = """
            SELECT DISTINCT itid
            FROM thread_state
            WHERE state IN ('R', 'Runing')
            AND ts <= ?
            AND ts + dur >= ?
            """
            cursor.execute(thread_state_query, (max_ts, min_ts))
            thread_state_data = cursor.fetchall()
            thread_state_cache = {itid for (itid,) in thread_state_data}
            print(f'  [预加载] thread_state 表: {len(thread_state_cache)} 个线程')
            
            # 4. 预加载 thread 和 process 表（避免每帧都查询）
            print(f'  [预加载] 加载 thread 和 process 表...')
            thread_process_query = """
            SELECT t.itid, t.tid, t.name as thread_name, p.pid, p.name as process_name
            FROM thread t
            INNER JOIN process p ON t.ipid = p.ipid
            """
            cursor.execute(thread_process_query)
            thread_process_data = cursor.fetchall()
            
            # 构建多种索引以支持不同的查询需求
            # 1. tid -> {thread_name, process_name} (用于calculate_thread_instructions)
            tid_to_info_cache = {}
            # 2. itid -> tid (用于map_itid_to_perf_thread_id)
            itid_to_tid_cache = {}
            # 3. itid -> {tid, thread_name, pid, process_name} (用于build_thread_info)
            itid_to_full_info_cache = {}
            # 4. pid -> [(itid, tid, thread_name, process_name), ...] (用于查找进程的所有线程)
            pid_to_threads_cache = {}
            
            for itid, tid, thread_name, pid, process_name in thread_process_data:
                # tid -> {thread_name, process_name}
                tid_to_info_cache[tid] = {
                    'thread_name': thread_name,
                    'process_name': process_name
                }
                # itid -> tid
                itid_to_tid_cache[itid] = tid
                # itid -> 完整信息
                itid_to_full_info_cache[itid] = {
                    'tid': tid,
                    'thread_name': thread_name,
                    'pid': pid,
                    'process_name': process_name
                }
                # pid -> 线程列表
                if pid not in pid_to_threads_cache:
                    pid_to_threads_cache[pid] = []
                pid_to_threads_cache[pid].append({
                    'itid': itid,
                    'tid': tid,
                    'thread_name': thread_name,
                    'process_name': process_name
                })
            
            print(f'  [预加载] thread/process 表: {len(thread_process_data)} 个线程，{len(pid_to_threads_cache)} 个进程')
            
            # 5. 预加载 NativeWindow API 事件到内存（用于假阳性检测优化）
            print('  [预加载] 加载 NativeWindow API 事件...')
            nw_preload_start = time.time()
            nativewindow_events_cache = {}  # 初始化缓存字典
            
            # 查询所有应用进程的 NativeWindow API 事件
            nw_query = """
            SELECT 
                c.callid as itid,
                c.ts
            FROM callstack c
            INNER JOIN thread t ON c.callid = t.id
            INNER JOIN process p ON t.ipid = p.ipid
            WHERE c.ts >= ? AND c.ts <= ?
            AND p.name NOT IN ('render_service', 'rmrenderservice', 'ohos.sceneboard')
            AND p.name NOT LIKE 'system_%'
            AND p.name NOT LIKE 'com.ohos.%'
            AND (c.name LIKE '%RequestBuffer%' 
                 OR c.name LIKE '%FlushBuffer%' 
                 OR c.name LIKE '%DoFlushBuffer%' 
                 OR c.name LIKE '%NativeWindow%')
            """
            cursor.execute(nw_query, (min_ts, max_ts))
            nw_records = cursor.fetchall()
            
            # 构建缓存: itid -> [ts1, ts2, ...]
            for record in nw_records:
                itid, ts = record
                if itid not in nativewindow_events_cache:
                    nativewindow_events_cache[itid] = []
                nativewindow_events_cache[itid].append(ts)
            
            nw_preload_elapsed = time.time() - nw_preload_start
            print(f'  [预加载] NativeWindow API 事件: {len(nw_records)} 条记录，{len(nativewindow_events_cache)} 个线程')
            print(f'  [预加载] NativeWindow API 加载耗时: {nw_preload_elapsed:.3f}秒')
            
            preload_elapsed = time.time() - preload_start
            stage_timings['preload'] = preload_elapsed
            print(f'[性能优化] 预加载完成，耗时: {preload_elapsed:.3f}秒\n')
        else:
            instant_cache = {}
            callstack_cache = set()
            callstack_id_cache = {}
            callstack_events_by_itid = {}
            thread_state_cache = set()
            tid_to_info_cache = {}
            itid_to_tid_cache = {}
            itid_to_full_info_cache = {}
            pid_to_threads_cache = {}
            nativewindow_events_cache = {}  # 初始化NativeWindow缓存
        
        # 性能优化：缓存perf_sample表的字段名（避免每帧都查询）
        perf_timestamp_field = None
        if perf_conn:
            try:
                perf_cursor_temp = perf_conn.cursor()
                perf_cursor_temp.execute("PRAGMA table_info(perf_sample)")
                columns = [row[1] for row in perf_cursor_temp.fetchall()]
                perf_timestamp_field = 'timestamp_trace' if 'timestamp_trace' in columns else 'timeStamp'
                perf_cursor_temp.close()
            except Exception as e:
                logger.warning('无法获取perf_sample表字段名: %s', str(e))
        
        # 性能优化：预加载 perf_sample 表数据（如果perf_conn存在）
        perf_sample_cache = {}  # thread_id -> [(timestamp, event_count), ...]
        if perf_conn and empty_frames and perf_timestamp_field:
            print(f'  [预加载] 加载 perf_sample 表...')
            preload_perf_start = time.time()
            
            # 计算所有帧的时间范围（扩展1ms以包含时间戳对齐问题）
            min_ts = min(ts for _, ts, _, _, _, _, _, _, _, _, _ in empty_frames) - 1_000_000
            max_ts = max(ts + (dur if dur else 0) for _, ts, dur, _, _, _, _, _, _, _, _ in empty_frames) + 1_000_000
            
            # 先快速遍历所有帧，收集所有可能的线程ID（通过itid_to_tid_cache）
            # 由于我们还没有完成唤醒链查找，先收集所有线程的tid
            all_possible_tids = set(itid_to_tid_cache.values()) if itid_to_tid_cache else set()
            
            if all_possible_tids:
                # 一次性查询所有时间范围内的perf_sample数据
                perf_cursor = perf_conn.cursor()
                tid_list = list(all_possible_tids)
                placeholders = ','.join('?' * len(tid_list))
                
                perf_query = f"""
                SELECT ps.thread_id, ps.{perf_timestamp_field} as ts, ps.event_count
                FROM perf_sample ps
                WHERE ps.thread_id IN ({placeholders})
                AND ps.{perf_timestamp_field} >= ? AND ps.{perf_timestamp_field} <= ?
                """
                
                perf_cursor.execute(perf_query, tid_list + [min_ts, max_ts])
                perf_data = perf_cursor.fetchall()
                
                # 构建缓存：按thread_id分组，存储(timestamp, event_count)列表
                for thread_id, ts, event_count in perf_data:
                    if thread_id not in perf_sample_cache:
                        perf_sample_cache[thread_id] = []
                    perf_sample_cache[thread_id].append((ts, event_count))
                
                # 按timestamp排序，便于后续范围查询
                for thread_id in perf_sample_cache:
                    perf_sample_cache[thread_id].sort(key=lambda x: x[0])
                
                print(f'  [预加载] perf_sample 表: {len(perf_data)} 条记录，{len(perf_sample_cache)} 个线程')
                preload_perf_elapsed = time.time() - preload_perf_start
                print(f'  [预加载] perf_sample 加载耗时: {preload_perf_elapsed:.3f}秒')
            else:
                print(f'  [预加载] perf_sample 表: 无可用线程ID，跳过')
        
        # 步骤2: 对每个空刷帧进行分析
        for frame_row in empty_frames:
            frame_id, ts, dur, itid, callstack_id, vsync, flag, tid, thread_name, pid, process_name = frame_row
            
            frame_info = {
                'frame_id': frame_id,
                'ts': ts,
                'dur': dur if dur else 0,
                'itid': itid,
                'callstack_id': callstack_id,
                'vsync': vsync,
                'flag': flag,
                'tid': tid,
                'thread_name': thread_name,
                'pid': pid,
                'process_name': process_name
            }
            
            frame_start = ts
            frame_end = ts + (dur if dur else 0)
            
            # 步骤2.1: 找到帧的最后事件（计时，使用缓存）
            stage_start = time.time()
            frame_itid = frame_info['itid']
            # 从缓存中查找该线程在帧时间范围内的最后一个事件
            last_event = None
            if frame_info.get('callstack_id') and frame_info['callstack_id'] in callstack_id_cache:
                # 使用callstack_id缓存
                result = callstack_id_cache[frame_info['callstack_id']]
                last_event = {
                    'id': result[0],
                    'ts': result[1],
                    'dur': result[2] if result[2] else 0,
                    'name': result[3],
                    'callid': result[4],
                    'itid': result[4]
                }
            elif frame_itid in callstack_events_by_itid:
                # 从该线程的事件中查找帧时间范围内的最后一个
                events = callstack_events_by_itid[frame_itid]
                filtered = [(row[0], row[1], row[2], row[3], row[4]) for row in events 
                           if frame_start <= row[1] <= frame_end]
                if filtered:
                    result = max(filtered, key=lambda x: x[1])  # 按ts排序，取最后一个
                    last_event = {
                        'id': result[0],
                        'ts': result[1],
                        'dur': result[2] if result[2] else 0,
                        'name': result[3],
                        'callid': result[4],
                        'itid': result[4]
                    }
            
            # 如果缓存中没有找到，使用原函数（向后兼容）
            if not last_event:
                last_event = find_frame_last_event(trace_conn, frame_info, 
                                                  callstack_id_cache=callstack_id_cache,
                                                  callstack_events_cache=None)
            
            elapsed = time.time() - stage_start
            stage_timings['find_last_event'] += elapsed
            # 只在debug模式下输出每个帧的详细耗时
            logger.debug(f'  [帧{frame_id}] find_last_event: {elapsed:.3f}秒')
            
            # 步骤2.2: 找到唤醒链（所有相关的线程）（计时，使用缓存）
            # 优先查找应用进程内的线程（除了ArkWeb，其他框架都在应用进程内开新线程）
            stage_start = time.time()
            
            # 处理last_event：如果找不到，使用帧所在线程的itid作为起始点
            if not last_event:
                logger.warning('帧 %d 未找到最后事件，使用帧所在线程itid作为起始点', frame_id)
                start_itid = itid  # 使用帧所在线程的itid
            else:
                start_itid = last_event.get('itid') or last_event.get('callid') or itid
            # 获取应用进程PID（如果帧所在进程是应用进程）
            app_pid = None
            if not is_system_thread(frame_info.get('process_name'), frame_info.get('thread_name')):
                app_pid = frame_info.get('pid')
            elif frame_info.get('pid'):
                # 即使帧在系统线程，也尝试查找应用进程（通过进程名判断）
                # 例如：com.qunar.hos的OS_VSyncThread，应用进程就是com.qunar.hos
                app_pid = frame_info.get('pid')
            
            related_itids = find_wakeup_chain(trace_conn, start_itid, frame_start, frame_end, 
                                             instant_cache=instant_cache, app_pid=app_pid)
            elapsed = time.time() - stage_start
            stage_timings['find_wakeup_chain'] += elapsed
            logger.debug(f'  [帧{frame_id}] find_wakeup_chain: {elapsed:.3f}秒 (找到{len(related_itids)}个线程)')
            
            logger.debug('帧 %d: 找到 %d 个相关线程（唤醒链）', frame_id, len(related_itids))
            
            # 步骤2.2.1: 过滤出在帧时间范围内实际在CPU上执行过的线程（计时，使用缓存）
            stage_start = time.time()
            executed_itids = filter_threads_executed_in_frame(trace_conn, related_itids, frame_start, frame_end,
                                                             callstack_cache=callstack_cache,
                                                             thread_state_cache=thread_state_cache)
            elapsed = time.time() - stage_start
            stage_timings['filter_threads'] += elapsed
            logger.debug(f'  [帧{frame_id}] filter_threads: {elapsed:.3f}秒 (过滤后{len(executed_itids)}个线程)')
            
            # 确保起始线程包含在内（即使没有执行记录，因为它是帧的入口）
            executed_itids.add(start_itid)
            
            # 特殊处理：对于应用进程，总是查找应用进程内的所有线程（包括主线程、RNOH_JS等）
            # 参考RN实现：对于空刷帧，应该查找应用进程内的所有线程（包括主线程、RNOH_JS等）
            # 即使唤醒链中已经找到了应用进程的线程，也要确保包含所有应用线程（如RNOH_JS）
            # 对于ArkWeb，还需要查找对应的render进程（如com.jd.hm.mall -> com.jd.hm.mall:render）
            if app_pid:
                # 性能优化：使用预加载的缓存查找应用进程的线程
                if pid_to_threads_cache and app_pid in pid_to_threads_cache:
                    # 从缓存中查找应用进程的所有线程
                    app_threads = pid_to_threads_cache[app_pid]
                    # 检查当前executed_itids中是否有应用进程的线程
                    app_threads_in_chain = {t['itid'] for t in app_threads if t['itid'] in executed_itids}
                    
                    # 总是查找应用进程内的所有线程（包括RNOH_JS），确保不遗漏
                    logger.debug('帧 %d: 查找应用进程 %d 的所有线程（包括RNOH_JS）', frame_id, app_pid)
                    for thread_info in app_threads:
                        app_itid = thread_info['itid']
                        app_tid = thread_info['tid']
                        app_thread_name = thread_info['thread_name']
                        app_process_name = thread_info['process_name']
                        if not is_system_thread(app_process_name, app_thread_name):
                            executed_itids.add(app_itid)
                            if app_thread_name == 'RNOH_JS':
                                logger.debug('帧 %d: 找到RNOH_JS线程 (itid=%d, tid=%d)', frame_id, app_itid, app_tid)
                            else:
                                logger.debug('帧 %d: 找到应用进程线程 %s (itid=%d)', frame_id, app_thread_name, app_itid)
                else:
                    # 向后兼容：如果没有缓存，查询数据库
                    cursor.execute("""
                        SELECT t.itid
                        FROM thread t
                        INNER JOIN process p ON t.ipid = p.ipid
                        WHERE t.itid IN ({})
                        AND p.pid = ?
                    """.format(','.join('?' * len(executed_itids))), list(executed_itids) + [app_pid])
                    app_threads_in_chain = {row[0] for row in cursor.fetchall()}
                    
                    # 总是查找应用进程内的所有线程（包括RNOH_JS），确保不遗漏
                    logger.debug('帧 %d: 查找应用进程 %d 的所有线程（包括RNOH_JS）', frame_id, app_pid)
                    cursor.execute("""
                        SELECT t.itid, t.tid, t.name, p.pid, p.name
                        FROM thread t
                        INNER JOIN process p ON t.ipid = p.ipid
                        WHERE p.pid = ?
                        AND t.name NOT LIKE 'OS_%'
                        AND t.name NOT LIKE 'ohos.%'
                        AND t.name NOT LIKE 'pp.%'
                    """, (app_pid,))
                    app_threads = cursor.fetchall()
                    for app_itid, app_tid, app_thread_name, app_pid_val, app_process_name in app_threads:
                        if not is_system_thread(app_process_name, app_thread_name):
                            executed_itids.add(app_itid)
                            if app_thread_name == 'RNOH_JS':
                                logger.debug('帧 %d: 找到RNOH_JS线程 (itid=%d, tid=%d)', frame_id, app_itid, app_tid)
                            else:
                                logger.debug('帧 %d: 找到应用进程线程 %s (itid=%d)', frame_id, app_thread_name, app_itid)
                
                # 特殊处理：对于ArkWeb，查找对应的render进程
                # ArkWeb使用多进程架构：主进程（如com.jd.hm.mall）和render进程（如.hm.mall:render或com.jd.hm.mall:render）
                app_process_name = frame_info.get('process_name', '')
                if app_process_name and '.' in app_process_name:
                    # 查找所有包含":render"的进程（ArkWeb的render进程通常以":render"结尾）
                    # 例如：.hm.mall:render, com.jd.hm.mall:render等
                    cursor.execute("""
                        SELECT DISTINCT p.pid, p.name
                        FROM process p
                        WHERE p.name LIKE '%:render'
                        OR (p.name LIKE '%render%' AND p.name != 'render_service' AND p.name != 'rmrenderservice')
                    """)
                    all_render_processes = cursor.fetchall()
                    
                    # 尝试匹配与主进程相关的render进程
                    # 可能的匹配模式：
                    # 1. com.jd.hm.mall -> com.jd.hm.mall:render
                    # 2. com.jd.hm.mall -> .hm.mall:render (去掉com前缀)
                    # 3. com.jd.hm.mall -> hm.mall:render
                    matched_render_processes = []
                    for render_pid, render_process_name in all_render_processes:
                        # 提取主进程名的关键部分（去掉com.前缀）
                        main_key = app_process_name.split('.', 1)[-1] if '.' in app_process_name else app_process_name
                        # 检查render进程名是否包含主进程的关键部分
                        if main_key in render_process_name or app_process_name.split('.')[-1] in render_process_name:
                            matched_render_processes.append((render_pid, render_process_name))
                    
                    # 如果没找到精确匹配，查找所有以":render"结尾的进程（可能是共享的render进程）
                    if not matched_render_processes:
                        cursor.execute("""
                            SELECT DISTINCT p.pid, p.name
                            FROM process p
                            WHERE p.name LIKE '%:render'
                        """)
                        matched_render_processes = cursor.fetchall()
                    
                    for render_pid, render_process_name in matched_render_processes:
                        logger.info('帧 %d: 找到ArkWeb render进程 %s (PID=%d)', frame_id, render_process_name, render_pid)
                        # 查找render进程的所有线程
                        cursor.execute("""
                            SELECT t.itid, t.tid, t.name, p.pid, p.name
                            FROM thread t
                            INNER JOIN process p ON t.ipid = p.ipid
                            WHERE p.pid = ?
                            AND t.name NOT LIKE 'OS_%'
                            AND t.name NOT LIKE 'ohos.%'
                            AND t.name NOT LIKE 'pp.%'
                        """, (render_pid,))
                        render_threads = cursor.fetchall()
                        for render_itid, render_tid, render_thread_name, render_pid_val, render_proc_name in render_threads:
                            if not is_system_thread(render_proc_name, render_thread_name):
                                executed_itids.add(render_itid)
                                logger.info('帧 %d: 找到render进程线程 %s (itid=%d, pid=%d, process=%s)', 
                                          frame_id, render_thread_name, render_itid, render_pid, render_proc_name)
            
            logger.debug('帧 %d: 其中 %d 个线程在帧时间范围内实际执行过', frame_id, len(executed_itids))
            
            # 使用执行过的线程集合
            related_itids = executed_itids
            
            # 步骤2.3: 将 itid 映射到 perf_thread_id（计时）
            stage_start = time.time()
            itid_to_perf_thread = {}
            if perf_conn:
                itid_to_perf_thread = map_itid_to_perf_thread_id(trace_conn, perf_conn, related_itids, itid_to_tid_cache)
            elapsed = time.time() - stage_start
            stage_timings['map_perf_thread'] += elapsed
            logger.debug(f'  [帧{frame_id}] map_perf_thread: {elapsed:.3f}秒 (映射{len(itid_to_perf_thread)}个线程)')
            
            # 步骤2.4: 计算进程级 CPU 指令数（新方法：使用进程级统计，与update命令保持一致）
            stage_start = time.time()
            app_thread_instructions = {}
            system_thread_instructions = {}
            total_wasted_instructions = 0  # 包括所有线程（应用+系统）的指令数
            total_system_instructions = 0
            
            # 获取应用进程PID（优先使用已获取的app_pid）
            app_pid_for_cpu = app_pid
            if not app_pid_for_cpu and frame_info.get('pid'):
                app_pid_for_cpu = frame_info.get('pid')
            
            # 使用进程级CPU统计（与update命令保持一致）
            if perf_conn and trace_conn and app_pid_for_cpu:
                try:
                    app_instructions, sys_instructions = calculate_process_instructions(
                        perf_conn=perf_conn,
                        trace_conn=trace_conn,
                        app_pid=app_pid_for_cpu,
                        frame_start=frame_start,
                        frame_end=frame_end,
                        perf_sample_cache=perf_sample_cache,
                        perf_timestamp_field=perf_timestamp_field,
                        tid_to_info_cache=tid_to_info_cache
                    )
                    total_wasted_instructions = app_instructions + sys_instructions
                    total_system_instructions = sys_instructions
                    # 为了兼容性，构建空的字典（唤醒链分析仍然用于related_threads）
                    app_thread_instructions = {}
                    system_thread_instructions = {}
                    logger.debug(f'  [帧{frame_id}] 进程级CPU统计: {total_wasted_instructions:,} 指令 (进程PID={app_pid_for_cpu})')
                except Exception as e:
                    logger.warning(f'  [帧{frame_id}] 进程级CPU计算失败，回退到唤醒链方式: {e}')
                    # 回退到原来的唤醒链方式
                    perf_thread_ids = set(itid_to_perf_thread.values())
                    if perf_thread_ids:
                        app_thread_instructions, system_thread_instructions = calculate_thread_instructions(
                            perf_conn, trace_conn, perf_thread_ids, frame_start, frame_end, 
                            tid_to_info_cache, perf_sample_cache, perf_timestamp_field
                        )
                        total_wasted_instructions = sum(app_thread_instructions.values()) + sum(system_thread_instructions.values())
                        total_system_instructions = sum(system_thread_instructions.values())
            else:
                # 向后兼容：如果没有app_pid，使用原来的唤醒链方式
                perf_thread_ids = set(itid_to_perf_thread.values())
                if perf_conn and perf_thread_ids:
                    app_thread_instructions, system_thread_instructions = calculate_thread_instructions(
                        perf_conn, trace_conn, perf_thread_ids, frame_start, frame_end, 
                        tid_to_info_cache, perf_sample_cache, perf_timestamp_field
                    )
                    total_wasted_instructions = sum(app_thread_instructions.values()) + sum(system_thread_instructions.values())
                    total_system_instructions = sum(system_thread_instructions.values())
            
            elapsed = time.time() - stage_start
            stage_timings['calculate_instructions'] += elapsed
            logger.debug(f'  [帧{frame_id}] calculate_instructions: {elapsed:.3f}秒')
            
            # 步骤2.5: 构建线程详细信息（使用预加载缓存）（计时）
            stage_start = time.time()
            related_threads_info = []
            if related_itids:
                # 性能优化：使用预加载的缓存，避免数据库查询
                thread_info_map = {}
                if itid_to_full_info_cache:
                    # 从缓存中查找
                    for itid in related_itids:
                        if itid in itid_to_full_info_cache:
                            thread_info_map[itid] = itid_to_full_info_cache[itid]
                else:
                    # 向后兼容：如果没有缓存，查询数据库
                    itids_list = list(related_itids)
                    placeholders = ','.join('?' * len(itids_list))
                    batch_thread_info_query = f"""
                    SELECT t.itid, t.tid, t.name, p.pid, p.name
                    FROM thread t
                    INNER JOIN process p ON t.ipid = p.ipid
                    WHERE t.itid IN ({placeholders})
                    """
                    cursor.execute(batch_thread_info_query, itids_list)
                    thread_results = cursor.fetchall()
                    
                    for itid, tid, thread_name, pid, process_name in thread_results:
                        thread_info_map[itid] = {
                            'tid': tid,
                            'thread_name': thread_name,
                            'pid': pid,
                            'process_name': process_name
                        }
                
                # 构建线程详细信息列表
                for itid in related_itids:
                    thread_info = thread_info_map.get(itid)
                    if thread_info:
                        # 优先使用itid_to_perf_thread映射，如果没有则直接使用thread_info中的tid
                        perf_thread_id = itid_to_perf_thread.get(itid)
                        if perf_thread_id is None:
                            # 如果映射中没有，直接使用thread_info中的tid（因为tid就是perf_sample.thread_id）
                            perf_thread_id = thread_info.get('tid')
                        
                        process_name = thread_info['process_name']
                        thread_name = thread_info['thread_name']
                        
                        # 判断是否为系统线程
                        is_system = is_system_thread(process_name, thread_name)
                        
                        # 根据线程类型获取指令数
                        # 注意：如果使用进程级CPU统计，app_thread_instructions和system_thread_instructions为空
                        # 此时instruction_count为0，但total_wasted_instructions已经包含了所有线程的CPU
                        instruction_count = 0
                        if perf_thread_id:
                            # 先尝试从应用线程字典查找（如果使用唤醒链方式）
                            if perf_thread_id in app_thread_instructions:
                                instruction_count = app_thread_instructions[perf_thread_id]
                            # 再尝试从系统线程字典查找（如果使用唤醒链方式）
                            elif perf_thread_id in system_thread_instructions:
                                instruction_count = system_thread_instructions[perf_thread_id]
                            # 如果使用进程级统计，app_thread_instructions和system_thread_instructions为空
                            # 此时instruction_count为0，这是正常的，因为CPU已经包含在total_wasted_instructions中
                            # 如果需要显示每个线程的CPU，需要额外查询（但为了性能，这里不查询）
                        else:
                            # perf_thread_id为None，说明该线程在trace数据库中没有对应的tid
                            # 这可能是数据问题，但指令数确实为0
                            logger.debug(f'线程 {thread_name} (itid={itid}) 没有找到perf_thread_id，指令数为0')
                    
                    related_threads_info.append({
                        'itid': itid,
                            'tid': thread_info['tid'],
                            'thread_name': thread_name,
                            'pid': thread_info['pid'],
                            'process_name': process_name,
                        'perf_thread_id': perf_thread_id,
                            'instruction_count': instruction_count,
                        'is_system_thread': is_system
                    })
            elapsed = time.time() - stage_start
            stage_timings['build_thread_info'] += elapsed
            logger.debug(f'  [帧{frame_id}] build_thread_info: {elapsed:.3f}秒 (构建{len(related_threads_info)}个线程信息)')
            
            # 为每帧计算Top 5浪费线程（按指令数排序，便于开发者快速定位问题）
            top_5_threads = []
            if related_threads_info:
                # 按指令数排序，取前5个
                sorted_threads = sorted(related_threads_info, 
                                      key=lambda x: x.get('instruction_count', 0), 
                                      reverse=True)
                top_5_threads = sorted_threads[:5]
                # 只保留关键信息，减少数据量
                top_5_threads = [
                    {
                        'process_name': t.get('process_name', 'N/A'),
                        'thread_name': t.get('thread_name', 'N/A'),
                        'pid': t.get('pid', 'N/A'),
                        'tid': t.get('tid', 'N/A'),
                        'instruction_count': t.get('instruction_count', 0),
                        'is_system_thread': t.get('is_system_thread', False),
                        'percentage': (t.get('instruction_count', 0) / total_wasted_instructions * 100) if total_wasted_instructions > 0 else 0
                    }
                    for t in top_5_threads
                ]
            
            # 注意：假阳性已经在加载空刷帧后统一过滤了，这里不再需要检查
            # 所有到达这里的帧都是真阳性（真正的空刷帧）
            results.append({
                'frame_id': frame_id,
                'frame_info': frame_info,
                'last_event': last_event,
                'related_threads': related_threads_info,
                'top_5_waste_threads': top_5_threads,  # 新增：Top 5浪费线程（便于开发者快速定位问题）
                'total_wasted_instructions': total_wasted_instructions,  # 只包含应用线程
                'total_system_instructions': total_system_instructions,  # 系统线程指令数（用于统计）
                'app_thread_instructions': app_thread_instructions,
                'system_thread_instructions': system_thread_instructions
            })
        
        # 输出假阳性统计
        false_positive_count = getattr(analyze_empty_frame_wakeup_chain, '_false_positive_count', 0)
        if false_positive_count > 0:
            logger.info('过滤了 %d 个假阳性帧（flag=2但通过NativeWindow API成功提交了帧）', false_positive_count)
        
        # 计算总event_count（从perf_sample表中SUM所有event_count）作为分母
        total_event_count = 0
        if perf_conn:
            try:
                perf_cursor = perf_conn.cursor()
                perf_cursor.execute("SELECT SUM(event_count) FROM perf_sample")
                result = perf_cursor.fetchone()
                if result and result[0] is not None:
                    total_event_count = result[0]
                    logger.info('perf_sample表总event_count: %d', total_event_count)
                else:
                    logger.warning('无法获取perf_sample表总event_count，可能表为空')
            except Exception as e:
                logger.warning('查询perf_sample表总event_count失败: %s', str(e))
        
        # 计算总浪费指令数和占比
        total_wasted_instructions = sum(r['total_wasted_instructions'] for r in results)
        wasted_instruction_percentage = 0.0
        if total_event_count > 0:
            wasted_instruction_percentage = (total_wasted_instructions / total_event_count) * 100
            logger.info('总浪费指令数: %d, 总event_count: %d, 占比: %.4f%%', 
                       total_wasted_instructions, total_event_count, wasted_instruction_percentage)
        
        # 将总event_count和占比添加到每个结果中（用于后续报告）
        for result in results:
            result['total_event_count'] = total_event_count
            result['wasted_instruction_percentage'] = wasted_instruction_percentage
        
        trace_conn.close()
        # 如果 perf_conn 和 trace_conn 是同一个，不要重复关闭
        # perf_in_trace 在函数开始处定义，如果 perf_conn == trace_conn，说明是同一个连接
        if perf_conn and perf_conn != trace_conn:
            perf_conn.close()
        
        # 按浪费的指令数排序
        results.sort(key=lambda x: x['total_wasted_instructions'], reverse=True)
        
        # 打印性能分析结果（直接输出到控制台）
        total_time = sum(stage_timings.values())
        print('\n' + '='*80)
        print('性能分析 - 各阶段耗时汇总:')
        print('='*80)
        for stage_name, stage_time in sorted(stage_timings.items(), key=lambda x: x[1], reverse=True):
            percentage = (stage_time / total_time * 100) if total_time > 0 else 0
            print(f'  {stage_name:<25s}: {stage_time:>8.3f}秒 ({percentage:>5.1f}%)')
        print(f'  {"总计":<25s}: {total_time:>8.3f}秒 (100.0%)')
        print('='*80 + '\n')
        
        # 同时记录到日志
        logger.info('='*80)
        logger.info('性能分析 - 各阶段耗时:')
        logger.info('='*80)
        for stage_name, stage_time in sorted(stage_timings.items(), key=lambda x: x[1], reverse=True):
            percentage = (stage_time / total_time * 100) if total_time > 0 else 0
            logger.info('  %-25s: %.2f秒 (%.1f%%)', stage_name, stage_time, percentage)
        logger.info('  %-25s: %.2f秒 (100.0%%)', '总计', total_time)
        logger.info('='*80)
        
        logger.info('分析完成: 共分析 %d 个空刷帧', len(results))
        
        return results
        
    except Exception as e:
        logger.error('分析空刷帧唤醒链失败: %s', str(e))
        logger.error('异常堆栈跟踪:\n%s', traceback.format_exc())
        return None


def print_results(results: List[Dict[str, Any]], top_n: int = 10, framework_name: str = ""):
    """打印分析结果
    
    Args:
        results: 分析结果列表
        top_n: 打印前 N 个结果
        framework_name: 框架名称（用于标题）
    """
    if not results:
        print('未找到空刷帧或分析失败')
        return
    
    print('\n' + '='*80)
    print(f'应用层空刷帧唤醒链分析报告 - {framework_name}')
    print('='*80 + '\n')
    
    print(f'共分析 {len(results)} 个空刷帧\n')
    
    # 计算并显示总浪费指令占比
    if results:
        total_wasted = sum(r['total_wasted_instructions'] for r in results)
        total_event_count = results[0].get('total_event_count', 0)
        wasted_percentage = results[0].get('wasted_instruction_percentage', 0.0)
        
        if total_event_count > 0:
            print(f'总浪费指令数: {total_wasted:,}')
            print(f'perf_sample表总event_count: {total_event_count:,}')
            print(f'浪费指令占比: {wasted_percentage:.4f}%\n')
        else:
            print(f'总浪费指令数: {total_wasted:,}')
            print(f'⚠️  无法计算占比（perf数据库不可用或表为空）\n')
    
    # 打印前 N 个结果
    print(f'前 {min(top_n, len(results))} 个结果（按浪费的 CPU 指令数排序）:')
    print('-'*80)
    
    for idx, result in enumerate(results[:top_n], 1):
        frame_info = result['frame_info']
        last_event = result['last_event']
        related_threads = result['related_threads']
        total_instructions = result['total_wasted_instructions']
        
        print(f'\n[{idx}] 帧 ID: {result["frame_id"]}')
        print(f'    进程: {frame_info["process_name"]} (PID: {frame_info["pid"]})')
        print(f'    主线程: {frame_info["thread_name"]} (TID: {frame_info["tid"]}, ITID: {frame_info["itid"]})')
        print(f'    时间: {frame_info["ts"]} - {frame_info["ts"] + frame_info["dur"]} '
              f'(持续 {frame_info["dur"]/1_000_000:.2f}ms)')
        print(f'    VSync: {frame_info.get("vsync", "N/A")}')
        print(f'    最后事件: {last_event.get("name", "N/A")} (ts: {last_event.get("ts", "N/A")})')
        print(f'    相关线程数: {len(related_threads)}')
        print(f'    浪费的 CPU 指令数（所有线程）: {total_instructions:,}')
        if result.get('total_system_instructions', 0) > 0:
            print(f'    系统线程 CPU 指令数: {result.get("total_system_instructions", 0):,}')
        
        # 优先显示Top 5浪费线程（便于开发者快速定位问题）
        top_5_threads = result.get('top_5_waste_threads', [])
        if top_5_threads:
            print(f'\n    Top 5 浪费线程（按CPU指令数排序，便于调试）:')
            print(f'    {"序号":<6} {"类型":<8} {"进程名":<25} {"线程名":<30} {"指令数":<15} {"占比":<10}')
            print(f'    {"-"*100}')
            for idx, thread in enumerate(top_5_threads, 1):
                thread_type = "系统" if thread.get('is_system_thread', False) else "应用"
                process_name = (thread.get('process_name', 'N/A') or 'N/A')[:24]
                thread_name = (thread.get('thread_name', 'N/A') or 'N/A')[:29]
                instruction_count = thread.get('instruction_count', 0)
                percentage = thread.get('percentage', 0)
                print(f'    {idx:<6} {thread_type:<8} {process_name:<25} {thread_name:<30} {instruction_count:<15,} {percentage:>6.2f}%')
        
        if related_threads:
            print(f'\n    相关线程列表（供人工验证）:')
            print(f'    {"序号":<6} {"类型":<8} {"进程名":<25} {"PID":<8} {"线程名":<30} {"TID":<8} {"ITID":<8} {"指令数":<15}')
            print(f'    {"-"*110}')
            for thread_idx, thread_info in enumerate(related_threads, 1):
                process_name = (thread_info.get("process_name") or "N/A")[:24]
                thread_name = (thread_info.get("thread_name") or "N/A")[:29]
                pid = thread_info.get("pid", "N/A")
                tid = thread_info.get("tid", "N/A")
                itid = thread_info.get("itid", "N/A")
                instruction_count = thread_info.get("instruction_count", 0)
                is_system = thread_info.get("is_system_thread", False)
                thread_type = "系统" if is_system else "应用"
                
                print(f'    {thread_idx:<6} {thread_type:<8} {process_name:<25} {pid:<8} {thread_name:<30} {tid:<8} {itid:<8} {instruction_count:<15,}')
        else:
            print(f'    注意: 未找到相关线程（可能是 instant 表不存在或唤醒链为空）')
    
    print('\n' + '-'*80)
    
    # 统计信息
    total_frames = len(results)
    total_instructions = sum(r['total_wasted_instructions'] for r in results)
    total_system_instructions = sum(r.get('total_system_instructions', 0) for r in results)
    avg_instructions = total_instructions / total_frames if total_frames > 0 else 0
    max_instructions = max((r['total_wasted_instructions'] for r in results), default=0)
    
    # 统计所有涉及的线程
    all_threads = {}
    for result in results:
        for thread_info in result['related_threads']:
            thread_key = (thread_info.get('pid'), thread_info.get('tid'), thread_info.get('thread_name'))
            if thread_key not in all_threads:
                all_threads[thread_key] = {
                    'process_name': thread_info.get('process_name'),
                    'pid': thread_info.get('pid'),
                    'thread_name': thread_info.get('thread_name'),
                    'tid': thread_info.get('tid'),
                    'itid': thread_info.get('itid'),
                    'appear_count': 0,
                    'total_instructions': 0
                }
            all_threads[thread_key]['appear_count'] += 1
            all_threads[thread_key]['total_instructions'] += thread_info.get('instruction_count', 0)
    
    print(f'\n统计信息:')
    print(f'  - 总空刷帧数: {total_frames}')
    print(f'  - 总浪费指令数（应用线程）: {total_instructions:,}')
    if total_system_instructions > 0:
        print(f'  - 系统线程指令数（统计用）: {total_system_instructions:,}')
    print(f'  - 平均每帧浪费指令数（应用线程）: {avg_instructions:,.0f}')
    print(f'  - 单帧最大浪费指令数（应用线程）: {max_instructions:,}')
    print(f'  - 涉及的唯一线程数: {len(all_threads)}')
    
    if all_threads:
        print(f'\n所有涉及的线程汇总（按出现次数排序）:')
        print(f'{"序号":<6} {"类型":<8} {"进程名":<25} {"PID":<8} {"线程名":<30} {"TID":<8} {"ITID":<8} {"出现次数":<12} {"总指令数":<15}')
        print(f'{"-"*130}')
        sorted_threads = sorted(all_threads.items(), key=lambda x: x[1]['appear_count'], reverse=True)
        for thread_idx, (key, thread_data) in enumerate(sorted_threads, 1):
            process_name = (thread_data['process_name'] or "N/A")[:24]
            thread_name = (thread_data['thread_name'] or "N/A")[:29]
            is_system = is_system_thread(thread_data.get('process_name'), thread_data.get('thread_name'))
            thread_type = "系统" if is_system else "应用"
            print(f'{thread_idx:<6} {thread_type:<8} {process_name:<25} {thread_data["pid"]:<8} {thread_name:<30} '
                  f'{thread_data["tid"]:<8} {thread_data["itid"]:<8} {thread_data["appear_count"]:<12} '
                  f'{thread_data["total_instructions"]:<15,}')
    print()


def main():
    """主函数"""
    if len(sys.argv) < 3:
        print('使用方法: python app_empty_frame_wakeup_chain.py <trace_db_path> <perf_db_path> [app_pids...] [framework_name]')
        print('示例: python app_empty_frame_wakeup_chain.py trace.db perf.db 12345 12346 Flutter')
        sys.exit(1)
    
    trace_db_path = sys.argv[1]
    perf_db_path = sys.argv[2]
    
    # 解析参数：app_pids 和 framework_name
    app_pids = None
    framework_name = ""
    
    if len(sys.argv) > 3:
        # 尝试解析为 PID 或框架名称
        remaining_args = sys.argv[3:]
        pids = []
        for arg in remaining_args:
            try:
                pids.append(int(arg))
            except ValueError:
                framework_name = arg
        if pids:
            app_pids = pids
    
    # 执行分析
    results = analyze_empty_frame_wakeup_chain(trace_db_path, perf_db_path, app_pids)
    
    if results is None:
        print('分析失败，请检查日志')
        sys.exit(1)
    
    # 打印结果
    print_results(results, top_n=10, framework_name=framework_name)
    
    # 保存结果到 JSON 文件
    output_file = os.path.join(os.path.dirname(__file__), f'app_empty_frame_wakeup_chain_results_{framework_name.lower() if framework_name else "all"}.json')
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f'结果已保存到: {output_file}')


if __name__ == '__main__':
    main()

