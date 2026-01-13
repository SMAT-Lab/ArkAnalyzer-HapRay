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

from .memory_data_loader import MemoryDataLoader


class MemoryStatisticLoader:
    """内存统计数据加载器

    专门用于从 native_hook_statistic 表加载聚合统计数据
    当 native_hook 表没有数据时，使用此加载器作为备选方案
    """

    @staticmethod
    def has_native_hook_statistic_data(db_path: str) -> bool:
        """检查数据库中是否存在 native_hook_statistic 表且有数据

        Args:
            db_path: 数据库路径

        Returns:
            如果 native_hook_statistic 表存在且有数据返回 True，否则返回 False
        """
        conn = None
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            # 检查 native_hook_statistic 表是否存在
            cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='native_hook_statistic'
            """)

            if not cursor.fetchone():
                logging.info('native_hook_statistic table does not exist in database: %s', db_path)
                return False

            # 检查表中是否有数据
            cursor.execute('SELECT COUNT(*) FROM native_hook_statistic')
            count = cursor.fetchone()[0]

            if count == 0:
                logging.info('native_hook_statistic table is empty in database: %s', db_path)
                return False

            logging.info('Found %d records in native_hook_statistic table: %s', count, db_path)
            return True

        except Exception as e:
            logging.warning('Failed to check native_hook_statistic table in %s: %s', db_path, str(e))
            return False
        finally:
            if conn:
                conn.close()

    @staticmethod
    def load_statistic_data(db_path: str, app_pids: list) -> dict[str, Any]:
        """从 native_hook_statistic 表加载统计数据

        Args:
            db_path: trace.db 数据库路径
            app_pids: 应用进程ID列表

        Returns:
            包含统计数据的字典
        """
        conn = None
        try:
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row

            data = {
                'statistic_events': MemoryStatisticLoader._query_native_hook_statistic_events(conn, app_pids),
                'processes': MemoryDataLoader._query_processes(conn),
                'threads': MemoryDataLoader._query_threads(conn),
                'sub_type_names': MemoryStatisticLoader._query_sub_type_names_from_statistic(conn),
                'data_dict': MemoryStatisticLoader._query_data_dict_from_statistic(conn),
                'trace_start_ts': MemoryDataLoader._query_trace_start_ts(conn),
                'callchains': MemoryStatisticLoader._query_callchains_from_statistic(conn),
            }

            logging.info(
                'Loaded statistic data: %d events, %d processes, %d threads',
                len(data['statistic_events']),
                len(data['processes']),
                len(data['threads']),
            )

            return data

        except Exception as e:
            logging.error('Failed to load statistic data: %s', str(e))
            raise
        finally:
            if conn:
                conn.close()

    @staticmethod
    def _query_native_hook_statistic_events(conn: sqlite3.Connection, app_pids: list) -> list[dict]:
        """查询 native_hook_statistic 表中的统计事件

        Args:
            conn: 数据库连接
            app_pids: 应用进程ID列表

        Returns:
            统计事件列表
        """
        if not app_pids:
            logging.warning('❌ app_pids 为空，无法查询 native_hook_statistic 事件！')
            return []

        logging.info('查询 native_hook_statistic 事件，app_pids: %s', app_pids)

        placeholders = ','.join(['?'] * len(app_pids))
        sql = f"""
            SELECT
                nhs.id, nhs.callchain_id, nhs.ipid, nhs.ts, nhs.type, nhs.sub_type_id,
                nhs.apply_count, nhs.release_count, nhs.apply_size, nhs.release_size,
                nhs.last_lib_id, nhs.last_symbol_id
            FROM native_hook_statistic AS nhs
            JOIN process AS p ON nhs.ipid = p.ipid
            WHERE p.pid IN ({placeholders})
            ORDER BY nhs.ts
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
                    'ts': row[3],
                    'type': row[4],
                    'sub_type_id': row[5],
                    'apply_count': row[6],
                    'release_count': row[7],
                    'apply_size': row[8],
                    'release_size': row[9],
                    'last_lib_id': row[10],
                    'last_symbol_id': row[11],
                }
            )

        logging.info('✓ 查询到 %d 条 native_hook_statistic 统计记录', len(events))
        return events

    @staticmethod
    def _query_sub_type_names_from_statistic(conn: sqlite3.Connection) -> dict[int, str]:
        """从 native_hook_statistic 表查询 sub_type 名称映射"""
        cursor = conn.cursor()

        # 获取所有在 native_hook_statistic 表中使用的 sub_type_id
        cursor.execute("""
            SELECT DISTINCT sub_type_id
            FROM native_hook_statistic
            WHERE sub_type_id IS NOT NULL
        """)

        sub_type_ids = [row[0] for row in cursor.fetchall()]

        if not sub_type_ids:
            logging.info('No sub_type_id found in native_hook_statistic table')
            return {}

        # 从 data_dict 表中查询这些 id 对应的值
        placeholders = ','.join(['?'] * len(sub_type_ids))
        cursor.execute(f'SELECT id, data FROM data_dict WHERE id IN ({placeholders})', sub_type_ids)

        sub_type_map = {}
        for row in cursor.fetchall():
            dict_id = row[0]
            data_value = row[1]
            if data_value and data_value.strip():
                sub_type_map[dict_id] = data_value

        logging.info('Loaded %d sub_type names from data_dict', len(sub_type_map))
        return sub_type_map

    @staticmethod
    def _query_data_dict_from_statistic(conn: sqlite3.Connection) -> dict[int, str]:
        """从 native_hook_statistic 相关的调用链查询 data_dict"""
        cursor = conn.cursor()

        # 获取 native_hook_statistic 中使用的 callchain_id
        cursor.execute("""
            SELECT DISTINCT callchain_id
            FROM native_hook_statistic
            WHERE callchain_id IS NOT NULL AND callchain_id > 0
        """)

        callchain_ids = [row[0] for row in cursor.fetchall()]

        if not callchain_ids:
            logging.warning('No callchain_id found in native_hook_statistic')
            return {}

        # 查询这些调用链使用的 symbol_id 和 file_id（分批查询）
        used_ids: set[int] = set()
        chunk_size = 500
        for start in range(0, len(callchain_ids), chunk_size):
            chunk = callchain_ids[start : start + chunk_size]
            placeholders = ','.join(['?'] * len(chunk))
            cursor.execute(
                f"""
                SELECT DISTINCT nhf.symbol_id, nhf.file_id
                FROM native_hook_frame AS nhf
                WHERE nhf.callchain_id IN ({placeholders})
                """,
                chunk,
            )

            for symbol_id, file_id in cursor.fetchall():
                if symbol_id is not None and symbol_id >= 0:
                    used_ids.add(symbol_id)
                if file_id is not None and file_id >= 0:
                    used_ids.add(file_id)

        # 同时添加 native_hook_statistic 中的 last_lib_id 和 last_symbol_id
        cursor.execute("""
            SELECT DISTINCT last_lib_id, last_symbol_id
            FROM native_hook_statistic
        """)
        for lib_id, symbol_id in cursor.fetchall():
            if lib_id is not None and lib_id >= 0:
                used_ids.add(lib_id)
            if symbol_id is not None and symbol_id >= 0:
                used_ids.add(symbol_id)

        if not used_ids:
            return {}

        data_dict: dict[int, str] = {}
        ids_list = list(used_ids)

        # 分批查询
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

        logging.info('Loaded %d data_dict entries from statistic data', len(data_dict))
        return data_dict

    @staticmethod
    def _query_callchains_from_statistic(conn: sqlite3.Connection) -> list[dict]:
        """查询 native_hook_statistic 相关的调用链"""
        cursor = conn.cursor()

        # 获取所有 native_hook_statistic 中的 callchain_id
        cursor.execute("""
            SELECT DISTINCT callchain_id
            FROM native_hook_statistic
            WHERE callchain_id IS NOT NULL AND callchain_id > 0
        """)

        callchain_ids = [row[0] for row in cursor.fetchall()]

        if not callchain_ids:
            logging.info('No callchains found in native_hook_statistic')
            return []

        callchains = []

        # 分批查询，避免 SQL 变量数量超限（SQLite 默认限制 999 个变量）
        chunk_size = 500
        for start in range(0, len(callchain_ids), chunk_size):
            chunk = callchain_ids[start : start + chunk_size]
            placeholders = ','.join(['?'] * len(chunk))
            cursor.execute(
                f"""
                SELECT id, callchain_id, depth, ip, symbol_id, file_id,
                    offset, symbol_offset, vaddr
                FROM native_hook_frame
                WHERE callchain_id IN ({placeholders})
                ORDER BY callchain_id, depth
                """,
                chunk,
            )

            for row in cursor.fetchall():
                callchains.append(
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

        logging.info('Loaded %d callchain frames from statistic data', len(callchains))
        return callchains
