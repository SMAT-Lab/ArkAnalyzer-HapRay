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

按所有线程做唤醒链分析（供 thread_analyzer 使用）。
按 docs/des_table.md：perf_sample.thread_id 与 perf_thread.thread_id 关联，必须通过 perf_thread 映射后再查 callchain。
"""

import logging
import os
import sqlite3
import traceback
from typing import Optional

from hapray.core.common.frame.frame_core_load_calculator import calculate_thread_instructions
from hapray.core.common.frame.frame_utils import is_system_thread
from hapray.core.common.frame.frame_wakeup_chain import (
    _check_perf_sample_has_data,
    find_wakeup_chain,
    map_itid_to_perf_thread_id,
)

logger = logging.getLogger(__name__)


def _build_perf_thread_id_map(perf_conn, app_pids: list) -> tuple:
    """按 des_table.md：perf_sample.thread_id = perf_thread.thread_id。
    建立 (process_id, thread_id) -> perf_thread.thread_id 与 (process_id, thread_name) -> perf_thread.thread_id；
    并返回该进程下所有 perf thread_id 集合，用于回退：trace.tid 直接等于 perf_thread.thread_id 时可用。"""
    pid_tid_to_perf_tid = {}
    pid_name_to_perf_tid = {}
    valid_perf_tids_by_pid = {}  # process_id -> set(thread_id)
    if not perf_conn or not app_pids:
        return pid_tid_to_perf_tid, pid_name_to_perf_tid, valid_perf_tids_by_pid
    try:
        cur = perf_conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='perf_thread'")
        if not cur.fetchone():
            return pid_tid_to_perf_tid, pid_name_to_perf_tid, valid_perf_tids_by_pid
        ph = ','.join('?' * len(app_pids))
        cur.execute(
            f"SELECT thread_id, process_id, thread_name FROM perf_thread WHERE process_id IN ({ph})",
            list(app_pids),
        )
        for thread_id, process_id, thread_name in cur.fetchall():
            pid_tid_to_perf_tid[(process_id, thread_id)] = thread_id
            if thread_name is not None and str(thread_name).strip():
                pid_name_to_perf_tid[(process_id, str(thread_name).strip())] = thread_id
            valid_perf_tids_by_pid.setdefault(process_id, set()).add(thread_id)
        return pid_tid_to_perf_tid, pid_name_to_perf_tid, valid_perf_tids_by_pid
    except Exception as e:
        logger.debug('build perf_thread id map: %s', e)
        return pid_tid_to_perf_tid, pid_name_to_perf_tid, valid_perf_tids_by_pid


def _query_thread_states_batch(trace_conn, itids_list: list, range_start: int, range_end: int) -> dict:
    """查 thread_state。des_table：thread_state.itid = thread.id，此处仍用 itid 列表查（兼容 itid 与 id 一致或库用 itid 存 thread.id 的情况）。"""
    if not itids_list:
        return {}
    out = {}
    try:
        cur = trace_conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='thread_state'")
        if not cur.fetchone():
            return out
        ph = ','.join('?' * len(itids_list))
        cur.execute(
            f"""
            SELECT itid, ts, COALESCE(dur, 0), state
            FROM thread_state
            WHERE itid IN ({ph}) AND ts < ? AND (ts + COALESCE(dur, 0)) > ?
            ORDER BY itid, ts
            """,
            itids_list + [range_end, range_start],
        )
        for itid, ts, dur, state in cur.fetchall():
            out.setdefault(itid, []).append({'ts': ts, 'dur': dur, 'state': state or ''})
    except Exception as e:
        logger.debug('query thread_state batch: %s', e)
    return out


def _query_callchains_batch(perf_conn, tid_list: list, range_start: int, range_end: int,
                            max_callchains_per_tid: int = 50, max_frames_per_tid: int = 20) -> dict:
    """按 des_table：perf_sample.callchain_id 关联 perf_callchain.callchain_id；perf_callchain.symbol_id 与 perf_files.serial_id 对应。"""
    out = {t: [] for t in tid_list}
    if not perf_conn or not tid_list:
        return out
    try:
        cur = perf_conn.cursor()
        cur.execute("PRAGMA table_info(perf_sample)")
        cols = [r[1] for r in cur.fetchall()]
        ts_col = 'timestamp_trace' if 'timestamp_trace' in cols else 'timeStamp'
        ph = ','.join('?' * len(tid_list))
        cur.execute(
            f"""
            SELECT thread_id, callchain_id
            FROM perf_sample
            WHERE thread_id IN ({ph}) AND {ts_col} >= ? AND {ts_col} <= ?
            AND callchain_id IS NOT NULL
            ORDER BY thread_id, callchain_id
            """,
            list(tid_list) + [range_start, range_end],
        )
        rows = cur.fetchall()
        tid_to_chain_ids = {t: [] for t in tid_list}
        for tid, cid in rows:
            lst = tid_to_chain_ids.get(tid)
            if lst is not None and len(lst) < max_callchains_per_tid and cid not in lst:
                lst.append(cid)
        all_chain_ids = sorted(set(cid for ids in tid_to_chain_ids.values() for cid in ids))
        if not all_chain_ids:
            return out
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='perf_callchain'")
        if not cur.fetchone():
            return out
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='perf_files'")
        if not cur.fetchone():
            return out
        ph2 = ','.join('?' * len(all_chain_ids))
        cur.execute(
            f"SELECT callchain_id, depth, file_id, symbol_id, name FROM perf_callchain WHERE callchain_id IN ({ph2}) ORDER BY callchain_id, depth",
            all_chain_ids,
        )
        chain_frames = {}
        for cid, depth, file_id, symbol_id, name in cur.fetchall():
            chain_frames.setdefault(cid, []).append((depth, file_id, symbol_id, name or ''))
        file_symbol_pairs = set()
        for frames in chain_frames.values():
            for _, file_id, symbol_id, _ in frames:
                if file_id is not None or symbol_id is not None:
                    file_symbol_pairs.add((file_id, symbol_id))
        fs_map = {}
        for (file_id, symbol_id) in file_symbol_pairs:
            cur.execute(
                "SELECT symbol, path FROM perf_files WHERE file_id = ? AND serial_id = ? LIMIT 1",
                (file_id, symbol_id),
            )
            row = cur.fetchone()
            if row:
                fs_map[(file_id, symbol_id)] = (str(row[0] or '').strip(), str(row[1] or '').strip())
            elif file_id is not None:
                cur.execute("SELECT symbol, path FROM perf_files WHERE file_id = ? LIMIT 1", (file_id,))
                row = cur.fetchone()
                if row:
                    fs_map[(file_id, symbol_id)] = (str(row[0] or '').strip(), str(row[1] or '').strip())
        for tid in tid_list:
            for cid in (tid_to_chain_ids.get(tid) or [])[:max_frames_per_tid]:
                frames = chain_frames.get(cid, [])
                functions = []
                for _depth, file_id, symbol_id, name in frames:
                    symbol = (str(name) if name is not None else '').strip()
                    path = ''
                    if file_id is not None and symbol_id is not None:
                        sym_path = fs_map.get((file_id, symbol_id))
                        if sym_path:
                            symbol, path = sym_path
                    functions.append({'symbol': symbol, 'name': symbol, 'file_path': path})
                if functions:
                    out[tid].append({'functions': functions})
        return out
    except Exception as e:
        logger.debug('callchain 批量查询异常: %s', e)
        return out


def analyze_all_threads_wakeup_chain(
    trace_db_path: str,
    perf_db_path: str,
    app_pids: list = None,
    time_range: tuple = None,
    max_threads: Optional[int] = None,
) -> Optional[list]:
    """分析应用进程所有线程的唤醒链与 CPU/callchain。按 des_table 通过 perf_thread 映射 thread_id 再查 perf_sample/callchain。"""
    if not app_pids:
        logger.error('app_pids 不能为空')
        return None
    try:
        trace_conn = sqlite3.connect(trace_db_path)
        perf_conn = None
        if perf_db_path and os.path.exists(perf_db_path) and perf_db_path != trace_db_path:
            perf_conn = sqlite3.connect(perf_db_path)
        else:
            perf_conn = trace_conn
        if not _check_perf_sample_has_data(perf_conn):
            perf_conn = None
        cursor = trace_conn.cursor()
        range_start, range_end = None, None
        if time_range and len(time_range) >= 2:
            range_start, range_end = int(time_range[0]), int(time_range[1])
        if range_start is None or range_end is None:
            for tbl in ('trace_range', 'frame_slice', 'callstack_events', 'trace'):
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (tbl,))
                if cursor.fetchone():
                    try:
                        if tbl == 'trace_range':
                            cursor.execute("SELECT start_ts, end_ts FROM trace_range LIMIT 1")
                        else:
                            cursor.execute(f"SELECT min(ts), max(ts) FROM {tbl}")
                        row = cursor.fetchone()
                        if row and row[0] is not None and row[1] is not None:
                            range_start, range_end = row[0], row[1]
                            if tbl == 'frame_slice':
                                cursor.execute("SELECT max(ts + COALESCE(dur, 0)) FROM frame_slice")
                                r2 = cursor.fetchone()
                                if r2 and r2[0] is not None:
                                    range_end = max(range_end, r2[0])
                            break
                    except Exception:
                        continue
        if range_start is None or range_end is None:
            trace_conn.close()
            if perf_conn and perf_conn != trace_conn:
                perf_conn.close()
            logger.error('无法从 trace 推断时间范围，请传入 time_range')
            return None
        ph = ','.join('?' * len(app_pids))
        cursor.execute(
            f"SELECT t.itid, t.tid, t.name, p.pid, p.name FROM thread t INNER JOIN process p ON t.ipid = p.ipid WHERE p.pid IN ({ph})",
            list(app_pids),
        )
        app_threads = cursor.fetchall()
        if max_threads is not None and max_threads > 0:
            app_threads = app_threads[: max_threads]
        if not app_threads:
            trace_conn.close()
            if perf_conn and perf_conn != trace_conn:
                perf_conn.close()
            return []
        itid_to_tid_cache = {row[0]: row[1] for row in app_threads}
        pid_tid_to_perf_tid, pid_name_to_perf_tid, valid_perf_tids_by_pid = _build_perf_thread_id_map(perf_conn, list(app_pids))
        results = []
        total_threads = len(app_threads)
        progress_interval = max(1, total_threads // 20)  # 约 20 次进度
        for idx, (itid, tid, thread_name, pid, _process_name) in enumerate(app_threads, 1):
            if idx == 1 or idx % progress_interval == 0 or idx == total_threads:
                logger.info('唤醒链分析进度: %d/%d 线程', idx, total_threads)
            related_itids_ordered = find_wakeup_chain(
                trace_conn, itid, range_start, range_end, app_pid=pid
            )
            if not isinstance(related_itids_ordered, list):
                related_itids_ordered = [(itid, 0)]
            related_itids = {i for i, _ in related_itids_ordered}
            itid_to_perf = map_itid_to_perf_thread_id(
                trace_conn, perf_conn, related_itids, itid_to_tid_cache
            )
            perf_thread_ids = set(itid_to_perf.values()) if itid_to_perf else set()
            app_inst, sys_inst = {}, {}
            if perf_conn and perf_thread_ids:
                app_inst, sys_inst = calculate_thread_instructions(
                    perf_conn, trace_conn, perf_thread_ids, range_start, range_end, None, None, None
                )
            thread_instructions = {}
            for i, _ in related_itids_ordered:
                ptid = itid_to_perf.get(i) if itid_to_perf else None
                if ptid is not None:
                    thread_instructions[i] = app_inst.get(ptid, 0) or sys_inst.get(ptid, 0)
            total_instructions = thread_instructions.get(itid, 0)
            itids_list = list(related_itids)
            if not itids_list:
                itids_list = [itid]
            ph2 = ','.join('?' * len(itids_list))
            # des_table：thread_state.itid = thread.id；find_wakeup_chain 可能返回 id 或 itid，故用 id 与 itid 都能查到
            cursor.execute(
                f"SELECT t.id, t.itid, t.tid, t.name, p.pid, p.name FROM thread t INNER JOIN process p ON t.ipid = p.ipid WHERE t.itid IN ({ph2}) OR t.id IN ({ph2})",
                itids_list + itids_list,
            )
            thread_info_map = {}
            for row in cursor.fetchall():
                id_val, itid_val, tid_val, name_val, pid_val, pname = row[0], row[1], row[2], row[3], row[4], row[5]
                info = {'tid': tid_val, 'thread_name': name_val, 'pid': pid_val, 'process_name': pname}
                thread_info_map[id_val] = info
                thread_info_map[itid_val] = info
            states_by_itid = _query_thread_states_batch(trace_conn, itids_list, range_start, range_end)
            itid_to_perf_sample_tid = {}
            for i, _ in related_itids_ordered:
                info = thread_info_map.get(i)
                if not info:
                    continue
                pid_i, tid_i, name_i = info.get('pid'), info.get('tid'), (info.get('thread_name') or '').strip()
                perf_tid = (
                    pid_tid_to_perf_tid.get((pid_i, tid_i))
                    or pid_name_to_perf_tid.get((pid_i, name_i))
                    or (itid_to_perf.get(i) if itid_to_perf else None)
                    or (tid_i if (pid_i is not None and tid_i is not None and tid_i in valid_perf_tids_by_pid.get(pid_i, set())) else None)
                )
                if perf_tid is not None:
                    itid_to_perf_sample_tid[i] = perf_tid
            tids_for_callchain = [itid_to_perf_sample_tid[i] for i, _ in related_itids_ordered if i in itid_to_perf_sample_tid]
            callchains_by_tid = {}
            if perf_conn and tids_for_callchain:
                try:
                    callchains_by_tid = _query_callchains_batch(perf_conn, tids_for_callchain, range_start, range_end)
                    n_fetched = sum(len(v) for v in callchains_by_tid.values())
                    if n_fetched:
                        logger.info('callchain 查询到 %s 个 perf_tid，共 %s 条', len(tids_for_callchain), n_fetched)
                except Exception as e:
                    logger.debug('callchain 批量查询异常: %s', e)
            wakeup_threads = []
            for i, depth in related_itids_ordered:
                info = thread_info_map.get(i)
                if not info:
                    continue
                ptid = itid_to_perf.get(i) if itid_to_perf else None
                inst = thread_instructions.get(i, 0) if ptid else 0
                thread_states = states_by_itid.get(i, [])
                perf_sample_tid = itid_to_perf_sample_tid.get(i)
                callchains = callchains_by_tid.get(perf_sample_tid, []) if perf_sample_tid is not None else []
                wakeup_threads.append({
                    'itid': i, 'tid': info['tid'], 'thread_name': info['thread_name'],
                    'pid': info['pid'], 'process_name': info['process_name'],
                    'instruction_count': inst,
                    'is_system_thread': is_system_thread(info.get('process_name', ''), info.get('thread_name', '')),
                    'wakeup_depth': depth,
                    'thread_states': thread_states,
                    'callchains': callchains,
                })
            ti = thread_info_map.get(itid) or {}
            results.append({
                'thread_id': tid,
                'thread_info': {
                    'thread_name': thread_name or '',
                    'start_ts': ti.get('start_ts'),
                    'end_ts': ti.get('end_ts'),
                },
                'total_instructions': total_instructions,
                'wakeup_threads': wakeup_threads,
            })
        trace_conn.close()
        if perf_conn and perf_conn != trace_conn:
            perf_conn.close()
        return results
    except Exception as e:
        logger.error('analyze_all_threads_wakeup_chain: %s', e)
        traceback.print_exc()
        return None


def print_thread_results(results: list, top_n: int = 10, framework_name: str = '') -> None:
    """打印线程指令数 Top N。"""
    if not results:
        return
    sorted_results = sorted(results, key=lambda x: x.get('total_instructions', 0), reverse=True)
    logger.info("前 %d 个线程（按 total_instructions 降序）:", top_n)
    for idx, r in enumerate(sorted_results[:top_n], 1):
        ti = r.get('thread_info', {})
        name = ti.get('thread_name', '')
        tid = r.get('thread_id', 'N/A')
        inst = r.get('total_instructions', 0)
        n_wt = len(r.get('wakeup_threads', []))
        logger.info("  [%d] %s (TID: %s)  指令数: %s  相关线程数: %s", idx, name, tid, f"{inst:,}", n_wt)
