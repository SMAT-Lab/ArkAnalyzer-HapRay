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

import contextlib
import os
import sqlite3
from collections import defaultdict
from statistics import mean
from typing import Any, Optional

from hapray.analyze.base_analyzer import BaseAnalyzer

# 哪些事件认为是"请求端"，哪些是"响应端"
REQUEST_EVENT_KEYWORDS = ('binder transaction async', 'binder transaction')
RESPONSE_EVENT_KEYWORDS = ('binder async rcv', 'binder reply')


class IpcBinderAnalyzer(BaseAnalyzer):
    """Analyzer for IPC binder transaction analysis"""

    def __init__(self, scene_dir: str):
        super().__init__(scene_dir, 'trace/ipc_binder')

    def _analyze_impl(
        self, step_dir: str, trace_db_path: str, perf_db_path: str, app_pids: list
    ) -> Optional[dict[str, Any]]:
        """Analyze IPC binder transactions for a single step.

        Args:
            step_dir: Identifier for the current step
            trace_db_path: Path to trace database
            perf_db_path: Path to performance database (not used in this analyzer)
            app_pids: List of application process IDs, used to filter transactions (only transactions
                     where caller or callee pid is in app_pids will be analyzed)

        Returns:
            Dictionary containing IPC binder analysis result for this step, or None if no data
        """
        if not os.path.exists(trace_db_path):
            self.logger.warning('Trace database not found: %s', trace_db_path)
            return None

        try:
            conn = sqlite3.connect(trace_db_path)
            conn.row_factory = sqlite3.Row

            # 1. 从 data_dict 自动解析字段名
            id_to_name = self._load_data_dict(conn)
            key_txn_id = 'transaction id'

            # 2. 加载进程/线程映射
            self.logger.info('加载进程/线程映射...')
            proc_by_pid, thread_by_id, thread_by_tid = self._load_process_and_thread_maps(conn)
            self.logger.info('加载了 %d 个进程, %d 个线程', len(proc_by_pid), len(thread_by_id))

            # 3. 加载 binder 事件（如果提供了 app_pids，则只加载相关事件）
            self.logger.info('加载 binder 事件...')
            events = self._load_binder_events(conn, id_to_name, thread_by_id, app_pids)
            self.logger.info('总共 binder 事件数: %d', len(events))

            if not events:
                conn.close()
                return None

            # 4. 按 transaction id 聚合成通信记录
            self.logger.info('按 transaction id 配对通信记录...')
            transactions = self._build_transactions(events, key_txn_id)
            self.logger.info('推导出通信记录条数: %d', len(transactions))

            if not transactions:
                conn.close()
                return None

            # 5. 补充进程/线程信息并计算耗时
            self.logger.info('补充进程/线程信息并计算耗时（使用 callid 关联 thread 表，并解析 data_dict）...')
            enriched = self._enrich_with_proc_thread_info(
                transactions,
                thread_by_id,
                thread_by_tid,
                proc_by_pid,
                id_to_name=id_to_name,
            )

            # 6. 做聚合统计（按进程，耗时单位：毫秒）
            self.logger.info('开始聚合统计...')
            process_agg = self._aggregate_stats(enriched)
            self.logger.info('进程对统计完成，共 %d 条记录', len(process_agg))

            thread_agg = self._aggregate_by_thread(enriched)
            self.logger.info('线程对统计完成，共 %d 条记录', len(thread_agg))

            interface_agg = self._aggregate_by_interface(enriched)
            self.logger.info('接口统计完成，共 %d 条记录', len(interface_agg))

            conn.close()

            # 构建返回结果
            return {
                'process_stats': process_agg,
                'thread_stats': thread_agg,
                'interface_stats': interface_agg,
            }

        except Exception as e:
            self.logger.error('IPC binder analysis failed: %s', str(e))
            return None

    def _load_data_dict(self, conn):
        """
        读取 data_dict，构造:
          - id_to_name:  {id -> data文本}
        """
        cur = conn.cursor()
        cur.execute('SELECT id, data FROM data_dict')
        id_to_name = {}
        for row in cur.fetchall():
            id_to_name[row['id']] = row['data']
        return id_to_name

    def _load_process_and_thread_maps(self, conn):
        """
        加载进程/线程映射表，便于把 pid/tid 转成名字。
        返回:
          - proc_by_pid:  {pid -> {name, ipid}}
          - thread_by_id: {thread.id -> {tid, name, ipid, proc_pid, proc_name}}
          - thread_by_tid: {tid -> 同上}
        """
        proc_by_pid = {}
        proc_by_ipid = {}
        cur = conn.cursor()
        cur.execute('SELECT pid, name, ipid FROM process')
        for row in cur.fetchall():
            pid = row['pid']
            name = row['name']
            ipid = row['ipid']
            proc_by_pid[pid] = {'name': name, 'ipid': ipid}
            if ipid is not None:
                proc_by_ipid[ipid] = {'pid': pid, 'name': name}

        # thread_by_id: 通过 thread.id (即 callstack.callid) 查找线程信息
        thread_by_id = {}
        # thread_by_tid: 通过 thread.tid 查找线程信息（保留作为备用）
        thread_by_tid = {}
        cur.execute('SELECT id, tid, name, ipid FROM thread')
        for row in cur.fetchall():
            thread_id = row['id']
            tid = row['tid']
            name = row['name']
            ipid = row['ipid']
            proc_info = proc_by_ipid.get(ipid, {}) if ipid is not None else {}
            thread_by_id[thread_id] = {
                'tid': tid,
                'name': name,
                'ipid': ipid,
                'proc_pid': proc_info.get('pid'),
                'proc_name': proc_info.get('name'),
            }
            if tid is not None:
                thread_by_tid[tid] = {
                    'id': thread_id,
                    'name': name,
                    'ipid': ipid,
                    'proc_pid': proc_info.get('pid'),
                    'proc_name': proc_info.get('name'),
                }

        return proc_by_pid, thread_by_id, thread_by_tid

    def _load_binder_events(self, conn, id_to_name, thread_by_id=None, app_pids=None):
        """
        读取所有 binder 相关 callstack 事件及其 args。
        如果提供了 app_pids，则只加载与这些进程相关的事件（通过 callid 关联到进程）。

        Args:
            conn: 数据库连接
            id_to_name: 数据字典映射
            thread_by_id: 线程映射字典，用于通过 callid 查找进程
            app_pids: 应用进程 ID 列表，如果提供则只加载相关事件

        Returns:
            dict[call_id] = { id, ts, dur, name, cat, callid, args: {key: (value, datatype)} }
        注意: callid 对应 thread.id，用于关联线程和进程信息
        """
        cur = conn.cursor()

        # 如果提供了 app_pids，构建过滤条件
        app_pids_set = set(app_pids) if app_pids else None

        # 如果提供了 app_pids，先找出相关的 thread.id 集合
        relevant_thread_ids = None
        if app_pids_set and thread_by_id:
            relevant_thread_ids = set()
            for thread_id, thread_info in thread_by_id.items():
                proc_pid = thread_info.get('proc_pid')
                if proc_pid in app_pids_set:
                    relevant_thread_ids.add(thread_id)
            self.logger.info('找到 %d 个与 app_pids 相关的线程', len(relevant_thread_ids))

        cur.execute("""
            SELECT
              c.id,
              c.ts,
              c.dur,
              c.name,
              c.cat,
              c.callid,
              a.key,
              a.value,
              a.datatype
            FROM callstack AS c
            LEFT JOIN args AS a
              ON c.argsetid = a.argset
            WHERE c.name LIKE '%binder%'
        """)

        events = {}
        filtered_count = 0
        total_count = 0
        # 临时存储每个事件的 args，用于后续过滤判断
        event_args_temp = {}

        for row in cur.fetchall():
            total_count += 1
            call_id = row['id']
            callid = row['callid']

            # 先收集所有 args 信息
            if call_id not in events:
                events[call_id] = {
                    'id': call_id,
                    'ts': row['ts'],
                    'dur': row['dur'],
                    'name': row['name'],
                    'cat': row['cat'],
                    'callid': callid,
                    'args': {},
                }
                event_args_temp[call_id] = {}
            ev = events[call_id]
            args_temp = event_args_temp[call_id]

            key = row['key']
            if key is not None:
                key_name = id_to_name.get(key)
                if key_name is None:
                    continue

                value = row['value']
                datatype = row['datatype']

                value_parsed = id_to_name.get(value, value) if datatype == 1 else value

                args_temp[key_name] = value_parsed

                # 安全解析 code 字段：支持 "0x0 Java Layer Dependent" 这类格式，
                # 仅提取前面形如 0x.. 的部分尝试按 16 进制转换，失败则保持原值。
                if key_name == 'code':
                    text = str(value_parsed).strip()
                    first_part = text.split()[0] if text else ''
                    if first_part.startswith('0x'):
                        with contextlib.suppress(ValueError):
                            # 解析失败则不修改原始字符串，避免抛异常
                            value_parsed = int(first_part, 16)

                ev['args'][key_name] = value_parsed

        # 如果提供了 app_pids，进行过滤
        if app_pids_set and relevant_thread_ids is not None:
            events_to_remove = []
            for call_id, ev in events.items():
                callid = ev.get('callid')
                ev.get('name', '').lower()
                args = event_args_temp.get(call_id, {})

                # 检查事件是否与 app_pids 相关
                is_relevant = False

                # 1. 检查 callid 对应的进程是否在 app_pids 中
                if callid is not None and callid in relevant_thread_ids:
                    is_relevant = True

                # 2. 对于响应事件，检查 destination process 是否在 app_pids 中
                if not is_relevant:
                    dest_process = args.get('destination process')
                    if dest_process is not None and dest_process in app_pids_set:
                        is_relevant = True

                # 3. 对于请求事件，检查 calling tid 对应的进程是否在 app_pids 中
                if not is_relevant and thread_by_id:
                    calling_tid = args.get('calling tid')
                    if calling_tid is not None:
                        # 通过 tid 查找线程，再查找进程
                        for _, thread_info in thread_by_id.items():
                            if thread_info.get('tid') == calling_tid:
                                if thread_info.get('proc_pid') in app_pids_set:
                                    is_relevant = True
                                break

                if not is_relevant:
                    events_to_remove.append(call_id)
                    filtered_count += 1

            # 移除不相关的事件
            for call_id in events_to_remove:
                del events[call_id]

            self.logger.info(
                '过滤后保留 %d/%d 个 binder 事件（过滤掉 %d 个）',
                len(events),
                total_count,
                filtered_count,
            )

        return events

    def _classify_event(self, ev):
        """根据 name 判断是请求侧还是响应侧 / 或其他。"""
        name = ev['name'] or ''
        lname = name.lower()
        role = 'other'
        for kw in REQUEST_EVENT_KEYWORDS:
            if kw in lname:
                role = 'request'
                break
        for kw in RESPONSE_EVENT_KEYWORDS:
            if kw in lname:
                # 响应关键字优先覆盖
                role = 'response'
                break
        return role

    def _build_transactions(self, events, key_txn_id):
        """
        根据事务号把事件配对成通信记录。
        返回:
          txns: list[dict]，每个 dict 描述一条通信记录（含发起/接收事件）
        """
        tx_groups = defaultdict(list)
        # 记录缺少 transaction id 的事件，便于后续排查
        no_txn_event = []

        for ev in events.values():
            args = ev['args']
            txn_id = args.get(key_txn_id) if args else None
            if txn_id is None:
                no_txn_event.append(ev)
                continue
            tx_groups[txn_id].append(ev)

        transactions = []
        for transaction_id, ev_list in tx_groups.items():
            requests = [e for e in ev_list if self._classify_event(e) == 'request']
            responses = [e for e in ev_list if self._classify_event(e) == 'response']

            if not requests and not responses:
                continue

            req = min(requests, key=lambda e: e['ts']) if requests else None
            rsp = max(responses, key=lambda e: e['ts']) if responses else None

            transactions.append(
                {
                    'transaction_id': transaction_id,
                    'request_event': req,
                    'response_event': rsp,
                }
            )

        if no_txn_event:
            self.logger.warning(
                '共 %d 条 binder 事件缺少 transaction id，对应 callstack.id 列表示例（前 50 条）',
                len(no_txn_event),
            )
            self.logger.debug('缺少 transaction id 的事件示例: %s', [e['id'] for e in no_txn_event[:50]])

        return transactions

    def _enrich_with_proc_thread_info(
        self,
        transactions,
        thread_by_id,
        thread_by_tid,
        proc_by_pid,
        id_to_name=None,
    ):
        """
        为每条通信补充：
          - 发起/接收的 tid/pid 以及进程名/线程名；
          - caller 和 callee 的 args 字典（包含 code 等信息）。

        优先使用 callstack.callid -> thread.id 来获取线程和进程信息（更准确）。
        如果 callid 不可用，则回退到使用 args 中的 calling tid / destination thread。
        """
        enriched = []

        def extract_from_callid(ev, thread_by_id):
            """
            通过 callid (对应 thread.id) 获取线程和进程信息。
            这是最准确的方式。
            """
            if ev is None:
                return {'pid': None, 'tid': None, 'proc_name': None, 'thread_name': None, 'ipid': None}

            callid = ev.get('callid')
            if callid is not None:
                thread_info = thread_by_id.get(callid, {})
                return {
                    'pid': thread_info.get('proc_pid'),
                    'tid': thread_info.get('tid'),
                    'proc_name': thread_info.get('proc_name'),
                    'thread_name': thread_info.get('name'),
                    'ipid': thread_info.get('ipid'),
                }
            return {'pid': None, 'tid': None, 'proc_name': None, 'thread_name': None, 'ipid': None}

        def extract_from_args(ev, thread_by_tid, proc_by_pid, is_request=True):
            """
            从 args 中提取线程/进程信息（备用方案）。
            """
            if ev is None:
                return {'pid': None, 'tid': None, 'proc_name': None, 'thread_name': None}

            args = ev['args'] or {}
            if is_request:
                # 请求端：使用 calling tid
                tid = args.get('calling tid')
                thread = thread_by_tid.get(tid, {}) if tid is not None else {}
                pid = thread.get('proc_pid')
                return {
                    'pid': pid,
                    'tid': tid,
                    'proc_name': thread.get('proc_name'),
                    'thread_name': thread.get('name'),
                }
            # 响应端：优先使用 destination thread，其次 destination process
            tid = args.get('destination thread')
            pid = args.get('destination process')
            thread = thread_by_tid.get(tid, {}) if tid is not None else {}
            proc = proc_by_pid.get(pid, {}) if pid is not None else {}
            return {
                'pid': pid or thread.get('proc_pid'),
                'tid': tid,
                'proc_name': proc.get('name') or thread.get('proc_name'),
                'thread_name': thread.get('name'),
            }

        for tx in transactions:
            transaction_id = tx['transaction_id']
            req = tx['request_event']
            rsp = tx['response_event']

            # 优先使用 callid 方式获取信息
            caller = extract_from_callid(req, thread_by_id)
            callee = extract_from_callid(rsp, thread_by_id)

            # 如果 callid 方式没有获取到完整信息，尝试从 args 补充
            if caller.get('proc_name') is None and req is not None:
                caller_fallback = extract_from_args(req, thread_by_tid, proc_by_pid, is_request=True)
                if caller_fallback.get('proc_name'):
                    caller.update(caller_fallback)

            if callee.get('proc_name') is None and rsp is not None:
                callee_fallback = extract_from_args(rsp, thread_by_tid, proc_by_pid, is_request=False)
                if callee_fallback.get('proc_name'):
                    callee.update(callee_fallback)

            # 将事件名和参数添加到 caller 和 callee 字典中
            if req is not None:
                caller['event'] = req['name']
                caller['args'] = req.get('args') or {}
            if rsp is not None:
                callee['event'] = rsp['name']
                callee['args'] = rsp.get('args') or {}

            # 计算耗时：ts 为纳秒，这里统一换算为毫秒
            latency = (rsp['ts'] - req['ts']) / 1000000.0 if req is not None and rsp is not None else None

            enriched.append(
                {
                    'transaction_id': transaction_id,
                    'caller': caller,
                    'callee': callee,
                    'request_ts': req['ts'] if req else None,
                    'response_ts': rsp['ts'] if rsp else None,
                    'latency': latency,
                }
            )

        return enriched

    def _aggregate_stats(self, enriched_txns):
        """
        按"调用进程 -> 被调进程"做聚合统计：
          - 通信次数
          - 平均/最小/最大耗时（毫秒）
          - 调用频率（QPS：每秒调用次数）
          - 平均调用间隔（毫秒）
        """
        stats = defaultdict(list)

        for tx in enriched_txns:
            caller_proc = tx['caller']['proc_name'] or f'pid={tx["caller"]["pid"]}'
            callee_proc = tx['callee']['proc_name'] or f'pid={tx["callee"]["pid"]}'
            key = (caller_proc, callee_proc)
            if tx['latency'] is not None:
                stats[key].append(
                    {
                        'latency': tx['latency'],
                        'request_ts': tx.get('request_ts'),
                    }
                )

        agg = []
        for (caller_proc, callee_proc), items in stats.items():
            latencies = [item['latency'] for item in items]
            request_times = [item['request_ts'] for item in items if item['request_ts'] is not None]

            # 计算频率：QPS（每秒调用次数）
            qps = None
            avg_interval_ms = None
            if len(request_times) > 1:
                time_span_ns = max(request_times) - min(request_times)
                if time_span_ns > 0:
                    time_span_sec = time_span_ns / 1_000_000_000.0
                    qps = len(request_times) / time_span_sec
                    # 平均调用间隔（毫秒）
                    intervals = []
                    sorted_times = sorted(request_times)
                    for i in range(1, len(sorted_times)):
                        intervals.append((sorted_times[i] - sorted_times[i - 1]) / 1_000_000.0)
                    if intervals:
                        avg_interval_ms = mean(intervals)

            agg.append(
                {
                    'caller_proc': caller_proc,
                    'callee_proc': callee_proc,
                    'count': len(latencies),
                    'avg_latency': mean(latencies),
                    'min_latency': min(latencies),
                    'max_latency': max(latencies),
                    'qps': qps,
                    'avg_interval_ms': avg_interval_ms,
                }
            )

        agg.sort(key=lambda x: x['count'], reverse=True)
        return agg

    def _aggregate_by_thread(self, enriched_txns):
        """
        按"调用线程 -> 被调线程"做聚合统计：
          - 维度：caller_proc/caller_tid -> callee_proc/callee_tid
          - 指标：通信次数、平均/最小/最大耗时（毫秒）
          - 调用频率（QPS：每秒调用次数）
          - 平均调用间隔（毫秒）
        """
        stats = defaultdict(list)

        for tx in enriched_txns:
            caller_proc = tx['caller']['proc_name'] or f'pid={tx["caller"]["pid"]}'
            callee_proc = tx['callee']['proc_name'] or f'pid={tx["callee"]["pid"]}'
            caller_tid = tx['caller']['tid']
            callee_tid = tx['callee']['tid']
            caller_thread_name = tx['caller']['thread_name']
            callee_thread_name = tx['callee']['thread_name']
            key = (caller_proc, caller_tid, caller_thread_name, callee_proc, callee_tid, callee_thread_name)
            if tx['latency'] is not None:
                stats[key].append(
                    {
                        'latency': tx['latency'],
                        'request_ts': tx.get('request_ts'),
                    }
                )

        agg = []
        for (
            caller_proc,
            caller_tid,
            caller_thread_name,
            callee_proc,
            callee_tid,
            callee_thread_name,
        ), items in stats.items():
            latencies = [item['latency'] for item in items]
            request_times = [item['request_ts'] for item in items if item['request_ts'] is not None]

            # 计算频率：QPS（每秒调用次数）
            qps = None
            avg_interval_ms = None
            if len(request_times) > 1:
                time_span_ns = max(request_times) - min(request_times)
                if time_span_ns > 0:
                    time_span_sec = time_span_ns / 1_000_000_000.0
                    qps = len(request_times) / time_span_sec
                    # 平均调用间隔（毫秒）
                    intervals = []
                    sorted_times = sorted(request_times)
                    for i in range(1, len(sorted_times)):
                        intervals.append((sorted_times[i] - sorted_times[i - 1]) / 1_000_000.0)
                    if intervals:
                        avg_interval_ms = mean(intervals)

            agg.append(
                {
                    'caller_proc': caller_proc,
                    'caller_tid': caller_tid,
                    'caller_thread_name': caller_thread_name,
                    'callee_proc': callee_proc,
                    'callee_tid': callee_tid,
                    'callee_thread_name': callee_thread_name,
                    'count': len(latencies),
                    'avg_latency': mean(latencies),
                    'min_latency': min(latencies),
                    'max_latency': max(latencies),
                    'qps': qps,
                    'avg_interval_ms': avg_interval_ms,
                }
            )

        # 按通信次数排序
        agg.sort(key=lambda x: x['count'], reverse=True)
        return agg

    def _aggregate_by_interface(self, enriched_txns):
        """
        按接口维度（code）做聚合统计：
          - 通信次数
          - 平均/最小/最大耗时（毫秒）
          - 调用方/被调方进程信息
          - 调用频率（QPS：每秒调用次数）
          - 平均调用间隔（毫秒）
        code 从 caller_args 或 callee_args 中获取
        """
        stats = defaultdict(list)

        for tx in enriched_txns:
            # 优先从 caller.args 中取 code，如果没有则从 callee.args 中取
            code = None
            caller_args = tx.get('caller', {}).get('args') or {}
            callee_args = tx.get('callee', {}).get('args') or {}

            if 'code' in caller_args:
                code = caller_args['code']
            elif 'code' in callee_args:
                code = callee_args['code']

            # 如果 code 为 None，跳过这条记录
            if code is None:
                continue

            if tx['latency'] is not None:
                stats[code].append(
                    {
                        'latency': tx['latency'],
                        'caller_proc': tx['caller']['proc_name'] or f'pid={tx["caller"]["pid"]}',
                        'callee_proc': tx['callee']['proc_name'] or f'pid={tx["callee"]["pid"]}',
                        'request_ts': tx.get('request_ts'),
                    }
                )

        agg = []
        for code_key, items in stats.items():
            latencies = [item['latency'] for item in items]
            request_times = [item['request_ts'] for item in items if item['request_ts'] is not None]

            # 统计调用方/被调方进程分布（取最常见的）
            caller_procs = defaultdict(int)
            callee_procs = defaultdict(int)
            for item in items:
                caller_procs[item['caller_proc']] += 1
                callee_procs[item['callee_proc']] += 1

            top_caller = max(caller_procs.items(), key=lambda x: x[1])[0] if caller_procs else 'unknown'
            top_callee = max(callee_procs.items(), key=lambda x: x[1])[0] if callee_procs else 'unknown'

            # 计算频率：QPS（每秒调用次数）
            qps = None
            avg_interval_ms = None
            if len(request_times) > 1:
                time_span_ns = max(request_times) - min(request_times)
                if time_span_ns > 0:
                    time_span_sec = time_span_ns / 1_000_000_000.0
                    qps = len(request_times) / time_span_sec
                    # 平均调用间隔（毫秒）
                    intervals = []
                    sorted_times = sorted(request_times)
                    for i in range(1, len(sorted_times)):
                        intervals.append((sorted_times[i] - sorted_times[i - 1]) / 1_000_000.0)
                    if intervals:
                        avg_interval_ms = mean(intervals)

            # code 可能是整数（已解析的十六进制）或字符串
            code_repr = f'0x{code_key:x}' if isinstance(code_key, int) else str(code_key)

            agg.append(
                {
                    'code': code_repr,
                    'count': len(latencies),
                    'avg_latency': mean(latencies),
                    'min_latency': min(latencies),
                    'max_latency': max(latencies),
                    'qps': qps,
                    'avg_interval_ms': avg_interval_ms,
                    'top_caller_proc': top_caller,
                    'top_callee_proc': top_callee,
                    'caller_proc_variety': len(caller_procs),
                    'callee_proc_variety': len(callee_procs),
                }
            )

        agg.sort(key=lambda x: x['count'], reverse=True)
        return agg
