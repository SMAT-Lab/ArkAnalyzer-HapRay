#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RS系统API流程：从RS skip帧追溯到应用进程提交的帧

支持框架：ArkUI, RN, KMP

追溯方法：
1. 优先：通过IPC线程的runnable状态，wakeup_from tid直接找到应用线程的帧
2. 备选：通过唤醒链追溯（RS进程IPC线程 → 应用进程IPC线程 → UI线程）
"""

import sqlite3
import sys
import re
import argparse
import logging
import time
import os
from typing import Optional, Dict, List, Tuple
import io

# 注意：移除模块级别的stdout/stderr重定向和日志配置
# 这些操作应该由主脚本统一管理，避免导入时的冲突

logger = logging.getLogger(__name__)

# 导入CPU指令数计算函数（使用相对导入）
from .frame_empty_common import (
    calculate_thread_instructions,
    calculate_app_frame_cpu_waste
)
from .frame_utils import is_system_thread


def parse_unmarsh_pid(event_name: str) -> Optional[int]:
    """从UnMarsh事件名称中提取pid"""
    pattern = r'recv data from (\d+)'
    match = re.search(pattern, event_name)
    if match:
        return int(match.group(1))
    return None


def find_unmarsh_events_in_rs_frame(
    trace_conn: sqlite3.Connection,
    rs_frame_ts: int,
    rs_frame_dur: int,
    time_window_before: int = 500_000_000,  # 扩大到500ms，保证找到最近的buffer
    unmarsh_events_cache: Optional[List[Tuple]] = None
) -> List[Tuple]:
    """
    在RS帧时间窗口内查找UnMarsh事件（支持缓存）
    
    Args:
        trace_conn: trace数据库连接
        rs_frame_ts: RS帧开始时间
        rs_frame_dur: RS帧持续时间
        time_window_before: RS帧开始前的时间窗口（纳秒）
        unmarsh_events_cache: UnMarsh事件缓存列表，每个元素为 (name, ts, thread_id, thread_name, process_name, process_pid)
    
    Returns:
        事件列表
    """
    # 如果提供了缓存，从缓存中过滤，并选择最近的事件
    if unmarsh_events_cache is not None:
        result = []
        frame_start = rs_frame_ts - time_window_before
        frame_end = rs_frame_ts + rs_frame_dur
        
        for event in unmarsh_events_cache:
            event_ts = event[1]  # ts是第二个元素
            if frame_start <= event_ts <= frame_end:
                result.append(event)
        
        # 按距离RS帧的时间排序，选择最近的5个
        if result:
            result.sort(key=lambda x: abs(x[1] - rs_frame_ts))
            return result[:5]
        return result
    
    # 没有缓存，查询数据库
    cursor = trace_conn.cursor()
    
    query = """
    SELECT 
        c.name,
        c.ts,
        c.callid as thread_id,
        t.name as thread_name,
        p.name as process_name,
        p.pid as process_pid
    FROM callstack c
    INNER JOIN thread t ON c.callid = t.id
    INNER JOIN process p ON t.ipid = p.ipid
    WHERE p.name = 'render_service'
    AND c.name LIKE '%UnMarsh RSTransactionData%'
    AND c.ts >= ? - ?
    AND c.ts <= ? + ?
    ORDER BY ABS(c.ts - ?)
    LIMIT 5
    """
    
    cursor.execute(query, (
        rs_frame_ts,
        time_window_before,
        rs_frame_ts,
        rs_frame_dur,
        rs_frame_ts  # 用于ORDER BY ABS计算
    ))
    
    return cursor.fetchall()


def trace_by_runnable_wakeup_from(
    trace_conn: sqlite3.Connection,
    rs_ipc_thread_id: int,
    event_ts: int,
    app_pid: int,
    time_window: int = 10_000_000,
    instant_cache: Optional[Dict] = None,
    thread_info_cache: Optional[Dict] = None,
    app_frames_cache: Optional[Dict] = None
) -> Optional[Dict]:
    """
    通过IPC线程的runnable状态，wakeup_from tid追溯应用帧
    
    Args:
        trace_conn: trace数据库连接
        rs_ipc_thread_id: RS进程IPC线程ID
        event_ts: UnMarsh事件时间戳
        app_pid: 应用进程PID
        time_window: 时间窗口（纳秒）
    
    Returns:
        应用帧信息，如果找到；否则None
    """
    # 步骤1: 查找IPC线程的runnable状态下的wakeup_from tid
    # 在instant表中查找sched_wakeup事件，ref是IPC线程，wakeup_from是应用线程
    app_thread_id = None
    wakeup_ts = None
    
    if instant_cache is not None:
        # 从缓存中查找
        if rs_ipc_thread_id in instant_cache:
            wakeup_events = instant_cache[rs_ipc_thread_id]
            # 在时间窗口内查找最接近的wakeup事件
            best_wakeup = None
            best_diff = float('inf')
            for wf, ts in wakeup_events:
                if event_ts - time_window <= ts <= event_ts + time_window:
                    diff = abs(ts - event_ts)
                    if diff < best_diff:
                        best_diff = diff
                        best_wakeup = (wf, ts)
            if best_wakeup:
                app_thread_id, wakeup_ts = best_wakeup
    else:
        # 查询数据库
        cursor = trace_conn.cursor()
        wakeup_query = """
        SELECT 
            i.wakeup_from as app_thread_id,
            i.ts as wakeup_ts
        FROM instant i
        WHERE i.name = 'sched_wakeup'
        AND i.ref = ?
        AND i.ts >= ? - ?
        AND i.ts <= ? + ?
        ORDER BY ABS(i.ts - ?)
        LIMIT 1
        """
        
        cursor.execute(wakeup_query, (
            rs_ipc_thread_id,
            event_ts,
            time_window,
            event_ts,
            time_window,
            event_ts
        ))
        
        wakeup_result = cursor.fetchone()
        if wakeup_result:
            app_thread_id = wakeup_result[0]
            wakeup_ts = wakeup_result[1]
    
    if not app_thread_id or not wakeup_ts:
        logger.debug(f'未找到IPC线程 {rs_ipc_thread_id} 的wakeup_from tid')
        return None
    
    # 步骤2: 验证应用线程是否属于指定的应用进程
    thread_id = None
    thread_name = None
    process_name = None
    process_pid = None
    
    if thread_info_cache is not None:
        # 从缓存中查找
        if app_thread_id in thread_info_cache:
            info = thread_info_cache[app_thread_id]
            if info.get('pid') == app_pid:
                thread_id = app_thread_id
                thread_name = info.get('thread_name')
                process_name = info.get('process_name')
                process_pid = info.get('pid')
    else:
        # 查询数据库
        cursor = trace_conn.cursor()
        thread_info_query = """
        SELECT t.id, t.name, p.name as process_name, p.pid
        FROM thread t
        INNER JOIN process p ON t.ipid = p.ipid
        WHERE t.id = ? AND p.pid = ?
        """
        
        cursor.execute(thread_info_query, (app_thread_id, app_pid))
        thread_info = cursor.fetchone()
        
        if thread_info:
            thread_id, thread_name, process_name, process_pid = thread_info
    
    if not thread_id:
        logger.debug(f'线程 {app_thread_id} 不属于进程 {app_pid}')
        return None
    
    # 步骤3: 在应用线程中查找对应的帧
    # 时间窗口：UnMarsh事件前500ms到后10ms
    time_start = event_ts - 500_000_000  # 扩大到500ms
    time_end = event_ts + 10_000_000
    
    frame_id = None
    frame_ts = None
    frame_dur = None
    frame_flag = None
    frame_vsync = None
    
    if app_frames_cache is not None:
        # 从缓存中查找
        if app_thread_id in app_frames_cache:
            frames = app_frames_cache[app_thread_id]
            best_frame = None
            best_diff = float('inf')
            for f in frames:
                f_ts = f[1]  # ts是第二个元素
                if time_start <= f_ts <= time_end:
                    diff = abs(f_ts - event_ts)
                    if diff < best_diff:
                        best_diff = diff
                        best_frame = f
            if best_frame:
                frame_id, frame_ts, frame_dur, frame_flag, frame_vsync = best_frame[:5]
    else:
        # 查询数据库
        cursor = trace_conn.cursor()
        frame_query = """
        SELECT 
            fs.rowid,
            fs.ts,
            fs.dur,
            fs.flag,
            fs.vsync
        FROM frame_slice fs
        WHERE fs.itid = ?
        AND fs.ts >= ?
        AND fs.ts <= ?
        AND fs.type = 0
        ORDER BY ABS(fs.ts - ?)
        LIMIT 1
        """
        
        cursor.execute(frame_query, (app_thread_id, time_start, time_end, event_ts))
        frame_result = cursor.fetchone()
        
        if frame_result:
            frame_id, frame_ts, frame_dur, frame_flag, frame_vsync = frame_result
    
    if not frame_id:
        logger.debug(f'未找到应用线程 {thread_name} 的帧')
        return None
    
    return {
        'frame_id': frame_id,
        'frame_ts': frame_ts,
        'frame_dur': frame_dur if frame_dur else 0,
        'frame_flag': frame_flag,
        'frame_vsync': frame_vsync,
        'thread_id': thread_id,
        'thread_name': thread_name,
        'process_name': process_name,
        'process_pid': process_pid,
        'app_pid': process_pid,  # 添加app_pid字段，与process_pid相同
        'pid': process_pid,  # 添加pid字段（兼容）
        'wakeup_ts': wakeup_ts,
        'trace_method': 'runnable_wakeup_from'
    }


def trace_by_wakeup_chain(
    trace_conn: sqlite3.Connection,
    rs_ipc_thread_id: int,
    event_ts: int,
    app_pid: int,
    max_depth: int = 5,
    time_window: int = 500_000_000,  # 扩大到500ms
    instant_cache: Optional[Dict] = None,
    thread_info_cache: Optional[Dict] = None,
    app_frames_cache: Optional[Dict] = None
) -> Optional[Dict]:
    """
    通过唤醒链追溯应用帧（备选方法）
    
    追溯路径：RS进程IPC线程 → 应用进程IPC线程 → UI线程
    """
    cursor = trace_conn.cursor()
    
    # 步骤1: 从RS进程IPC线程开始，向前追溯唤醒链
    # 找到应用进程的IPC线程
    current_thread_id = rs_ipc_thread_id
    current_ts = event_ts
    depth = 0
    app_ipc_thread_id = None
    
    while depth < max_depth and current_thread_id:
        # 查找唤醒当前线程的事件
        waker_thread_id = None
        wakeup_ts = None
        
        if instant_cache is not None:
            # 从缓存中查找
            if current_thread_id in instant_cache:
                wakeup_events = instant_cache[current_thread_id]
                # 在时间窗口内查找最接近的wakeup事件
                best_wakeup = None
                best_diff = float('inf')
                for wf, ts in wakeup_events:
                    if current_ts - time_window <= ts <= current_ts:
                        diff = abs(ts - current_ts)
                        if diff < best_diff:
                            best_diff = diff
                            best_wakeup = (wf, ts)
                if best_wakeup:
                    waker_thread_id, wakeup_ts = best_wakeup
        else:
            # 查询数据库
            cursor = trace_conn.cursor()
            wakeup_query = """
            SELECT 
                i.wakeup_from as waker_thread_id,
                i.ts as wakeup_ts
            FROM instant i
            WHERE i.name = 'sched_wakeup'
            AND i.ref = ?
            AND i.ts >= ? - ?
            AND i.ts <= ?
            ORDER BY i.ts DESC
            LIMIT 1
            """
            
            cursor.execute(wakeup_query, (current_thread_id, current_ts, time_window, current_ts))
            wakeup_result = cursor.fetchone()
            
            if wakeup_result:
                waker_thread_id = wakeup_result[0]
                wakeup_ts = wakeup_result[1]
        
        if not waker_thread_id or not wakeup_ts:
            break
        
        if not waker_thread_id:
            break
        
        # 检查唤醒者线程是否属于应用进程
        if thread_info_cache is not None:
            # 从缓存中查找
            if waker_thread_id in thread_info_cache:
                info = thread_info_cache[waker_thread_id]
                if info.get('pid') == app_pid:
                    # 找到应用进程的线程
                    app_ipc_thread_id = waker_thread_id
                    break
        else:
            # 查询数据库
            cursor = trace_conn.cursor()
            thread_info_query = """
            SELECT t.id, t.name, p.name as process_name, p.pid
            FROM thread t
            INNER JOIN process p ON t.ipid = p.ipid
            WHERE t.id = ? AND p.pid = ?
            """
            
            cursor.execute(thread_info_query, (waker_thread_id, app_pid))
            thread_info = cursor.fetchone()
            
            if thread_info:
                # 找到应用进程的线程
                app_ipc_thread_id = waker_thread_id
                break
        
        current_thread_id = waker_thread_id
        current_ts = wakeup_ts
        depth += 1
    
    if not app_ipc_thread_id:
        logger.debug(f'未找到应用进程 {app_pid} 的IPC线程')
        return None
    
    # 步骤2: 从应用进程IPC线程开始，向前追溯找到UI线程
    # 查找应用进程的UI线程（名称与进程名相同，或包含"UI"）
    ui_thread_id = None
    ui_thread_name = None
    process_name = None
    
    if thread_info_cache is not None:
        # 从缓存中查找应用进程的UI线程
        for itid, info in thread_info_cache.items():
            if info.get('pid') == app_pid:
                thread_name = info.get('thread_name', '')
                proc_name = info.get('process_name', '')
                if thread_name == proc_name or 'UI' in thread_name or 'ui' in thread_name:
                    ui_thread_id = itid
                    ui_thread_name = thread_name
                    process_name = proc_name
                    break
    else:
        # 查询数据库
        cursor = trace_conn.cursor()
        ui_thread_query = """
        SELECT t.id, t.name, p.name as process_name
        FROM thread t
        INNER JOIN process p ON t.ipid = p.ipid
        WHERE p.pid = ?
        AND (t.name = p.name OR t.name LIKE '%UI%' OR t.name LIKE '%ui%')
        ORDER BY 
            CASE 
                WHEN t.name = p.name THEN 0
                WHEN t.name LIKE '%UI%' OR t.name LIKE '%ui%' THEN 1
                ELSE 2
            END
        LIMIT 1
        """
        
        cursor.execute(ui_thread_query, (app_pid,))
        ui_thread = cursor.fetchone()
        
        if ui_thread:
            ui_thread_id, ui_thread_name, process_name = ui_thread
    
    if not ui_thread_id:
        logger.debug(f'未找到应用进程 {app_pid} 的UI线程')
        return None
    
    # 步骤3: 在UI线程中查找对应的帧
    time_start = event_ts - 500_000_000  # 扩大到500ms
    time_end = event_ts + 10_000_000
    
    frame_id = None
    frame_ts = None
    frame_dur = None
    frame_flag = None
    frame_vsync = None
    
    if app_frames_cache is not None:
        # 从缓存中查找
        if ui_thread_id in app_frames_cache:
            frames = app_frames_cache[ui_thread_id]
            best_frame = None
            best_diff = float('inf')
            for f in frames:
                f_ts = f[1]  # ts是第二个元素
                if time_start <= f_ts <= time_end:
                    diff = abs(f_ts - event_ts)
                    if diff < best_diff:
                        best_diff = diff
                        best_frame = f
            if best_frame:
                frame_id, frame_ts, frame_dur, frame_flag, frame_vsync = best_frame[:5]
    else:
        # 查询数据库
        cursor = trace_conn.cursor()
        frame_query = """
        SELECT 
            fs.rowid,
            fs.ts,
            fs.dur,
            fs.flag,
            fs.vsync
        FROM frame_slice fs
        WHERE fs.itid = ?
        AND fs.ts >= ?
        AND fs.ts <= ?
        AND fs.type = 0
        ORDER BY ABS(fs.ts - ?)
        LIMIT 1
        """
        
        cursor.execute(frame_query, (ui_thread_id, time_start, time_end, event_ts))
        frame_result = cursor.fetchone()
        
        if frame_result:
            frame_id, frame_ts, frame_dur, frame_flag, frame_vsync = frame_result
    
    if not frame_id:
        logger.debug(f'未找到UI线程 {ui_thread_name} 的帧')
        return None
    
    return {
        'frame_id': frame_id,
        'frame_ts': frame_ts,
        'frame_dur': frame_dur if frame_dur else 0,
        'frame_flag': frame_flag,
        'frame_vsync': frame_vsync,
        'thread_id': ui_thread_id,
        'thread_name': ui_thread_name,
        'process_name': process_name,
        'process_pid': app_pid,
        'app_pid': app_pid,  # 添加app_pid字段
        'pid': app_pid,  # 添加pid字段（兼容）
        'trace_method': 'wakeup_chain'
    }


def preload_caches(
    trace_conn: sqlite3.Connection,
    min_ts: int,
    max_ts: int
) -> Dict:
    """
    预加载数据库表到内存（性能优化）
    
    Args:
        trace_conn: trace数据库连接
        min_ts: 最小时间戳
        max_ts: 最大时间戳
    
    Returns:
        包含所有缓存的字典
    """
    cursor = trace_conn.cursor()
    caches = {}
    
    print(f'[性能优化] 开始预加载数据库表到内存 (时间范围: {min_ts} - {max_ts})...')
    preload_start = time.time()
    
    # 1. 预加载UnMarsh事件
    print('  [预加载] 加载UnMarsh事件...')
    unmarsh_query = """
    SELECT 
        c.name,
        c.ts,
        c.callid as thread_id,
        t.name as thread_name,
        p.name as process_name,
        p.pid as process_pid
    FROM callstack c
    INNER JOIN thread t ON c.callid = t.id
    INNER JOIN process p ON t.ipid = p.ipid
    WHERE p.name = 'render_service'
    AND c.name LIKE '%UnMarsh RSTransactionData%'
    AND c.ts >= ?
    AND c.ts <= ?
    ORDER BY c.ts
    """
    cursor.execute(unmarsh_query, (min_ts, max_ts))
    caches['unmarsh_events'] = cursor.fetchall()
    print(f'  [预加载] UnMarsh事件: {len(caches["unmarsh_events"])} 条记录')
    
    # 2. 预加载instant表（用于runnable和唤醒链）
    print('  [预加载] 加载instant表...')
    instant_query = """
    SELECT i.ref, i.wakeup_from, i.ts
    FROM instant i
    WHERE i.name = 'sched_wakeup'
    AND i.ts >= ?
    AND i.ts <= ?
    AND i.ref_type = 'itid'
    AND i.wakeup_from IS NOT NULL
    AND i.ref IS NOT NULL
    """
    cursor.execute(instant_query, (min_ts, max_ts))
    instant_data = cursor.fetchall()
    
    # 构建instant缓存：按ref分组，存储(wakeup_from, ts)列表
    instant_cache = {}
    for ref, wakeup_from, ts in instant_data:
        if ref not in instant_cache:
            instant_cache[ref] = []
        instant_cache[ref].append((wakeup_from, ts))
    caches['instant'] = instant_cache
    print(f'  [预加载] instant表: {len(instant_data)} 条记录，{len(instant_cache)} 个线程')
    
    # 3. 预加载thread和process表
    print('  [预加载] 加载thread和process表...')
    thread_process_query = """
    SELECT t.id, t.tid, t.name as thread_name, p.name as process_name, p.pid
    FROM thread t
    INNER JOIN process p ON t.ipid = p.ipid
    """
    cursor.execute(thread_process_query)
    thread_process_data = cursor.fetchall()
    
    # 构建thread_info缓存：itid -> {tid, thread_name, process_name, pid}
    thread_info_cache = {}
    # 同时构建tid_to_info缓存：tid -> {itid, thread_name, process_name, pid}
    tid_to_info_cache = {}
    for itid, tid, thread_name, process_name, pid in thread_process_data:
        thread_info_cache[itid] = {
            'tid': tid,
            'thread_name': thread_name,
            'process_name': process_name,
            'pid': pid
        }
        tid_to_info_cache[tid] = {
            'itid': itid,
            'thread_name': thread_name,
            'process_name': process_name,
            'pid': pid
        }
    caches['thread_info'] = thread_info_cache
    caches['tid_to_info'] = tid_to_info_cache
    print(f'  [预加载] thread/process表: {len(thread_process_data)} 个线程')
    
    # 4. 预加载应用帧（非RS进程的帧）
    print('  [预加载] 加载应用帧...')
    app_frames_query = """
    SELECT 
        fs.rowid,
        fs.ts,
        fs.dur,
        fs.flag,
        fs.vsync,
        fs.itid
    FROM frame_slice fs
    INNER JOIN thread t ON fs.itid = t.id
    INNER JOIN process p ON t.ipid = p.ipid
    WHERE p.name != 'render_service'
    AND fs.type = 0
    AND fs.ts >= ?
    AND fs.ts <= ?
    """
    cursor.execute(app_frames_query, (min_ts, max_ts))
    app_frames_data = cursor.fetchall()
    
    # 构建app_frames缓存：按itid分组
    app_frames_cache = {}
    for row in app_frames_data:
        itid = row[5]  # itid是最后一个元素
        if itid not in app_frames_cache:
            app_frames_cache[itid] = []
        app_frames_cache[itid].append(row[:5])  # (rowid, ts, dur, flag, vsync)
    caches['app_frames'] = app_frames_cache
    print(f'  [预加载] 应用帧: {len(app_frames_data)} 条记录，{len(app_frames_cache)} 个线程')
    
    preload_elapsed = time.time() - preload_start
    print(f'[性能优化] 预加载完成，耗时: {preload_elapsed:.3f}秒\n')
    
    return caches


def trace_rs_skip_to_app_frame(
    trace_conn: sqlite3.Connection,
    rs_frame_id: int,
    caches: Optional[Dict] = None,
    perf_conn: Optional[sqlite3.Connection] = None,
    perf_sample_cache: Optional[Dict] = None,
    perf_timestamp_field: Optional[str] = None
) -> Optional[Dict]:
    """
    从RS skip帧追溯到应用进程提交的帧
    
    Args:
        trace_conn: trace数据库连接
        rs_frame_id: RS帧ID（frame_slice.rowid）
    
    Returns:
        追溯结果，包含RS帧和应用帧信息
    """
    # ========== 性能计时开始 ==========
    import time
    perf_timings = {}
    perf_start = time.time()
    # ========== 性能计时开始 ==========
    
    cursor = trace_conn.cursor()
    
    # 步骤1: 获取RS帧信息
    perf_t1 = time.time()
    perf_timings['get_rs_frame'] = perf_t1 - perf_start
    rs_frame_query = """
    SELECT 
        fs.rowid,
        fs.ts,
        fs.dur,
        fs.flag,
        fs.vsync,
        fs.itid
    FROM frame_slice fs
    WHERE fs.rowid = ?
    AND fs.ipid IN (
        SELECT p.ipid
        FROM process p
        WHERE p.name = 'render_service'
    )
    """
    
    cursor.execute(rs_frame_query, (rs_frame_id,))
    rs_frame = cursor.fetchone()
    
    if not rs_frame:
        logger.error(f'未找到RS帧 {rs_frame_id}')
        return None
    
    frame_id, frame_ts, frame_dur, frame_flag, frame_vsync, frame_itid = rs_frame
    frame_dur = frame_dur if frame_dur else 0
    
    # logger.info(f'RS帧 {frame_id}: 时间={frame_ts}, dur={frame_dur}, flag={frame_flag}, vsync={frame_vsync}')
    
    # 步骤2: 在RS帧时间窗口内查找UnMarsh事件
    perf_t2 = time.time()
    perf_timings['find_unmarsh'] = perf_t2 - perf_t1
    unmarsh_events_cache = caches.get('unmarsh_events') if caches else None
    unmarsh_events = find_unmarsh_events_in_rs_frame(
        trace_conn, frame_ts, frame_dur, time_window_before=500_000_000,  # 扩大到500ms，保证找到最近的buffer
        unmarsh_events_cache=unmarsh_events_cache
    )
    perf_t3 = time.time()
    perf_timings['find_unmarsh_done'] = perf_t3 - perf_t2
    
    if not unmarsh_events:
        logger.warning(f'RS帧 {frame_id} 未找到UnMarsh事件')
        return {
            'rs_frame': {
                'frame_id': frame_id,
                'ts': frame_ts,
                'dur': frame_dur,
                'flag': frame_flag,
                'vsync': frame_vsync
            },
            'app_frame': None,
            'trace_method': None,
            'error': '未找到UnMarsh事件'
        }
    
    # logger.info(f'找到 {len(unmarsh_events)} 个UnMarsh事件')
    
    # 步骤3: 对每个UnMarsh事件尝试追溯
    for unmarsh_event in unmarsh_events:
        event_name = unmarsh_event[0]
        event_ts = unmarsh_event[1]
        rs_ipc_thread_id = unmarsh_event[2]
        rs_ipc_thread_name = unmarsh_event[3]
        
        # 提取应用进程PID
        app_pid = parse_unmarsh_pid(event_name)
        if not app_pid:
            continue
        
        # logger.info(f'UnMarsh事件: 时间={event_ts}, RS IPC线程={rs_ipc_thread_name}, 应用PID={app_pid}')
        
        # 方法1: 优先使用runnable方法
        perf_t4 = time.time()
        perf_timings['runnable_start'] = perf_t4 - perf_t3
        instant_cache = caches.get('instant') if caches else None
        thread_info_cache = caches.get('thread_info') if caches else None
        app_frames_cache = caches.get('app_frames') if caches else None
        app_frame = trace_by_runnable_wakeup_from(
            trace_conn, rs_ipc_thread_id, event_ts, app_pid,
            instant_cache=instant_cache,
            thread_info_cache=thread_info_cache,
            app_frames_cache=app_frames_cache
        )
        perf_t5 = time.time()
        perf_timings['runnable_done'] = perf_t5 - perf_t4
        
        if app_frame:
            # logger.info(f'通过runnable方法找到应用帧: {app_frame["frame_id"]}')
            
            # 计算CPU浪费
            tid_to_info_cache = caches.get('tid_to_info') if caches else None
            cpu_waste = calculate_app_frame_cpu_waste(
                trace_conn=trace_conn,
                perf_conn=perf_conn,
                app_frame=app_frame,
                perf_sample_cache=perf_sample_cache,
                perf_timestamp_field=perf_timestamp_field,
                tid_to_info_cache=tid_to_info_cache
            )
            app_frame['cpu_waste'] = cpu_waste
            
            perf_end = time.time()
            perf_timings['total'] = perf_end - perf_start
            # print(f'[性能] RS帧{frame_id} 追溯耗时: {perf_timings["total"]*1000:.2f}ms | '
            #       f'获取RS帧: {perf_timings["get_rs_frame"]*1000:.2f}ms | '
            #       f'查找UnMarsh: {perf_timings["find_unmarsh"]*1000:.2f}ms | '
            #       f'UnMarsh查询: {perf_timings["find_unmarsh_done"]*1000:.2f}ms | '
            #       f'Runnable追溯: {perf_timings["runnable_done"]*1000:.2f}ms')
            return {
                'rs_frame': {
                    'frame_id': frame_id,
                    'ts': frame_ts,
                    'dur': frame_dur,
                    'flag': frame_flag,
                    'vsync': frame_vsync
                },
                'app_frame': app_frame,
                'trace_method': 'runnable_wakeup_from'
            }
        
        # 方法2: 备选使用唤醒链方法
        perf_t6 = time.time()
        perf_timings['wakeup_chain_start'] = perf_t6 - perf_t5
        app_frame = trace_by_wakeup_chain(
            trace_conn, rs_ipc_thread_id, event_ts, app_pid,
            instant_cache=instant_cache,
            thread_info_cache=thread_info_cache,
            app_frames_cache=app_frames_cache
        )
        perf_t7 = time.time()
        perf_timings['wakeup_chain_done'] = perf_t7 - perf_t6
        
        if app_frame:
            # logger.info(f'通过唤醒链方法找到应用帧: {app_frame["frame_id"]}')
            
            # 计算CPU浪费
            tid_to_info_cache = caches.get('tid_to_info') if caches else None
            cpu_waste = calculate_app_frame_cpu_waste(
                trace_conn=trace_conn,
                perf_conn=perf_conn,
                app_frame=app_frame,
                perf_sample_cache=perf_sample_cache,
                perf_timestamp_field=perf_timestamp_field,
                tid_to_info_cache=tid_to_info_cache
            )
            app_frame['cpu_waste'] = cpu_waste
            
            perf_end = time.time()
            perf_timings['total'] = perf_end - perf_start
            # print(f'[性能] RS帧{frame_id} 追溯耗时: {perf_timings["total"]*1000:.2f}ms | '
            #       f'获取RS帧: {perf_timings["get_rs_frame"]*1000:.2f}ms | '
            #       f'查找UnMarsh: {perf_timings["find_unmarsh"]*1000:.2f}ms | '
            #       f'UnMarsh查询: {perf_timings["find_unmarsh_done"]*1000:.2f}ms | '
            #       f'Runnable追溯: {perf_timings.get("runnable_done", 0)*1000:.2f}ms | '
            #       f'唤醒链追溯: {perf_timings["wakeup_chain_done"]*1000:.2f}ms')
            return {
                'rs_frame': {
                    'frame_id': frame_id,
                    'ts': frame_ts,
                    'dur': frame_dur,
                    'flag': frame_flag,
                    'vsync': frame_vsync
                },
                'app_frame': app_frame,
                'trace_method': 'wakeup_chain'
            }
    
    # 所有方法都失败
    perf_end = time.time()
    perf_timings['total'] = perf_end - perf_start
    # print(f'[性能] RS帧{frame_id} 追溯失败，耗时: {perf_timings["total"]*1000:.2f}ms | '
    #       f'获取RS帧: {perf_timings["get_rs_frame"]*1000:.2f}ms | '
    #       f'查找UnMarsh: {perf_timings["find_unmarsh"]*1000:.2f}ms | '
    #       f'UnMarsh查询: {perf_timings["find_unmarsh_done"]*1000:.2f}ms')
    return {
        'rs_frame': {
            'frame_id': frame_id,
            'ts': frame_ts,
            'dur': frame_dur,
            'flag': frame_flag,
            'vsync': frame_vsync
        },
        'app_frame': None,
        'trace_method': None,
        'error': '所有追溯方法都失败'
    }


def main():
    parser = argparse.ArgumentParser(
        description='RS系统API流程：从RS skip帧追溯到应用进程提交的帧'
    )
    parser.add_argument('trace_db', help='trace数据库路径')
    parser.add_argument('--rs-frame-id', type=int, help='RS帧ID（frame_slice.rowid）')
    parser.add_argument('--verbose', '-v', action='store_true', help='详细输出')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # 连接数据库
    try:
        trace_conn = sqlite3.connect(args.trace_db)
    except Exception as e:
        logger.error(f'无法连接数据库: {e}')
        return 1
    
    try:
        if args.rs_frame_id:
            # 获取RS帧信息以确定时间范围
            cursor = trace_conn.cursor()
            rs_frame_query = """
            SELECT fs.ts, fs.dur
            FROM frame_slice fs
            WHERE fs.rowid = ?
            AND fs.ipid IN (
                SELECT p.ipid FROM process p WHERE p.name = 'render_service'
            )
            """
            cursor.execute(rs_frame_query, (args.rs_frame_id,))
            rs_frame_info = cursor.fetchone()
            
            # 预加载缓存（如果RS帧存在）
            caches = None
            if rs_frame_info:
                frame_ts, frame_dur = rs_frame_info
                frame_dur = frame_dur if frame_dur else 0
                min_ts = frame_ts - 200_000_000  # 前200ms
                max_ts = frame_ts + frame_dur + 50_000_000  # 后50ms
                caches = preload_caches(trace_conn, min_ts, max_ts)
            
            # 追溯指定的RS帧
            result = trace_rs_skip_to_app_frame(trace_conn, args.rs_frame_id, caches=caches)
            
            if result:
                print(f'\n{"="*100}')
                print('追溯结果')
                print(f'{"="*100}\n')
                
                print(f'RS帧:')
                print(f'  帧ID: {result["rs_frame"]["frame_id"]}')
                print(f'  时间: {result["rs_frame"]["ts"]}')
                print(f'  持续时间: {result["rs_frame"]["dur"] / 1_000_000:.2f}ms')
                print(f'  Flag: {result["rs_frame"]["flag"]}')
                print(f'  VSync: {result["rs_frame"]["vsync"]}')
                
                if result['app_frame']:
                    print(f'\n应用帧:')
                    print(f'  帧ID: {result["app_frame"]["frame_id"]}')
                    print(f'  时间: {result["app_frame"]["frame_ts"]}')
                    print(f'  持续时间: {result["app_frame"]["frame_dur"] / 1_000_000:.2f}ms')
                    print(f'  Flag: {result["app_frame"]["frame_flag"]}')
                    print(f'  VSync: {result["app_frame"]["frame_vsync"]}')
                    print(f'  线程: {result["app_frame"]["thread_name"]} (ID: {result["app_frame"]["thread_id"]})')
                    print(f'  进程: {result["app_frame"]["process_name"]} (PID: {result["app_frame"]["process_pid"]})')
                    print(f'  追溯方法: {result["trace_method"]}')
                else:
                    print(f'\n应用帧: 未找到')
                    if 'error' in result:
                        print(f'  错误: {result["error"]}')
        else:
            # 查找所有包含skip的RS帧并追溯
            # logger.info('查找所有包含skip的RS帧...')
            # 这里可以调用rs_skip_analyzer.py的逻辑来找到skip帧
            print('请使用 --rs-frame-id 指定要追溯的RS帧ID')
            print('或者先运行 rs_skip_analyzer.py 找到skip帧，然后使用 --rs-frame-id 追溯')
    
    finally:
        trace_conn.close()
    
    return 0


if __name__ == '__main__':
    sys.exit(main())

