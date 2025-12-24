#!/usr/bin/env python3
"""
NativeWindow API流程：从RS skip帧追溯到应用进程提交的帧

支持框架：Flutter, ArkWeb

追溯方法：
- 基于时间戳匹配（时间窗口匹配）
- 在RS帧时间窗口内查找AcquireBuffer/DoFlushBuffer事件
- 在RS事件时间窗口内查找应用帧（前100ms到后10ms）
"""

import argparse
import logging
import sqlite3
import sys
import time
from typing import Optional

# 移除模块级别的stdout/stderr重定向和日志配置
# 这些操作应该由主脚本统一管理，避免导入时的冲突
# 导入CPU指令数计算函数（使用相对导入）
from .frame_empty_common import calculate_app_frame_cpu_waste

logger = logging.getLogger(__name__)


def find_rs_nativewindow_events_in_frame(
    trace_conn: sqlite3.Connection,
    rs_frame_ts: int,
    rs_frame_dur: int,
    time_window_before: int = 500_000_000,  # 扩大到500ms，保证找到最近的buffer
    nativewindow_events_cache: Optional[list[tuple]] = None,
) -> list[tuple]:
    """
    在RS帧时间窗口内查找NativeWindow API相关事件（支持缓存）

    Args:
        trace_conn: trace数据库连接
        rs_frame_ts: RS帧开始时间
        rs_frame_dur: RS帧持续时间
        time_window_before: RS帧开始前的时间窗口（纳秒）
        nativewindow_events_cache: NativeWindow事件缓存列表，每个元素为 (name, ts, dur, thread_id, thread_name, process_name)

    Returns:
        事件列表，每个元素为 (event_name, event_ts, event_dur, thread_id, thread_name, process_name)
    """
    # 如果提供了缓存，从缓存中过滤，并选择最近的事件
    if nativewindow_events_cache is not None:
        result = []
        frame_start = rs_frame_ts - time_window_before
        frame_end = rs_frame_ts + rs_frame_dur

        for event in nativewindow_events_cache:
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
        c.dur,
        c.callid as thread_id,
        t.name as thread_name,
        p.name as process_name
    FROM callstack c
    INNER JOIN thread t ON c.callid = t.id
    INNER JOIN process p ON t.ipid = p.ipid
    WHERE p.name = 'render_service'
    AND (
        c.name LIKE '%AcquireBuffer%'
        OR c.name LIKE '%DoFlushBuffer%'
        OR c.name LIKE '%ConsumeAndUpdateAllNodes%'
    )
    AND c.ts >= ? - ?
    AND c.ts <= ? + ?
    ORDER BY ABS(c.ts - ?)
    LIMIT 5
    """

    cursor.execute(
        query,
        (
            rs_frame_ts,
            time_window_before,
            rs_frame_ts,
            rs_frame_dur,
            rs_frame_ts,  # 用于ORDER BY ABS计算
        ),
    )

    return cursor.fetchall()


def find_app_frames_near_rs_event(
    trace_conn: sqlite3.Connection,
    rs_event_ts: int,
    time_window_before: int = 500_000_000,  # 扩大到500ms
    time_window_after: int = 10_000_000,
    app_frames_cache: Optional[list[tuple]] = None,
) -> list[dict]:
    """
    在RS事件时间窗口内查找应用帧（支持缓存）

    Args:
        trace_conn: trace数据库连接
        rs_event_ts: RS事件时间戳
        time_window_before: 事件前的时间窗口（纳秒，默认100ms）
        time_window_after: 事件后的时间窗口（纳秒，默认10ms）
        app_frames_cache: 应用帧缓存列表，每个元素为 (rowid, ts, dur, flag, vsync, thread_name, process_name, process_pid)

    Returns:
        应用帧列表，按时间差排序（最近的在前）
    """
    # 如果提供了缓存，从缓存中过滤
    if app_frames_cache is not None:
        result = []
        window_start = rs_event_ts - time_window_before
        window_end = rs_event_ts + time_window_after

        for frame in app_frames_cache:
            frame_ts = frame[1]  # ts是第二个元素
            if window_start <= frame_ts <= window_end:
                # frame格式: (rowid, ts, dur, flag, vsync, itid, thread_name, process_name, process_pid)
                frame_id, frame_ts, frame_dur, frame_flag, frame_vsync, itid, thread_name, process_name, process_pid = (
                    frame
                )
                frame_dur = frame_dur if frame_dur else 0
                time_diff_ns = abs(frame_ts - rs_event_ts)

                result.append(
                    {
                        'frame_id': frame_id,
                        'frame_ts': frame_ts,
                        'frame_dur': frame_dur,
                        'frame_flag': frame_flag,
                        'frame_vsync': frame_vsync,
                        'thread_id': itid,  # itid用于计算CPU指令数
                        'thread_name': thread_name,
                        'process_name': process_name,
                        'process_pid': process_pid,
                        'time_diff_ns': time_diff_ns,
                        'time_diff_ms': time_diff_ns / 1_000_000,
                    }
                )

        # 按时间差排序
        result.sort(key=lambda x: x['time_diff_ns'])
        return result[:10]  # 只返回前10个

    # 没有缓存，查询数据库
    cursor = trace_conn.cursor()

    query = """
    SELECT
        fs.rowid,
        fs.ts,
        fs.dur,
        fs.flag,
        fs.vsync,
        fs.itid,
        t.name as thread_name,
        p.name as process_name,
        p.pid as process_pid
    FROM frame_slice fs
    INNER JOIN thread t ON fs.itid = t.id
    INNER JOIN process p ON t.ipid = p.ipid
    WHERE p.name != 'render_service'
    AND fs.type = 0
    AND fs.ts >= ? - ?
    AND fs.ts <= ? + ?
    ORDER BY ABS(fs.ts - ?)
    LIMIT 10
    """

    cursor.execute(query, (rs_event_ts, time_window_before, rs_event_ts, time_window_after, rs_event_ts))

    frames = cursor.fetchall()

    result = []
    for frame in frames:
        frame_id, frame_ts, frame_dur, frame_flag, frame_vsync, itid, thread_name, process_name, process_pid = frame
        frame_dur = frame_dur if frame_dur else 0
        time_diff_ns = abs(frame_ts - rs_event_ts)

        result.append(
            {
                'frame_id': frame_id,
                'frame_ts': frame_ts,
                'frame_dur': frame_dur,
                'frame_flag': frame_flag,
                'frame_vsync': frame_vsync,
                'thread_id': itid,  # itid用于计算CPU指令数
                'thread_name': thread_name,
                'process_name': process_name,
                'process_pid': process_pid,
                'app_pid': process_pid,  # 添加app_pid字段，与process_pid相同
                'pid': process_pid,  # 添加pid字段（兼容）
                'time_diff_ns': time_diff_ns,
                'time_diff_ms': time_diff_ns / 1_000_000,
            }
        )

    return result


def preload_caches(trace_conn: sqlite3.Connection, min_ts: int, max_ts: int) -> dict:
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

    # 1. 预加载NativeWindow API事件
    print('  [预加载] 加载NativeWindow API事件...')
    nativewindow_query = """
    SELECT
        c.name,
        c.ts,
        c.dur,
        c.callid as thread_id,
        t.name as thread_name,
        p.name as process_name
    FROM callstack c
    INNER JOIN thread t ON c.callid = t.id
    INNER JOIN process p ON t.ipid = p.ipid
    WHERE p.name = 'render_service'
    AND (
        c.name LIKE '%AcquireBuffer%'
        OR c.name LIKE '%DoFlushBuffer%'
        OR c.name LIKE '%ConsumeAndUpdateAllNodes%'
    )
    AND c.ts >= ?
    AND c.ts <= ?
    ORDER BY c.ts
    """
    cursor.execute(nativewindow_query, (min_ts, max_ts))
    caches['nativewindow_events'] = cursor.fetchall()
    print(f'  [预加载] NativeWindow API事件: {len(caches["nativewindow_events"])} 条记录')

    # 2. 预加载应用帧（非RS进程的帧）
    print('  [预加载] 加载应用帧...')
    app_frames_query = """
    SELECT
        fs.rowid,
        fs.ts,
        fs.dur,
        fs.flag,
        fs.vsync,
        fs.itid,
        t.name as thread_name,
        p.name as process_name,
        p.pid as process_pid
    FROM frame_slice fs
    INNER JOIN thread t ON fs.itid = t.id
    INNER JOIN process p ON t.ipid = p.ipid
    WHERE p.name != 'render_service'
    AND fs.type = 0
    AND fs.ts >= ?
    AND fs.ts <= ?
    """
    cursor.execute(app_frames_query, (min_ts, max_ts))
    caches['app_frames'] = cursor.fetchall()
    print(f'  [预加载] 应用帧: {len(caches["app_frames"])} 条记录')

    # 3. 预加载thread和process表（用于tid到itid的映射）
    print('  [预加载] 加载thread和process表...')
    thread_process_query = """
    SELECT t.id, t.tid, t.name as thread_name, p.name as process_name, p.pid
    FROM thread t
    INNER JOIN process p ON t.ipid = p.ipid
    """
    cursor.execute(thread_process_query)
    thread_process_data = cursor.fetchall()

    # 构建tid_to_info缓存：tid -> {itid, thread_name, process_name, pid}
    tid_to_info_cache = {}
    for itid, tid, thread_name, process_name, pid in thread_process_data:
        tid_to_info_cache[tid] = {'itid': itid, 'thread_name': thread_name, 'process_name': process_name, 'pid': pid}
    caches['tid_to_info'] = tid_to_info_cache
    print(f'  [预加载] thread/process表: {len(thread_process_data)} 个线程')

    preload_elapsed = time.time() - preload_start
    print(f'[性能优化] 预加载完成，耗时: {preload_elapsed:.3f}秒\n')

    return caches


def trace_rs_skip_to_app_frame(
    trace_conn: sqlite3.Connection,
    rs_frame_id: int,
    nativewindow_events_cache: Optional[list[tuple]] = None,
    app_frames_cache: Optional[list[tuple]] = None,
    perf_conn: Optional[sqlite3.Connection] = None,
    perf_sample_cache: Optional[dict] = None,
    perf_timestamp_field: Optional[str] = None,
    tid_to_info_cache: Optional[dict] = None,
) -> Optional[dict]:
    """
    从RS skip帧追溯到应用进程提交的帧（NativeWindow API流程）

    Args:
        trace_conn: trace数据库连接
        rs_frame_id: RS帧ID（frame_slice.rowid）

    Returns:
        追溯结果，包含RS帧和应用帧信息
    """
    # ========== 性能计时开始 ==========
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

    # 步骤2: 在RS帧时间窗口内查找NativeWindow API事件
    perf_t2 = time.time()
    perf_timings['find_nativewindow_events'] = perf_t2 - perf_t1
    rs_events = find_rs_nativewindow_events_in_frame(
        trace_conn,
        frame_ts,
        frame_dur,
        time_window_before=500_000_000,  # 扩大到500ms，保证找到最近的buffer
        nativewindow_events_cache=nativewindow_events_cache,
    )
    perf_t3 = time.time()
    perf_timings['find_nativewindow_events_done'] = perf_t3 - perf_t2

    if not rs_events:
        logger.warning(f'RS帧 {frame_id} 未找到NativeWindow API事件')
        return {
            'rs_frame': {
                'frame_id': frame_id,
                'ts': frame_ts,
                'dur': frame_dur,
                'flag': frame_flag,
                'vsync': frame_vsync,
            },
            'app_frame': None,
            'trace_method': None,
            'error': '未找到NativeWindow API事件',
        }

    logger.info(f'找到 {len(rs_events)} 个NativeWindow API事件')

    # 步骤3: 对每个RS事件，在时间窗口内查找应用帧
    perf_t4 = time.time()
    perf_timings['match_frames_start'] = perf_t4 - perf_t3
    best_match = None
    best_time_diff = float('inf')

    for rs_event in rs_events:
        event_name = rs_event[0]
        event_ts = rs_event[1]
        event_dur = rs_event[2]
        rs_event[3]
        thread_name = rs_event[4]
        rs_event[5]

        # logger.info(f'RS事件: {event_name[:60]}... | 时间={event_ts}, 线程={thread_name}')

        # 在RS事件时间窗口内查找应用帧
        perf_t5 = time.time()
        app_frames = find_app_frames_near_rs_event(
            trace_conn,
            event_ts,
            time_window_before=500_000_000,  # 扩大到500ms
            time_window_after=10_000_000,  # 10ms
            app_frames_cache=app_frames_cache,
        )
        perf_t6 = time.time()
        perf_timings['find_app_frames'] = perf_timings.get('find_app_frames', 0) + (perf_t6 - perf_t5)

        if app_frames:
            # 选择时间差最小的应用帧
            closest_frame = app_frames[0]  # 已经按时间差排序

            if closest_frame['time_diff_ms'] < best_time_diff:
                best_match = {
                    'rs_event': {'name': event_name, 'ts': event_ts, 'dur': event_dur, 'thread_name': thread_name},
                    'app_frame': closest_frame,
                }
                best_time_diff = closest_frame['time_diff_ms']

                logger.info(
                    f'找到应用帧: 帧ID={closest_frame["frame_id"]}, '
                    f'进程={closest_frame["process_name"]}, '
                    f'时间差={closest_frame["time_diff_ms"]:.2f}ms'
                )

    perf_t7 = time.time()
    perf_timings['match_frames_done'] = perf_t7 - perf_t4
    perf_end = time.time()
    perf_timings['total'] = perf_end - perf_start
    # print(f'[性能] RS帧{frame_id} 追溯耗时: {perf_timings["total"]*1000:.2f}ms | '
    #       f'获取RS帧: {perf_timings["get_rs_frame"]*1000:.2f}ms | '
    #       f'查找NativeWindow事件: {perf_timings["find_nativewindow_events"]*1000:.2f}ms | '
    #       f'NativeWindow事件查询: {perf_timings["find_nativewindow_events_done"]*1000:.2f}ms | '
    #       f'匹配应用帧: {perf_timings["match_frames_done"]*1000:.2f}ms | '
    #       f'查找应用帧(累计): {perf_timings.get("find_app_frames", 0)*1000:.2f}ms')

    if best_match:
        app_frame = best_match['app_frame']

        # 计算CPU浪费
        cpu_waste = calculate_app_frame_cpu_waste(
            trace_conn=trace_conn,
            perf_conn=perf_conn,
            app_frame=app_frame,
            perf_sample_cache=perf_sample_cache,
            perf_timestamp_field=perf_timestamp_field,
            tid_to_info_cache=tid_to_info_cache,
        )
        app_frame['cpu_waste'] = cpu_waste

        return {
            'rs_frame': {
                'frame_id': frame_id,
                'ts': frame_ts,
                'dur': frame_dur,
                'flag': frame_flag,
                'vsync': frame_vsync,
            },
            'app_frame': app_frame,
            'trace_method': 'time_window_matching',
            'rs_event': best_match['rs_event'],
            'time_diff_ms': best_time_diff,
        }
    return {
        'rs_frame': {'frame_id': frame_id, 'ts': frame_ts, 'dur': frame_dur, 'flag': frame_flag, 'vsync': frame_vsync},
        'app_frame': None,
        'trace_method': None,
        'error': '所有时间窗口匹配都失败',
    }


def main():
    parser = argparse.ArgumentParser(description='从RS skip帧追溯到应用进程提交的帧（NativeWindow API流程）')
    parser.add_argument('trace_db', help='trace数据库路径')
    parser.add_argument('--rs-frame-id', type=int, help='RS帧ID（frame_slice.rowid）')
    parser.add_argument('--verbose', '-v', action='store_true', help='详细输出')

    args = parser.parse_args()

    if args.verbose:
        logger.setLevel(logging.DEBUG)

    # 连接数据库
    try:
        conn = sqlite3.connect(args.trace_db)
    except Exception as e:
        logger.error(f'无法连接数据库: {e}')
        sys.exit(1)

    if args.rs_frame_id:
        # 获取RS帧信息以确定时间范围
        cursor = conn.cursor()
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
            caches = preload_caches(conn, min_ts, max_ts)

        # 追溯单个RS帧
        nativewindow_events_cache = caches.get('nativewindow_events') if caches else None
        app_frames_cache = caches.get('app_frames') if caches else None
        result = trace_rs_skip_to_app_frame(
            conn,
            args.rs_frame_id,
            nativewindow_events_cache=nativewindow_events_cache,
            app_frames_cache=app_frames_cache,
        )

        if result:
            print(f'\n{"=" * 100}')
            print('追溯结果')
            print(f'{"=" * 100}\n')

            rs_frame = result['rs_frame']
            print('RS帧:')
            print(f'  帧ID: {rs_frame["frame_id"]}')
            print(f'  时间: {rs_frame["ts"]} ns ({rs_frame["ts"] / 1_000_000:.2f} ms)')
            print(f'  持续时间: {rs_frame["dur"]} ns ({rs_frame["dur"] / 1_000_000:.2f} ms)')
            print(f'  Flag: {rs_frame["flag"]}')
            print(f'  VSync: {rs_frame["vsync"]}')

            if result.get('rs_event'):
                rs_event = result['rs_event']
                print('\nRS事件:')
                print(f'  名称: {rs_event["name"]}')
                print(f'  时间: {rs_event["ts"]} ns ({rs_event["ts"] / 1_000_000:.2f} ms)')
                print(f'  线程: {rs_event["thread_name"]}')

            app_frame = result.get('app_frame')
            if app_frame:
                print('\n应用帧:')
                print(f'  帧ID: {app_frame["frame_id"]}')
                print(f'  时间: {app_frame["ts"]} ns ({app_frame["ts"] / 1_000_000:.2f} ms)')
                print(f'  持续时间: {app_frame["dur"]} ns ({app_frame["dur"] / 1_000_000:.2f} ms)')
                print(f'  Flag: {app_frame["flag"]}')
                print(f'  VSync: {app_frame["vsync"]}')
                print(f'  进程: {app_frame["process_name"]} (PID: {app_frame["process_pid"]})')
                print(f'  线程: {app_frame["thread_name"]}')
                print(f'  时间差: {app_frame["time_diff_ms"]:.2f} ms')
                print(f'\n追溯方法: {result["trace_method"]}')
            else:
                print('\n未找到应用帧')
                if result.get('error'):
                    print(f'错误: {result["error"]}')
        else:
            print('追溯失败')
    else:
        print('请指定 --rs-frame-id 参数')

    conn.close()


if __name__ == '__main__':
    main()
