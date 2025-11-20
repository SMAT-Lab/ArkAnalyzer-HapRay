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
from typing import Any


class MemoryDataLoader:
    """内存数据加载器

    负责从 trace.db 数据库中加载所有必要的内存分析数据：
    1. Native Hook 事件
    2. 进程信息
    3. 线程信息
    4. 数据字典（符号和文件名）
    5. Trace 起始时间

    注意：内存数据从 trace.htrace 转换的 trace.db 中获取，不再使用单独的 memory.db
    """

    @staticmethod
    def has_native_hook_data(db_path: str) -> bool:
        """检查数据库中是否存在 native_hook 表且有数据

        Args:
            db_path: 数据库路径

        Returns:
            如果 native_hook 表存在且有数据返回 True，否则返回 False
        """
        conn = None
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            # 检查 native_hook 表是否存在
            cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='native_hook'
            """)

            if not cursor.fetchone():
                logging.info('native_hook table does not exist in database: %s', db_path)
                return False

            # 检查表中是否有数据
            cursor.execute('SELECT COUNT(*) FROM native_hook')
            count = cursor.fetchone()[0]

            if count == 0:
                logging.info('native_hook table is empty in database: %s', db_path)
                return False

            logging.info('Found %d records in native_hook table: %s', count, db_path)
            return True

        except Exception as e:
            logging.warning('Failed to check native_hook table in %s: %s', db_path, str(e))
            return False
        finally:
            if conn:
                conn.close()

    @staticmethod
    def load_all_data(db_path: str, app_pids: list) -> dict[str, Any]:
        """加载所有内存分析所需的数据

        Args:
            db_path: trace.db 数据库路径（包含 native_hook 数据）

        Returns:
            包含所有数据的字典
        """
        conn = None
        try:
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row

            data = {
                'events': MemoryDataLoader._query_native_hook_events(conn, app_pids),
                'processes': MemoryDataLoader._query_processes(conn),
                'threads': MemoryDataLoader._query_threads(conn),
                'sub_type_names': MemoryDataLoader._query_sub_type_names(conn),
                'data_dict': MemoryDataLoader._query_data_dict(conn),
                'trace_start_ts': MemoryDataLoader._query_trace_start_ts(conn),
                'callchains': MemoryDataLoader.query_all_callchain(conn),
            }

            logging.info(
                'Loaded memory data: %d events, %d processes, %d threads',
                len(data['events']),
                len(data['processes']),
                len(data['threads']),
            )

            return data

        except Exception as e:
            logging.error('Failed to load memory data: %s', str(e))
            raise
        finally:
            if conn:
                conn.close()

    @staticmethod
    def _query_native_hook_events(conn: sqlite3.Connection, app_pids: list) -> list[dict]:
        """查询 native_hook 表中的事件，仅包含 pid 属于 app_pids 的进程

        当 app_pids 为空时返回空列表。
        """
        if not app_pids:
            return []

        placeholders = ','.join(['?'] * len(app_pids))
        sql = f"""
            SELECT
                nh.id, nh.callchain_id, nh.ipid, nh.itid, nh.event_type, nh.sub_type_id,
                nh.start_ts, nh.end_ts, nh.dur, nh.addr, nh.heap_size,
                nh.last_lib_id, nh.last_symbol_id
            FROM native_hook AS nh
            JOIN process AS p ON nh.ipid = p.ipid
            WHERE p.pid IN ({placeholders})
            ORDER BY nh.start_ts
        """
        cursor = conn.cursor()
        cursor.execute(sql, app_pids)

        events = []
        for row in cursor.fetchall():
            events.append(
                {
                    'id': row[0],
                    'callchain_id': row[1],
                    'ipid': row[2],
                    'itid': row[3],
                    'event_type': row[4],
                    'sub_type_id': row[5],
                    'start_ts': row[6],
                    'end_ts': row[7],
                    'dur': row[8],
                    'addr': row[9],
                    'heap_size': row[10],
                    'last_lib_id': row[11],
                    'last_symbol_id': row[12],
                }
            )

        return events

    @staticmethod
    def _query_processes(conn: sqlite3.Connection) -> list[dict]:
        """查询进程信息"""
        cursor = conn.cursor()
        cursor.execute('SELECT id, ipid, pid, name FROM process')

        processes = []
        for row in cursor.fetchall():
            processes.append(
                {
                    'id': row[0],
                    'ipid': row[1],
                    'pid': row[2],
                    'name': row[3],
                }
            )

        return processes

    @staticmethod
    def _query_threads(conn: sqlite3.Connection) -> list[dict]:
        """查询线程信息"""
        cursor = conn.cursor()
        cursor.execute('SELECT id, itid, tid, name, ipid FROM thread')

        threads = []
        for row in cursor.fetchall():
            threads.append(
                {
                    'id': row[0],
                    'itid': row[1],
                    'tid': row[2],
                    'name': row[3],
                    'ipid': row[4],
                }
            )

        return threads

    @staticmethod
    def _query_sub_type_names(conn: sqlite3.Connection) -> dict[int, str]:
        """查询 sub_type 名称映射

        从 data_dict 表中读取所有 sub_type_id 对应的名称
        注意：data_dict 表的字段是 (id, data)，不是 (id, value)
        """
        cursor = conn.cursor()

        # 检查 data_dict 表是否存在
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='data_dict'
        """)

        if not cursor.fetchone():
            logging.warning('data_dict table does not exist in database')
            return {}

        # 获取所有在 native_hook 表中使用的 sub_type_id
        cursor.execute("""
            SELECT DISTINCT sub_type_id
            FROM native_hook
            WHERE sub_type_id IS NOT NULL
        """)

        sub_type_ids = [row[0] for row in cursor.fetchall()]

        if not sub_type_ids:
            logging.info('No sub_type_id found in native_hook table')
            return {}

        # 从 data_dict 表中查询这些 id 对应的值
        placeholders = ','.join(['?'] * len(sub_type_ids))
        cursor.execute(f'SELECT id, data FROM data_dict WHERE id IN ({placeholders})', sub_type_ids)

        sub_type_map = {}
        for row in cursor.fetchall():
            dict_id = row[0]
            data_value = row[1]
            # 只保留非空的值
            if data_value and data_value.strip():
                sub_type_map[dict_id] = data_value

        logging.info('Loaded %d sub_type names from data_dict', len(sub_type_map))

        return sub_type_map

    @staticmethod
    def _query_data_dict(conn: sqlite3.Connection) -> dict[int, str]:
        """查询 data_dict 表（符号和文件名）"""
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT DISTINCT nhf.symbol_id, nhf.file_id
            FROM native_hook_frame AS nhf
            WHERE nhf.callchain_id IN (
                SELECT callchain_id FROM native_hook
            )
            """
        )

        used_ids: set[int] = set()
        for symbol_id, file_id in cursor.fetchall():
            if symbol_id is not None and symbol_id >= 0:
                used_ids.add(symbol_id)
            if file_id is not None and file_id >= 0:
                used_ids.add(file_id)

        if not used_ids:
            return {}

        data_dict: dict[int, str] = {}
        ids_list = list(used_ids)

        # SQLite 单条查询的占位符数量有限，分批查询确保安全
        chunk_size = 500
        for start in range(0, len(ids_list), chunk_size):
            chunk = ids_list[start : start + chunk_size]
            placeholders = ','.join(['?'] * len(chunk))
            cursor.execute(
                f'SELECT id, data FROM data_dict WHERE id IN ({placeholders})',
                chunk,
            )
            for row in cursor.fetchall():
                data_dict[row[0]] = row[1]

        return data_dict

    @staticmethod
    def _query_trace_start_ts(conn: sqlite3.Connection) -> int:
        """查询 trace_range 的 start_ts"""
        cursor = conn.cursor()
        cursor.execute('SELECT start_ts FROM trace_range LIMIT 1')

        row = cursor.fetchone()
        return row[0] if row else 0

    @staticmethod
    def query_callchain_frames(conn: sqlite3.Connection, callchain_id: int) -> list[dict]:
        """查询指定调用链的所有帧

        Args:
            conn: 数据库连接
            callchain_id: 调用链 ID

        Returns:
            调用链帧列表，按 depth 排序
        """
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT
                id, callchain_id, depth, ip, symbol_id, file_id,
                offset, symbol_offset, vaddr
            FROM native_hook_frame
            WHERE callchain_id = ?
            ORDER BY depth
        """,
            (callchain_id,),
        )

        frames = []
        for row in cursor.fetchall():
            frames.append(
                {
                    'id': row[0],
                    'callchain_id': row[1],
                    'depth': row[2],
                    'ip': row[3],
                    'symbol_id': row[4],
                    'file_id': row[5],
                    'offset': row[6],
                    'symbol_offset': row[7],
                    'vaddr': row[8],
                }
            )

        return frames

    @staticmethod
    def query_all_callchain(conn: sqlite3.Connection) -> list[dict]:
        """查询指定调用链的所有帧

        Args:
            conn: 数据库连接

        Returns:
            调用链帧列表，按 depth 排序
        """
        cursor = conn.cursor()
        cursor.execute(
            """
                SELECT id, callchain_id, depth, ip, symbol_id, file_id,
                    offset, symbol_offset, vaddr
                FROM native_hook_frame
                WHERE callchain_id in (select callchain_id from native_hook)
                ORDER BY callchain_id, depth
            """,
        )

        callchain = []
        for row in cursor.fetchall():
            callchain.append(
                {
                    'id': row[0],
                    'callchain_id': row[1],
                    'depth': row[2],
                    'ip': row[3],
                    'symbol_id': row[4],
                    'file_id': row[5],
                    'offset': row[6],
                    'symbol_offset': row[7],
                    'vaddr': row[8],
                }
            )

        return callchain

    @staticmethod
    def query_callchain_by_id(conn: sqlite3.Connection, callchain_id: int) -> list[dict]:
        """查询指定callchain_id的所有帧

        Args:
            conn: 数据库连接
            callchain_id: 调用链ID

        Returns:
            调用链帧列表，按 depth 排序
        """
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, callchain_id, depth, ip, symbol_id, file_id,
                offset, symbol_offset, vaddr
            FROM native_hook_frame
            WHERE callchain_id = ?
            ORDER BY depth
        """,
            (callchain_id,),
        )

        frames = []
        for row in cursor.fetchall():
            frames.append(
                {
                    'id': row[0],
                    'callchain_id': row[1],
                    'depth': row[2],
                    'ip': row[3],
                    'symbol_id': row[4],
                    'file_id': row[5],
                    'offset': row[6],
                    'symbol_offset': row[7],
                    'vaddr': row[8],
                }
            )

        return frames
