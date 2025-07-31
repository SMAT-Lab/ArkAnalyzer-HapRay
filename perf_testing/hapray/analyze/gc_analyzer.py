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
import os.path
import re
import sqlite3
from typing import Dict, Any, Optional

from hapray.analyze.base_analyzer import BaseAnalyzer


class GCAnalyzer(BaseAnalyzer):
    """
    GC线程负载 > 15%，调用次数大于10次且频率>1次/s，则判定GC异常
    """

    pattern = re.compile(r'H:(FullGC|SharedFullGC|SharedGC|PartialGC)::RunPhases')

    def __init__(self, scene_dir: str):
        super().__init__(scene_dir, 'trace/gc_thread')

    def _analyze_impl(self,
                      step_dir: str,
                      trace_db_path: str,
                      perf_db_path: str,
                      app_pids: list) -> Optional[Dict[str, Any]]:
        if not os.path.exists(trace_db_path) or not os.path.exists(perf_db_path):
            return None

        result = self._calc_gc_invoke_times(trace_db_path, app_pids)
        result['perf_percentage'] = self._calc_gc_perf(perf_db_path, app_pids)
        # GC线程负载 > 15%，则判定GC异常
        if result['perf_percentage'] > 0.15:
            result["GCStatus"] = "Too many GC"

        return result

    def _calc_gc_perf(self, perf_db_path: str, app_pids: list) -> float:
        gc_sql = f"""
            SELECT sum(event_count) as gc
            FROM perf_sample
            where thread_id in
             (select thread_id
                 from perf_thread
                 where thread_name = 'OS_GC_Thread'
                 and process_id in ({','.join('?' * len(app_pids))}))
        """

        all_sql = f"""
            SELECT sum(event_count) as total
            FROM perf_sample
            where thread_id in
             (select thread_id
                 from perf_thread
                 where process_id in ({','.join('?' * len(app_pids))}))
        """

        try:
            with sqlite3.connect(perf_db_path) as _conn:
                _conn.row_factory = sqlite3.Row
                cursor = _conn.cursor()

                cursor.execute(gc_sql, app_pids)
                row = cursor.fetchall()[0]
                gc_perf = row['gc']

                cursor.execute(all_sql, app_pids)
                row = cursor.fetchall()[0]
                total_perf = row['total']
                if total_perf == 0 or total_perf is None or gc_perf is None:
                    return 0.0

                return gc_perf * 1.0 / total_perf

        except sqlite3.Error as e:
            self.logger.error("GCAnalyzer _calc_gc_perf Database error: %s", str(e))
        return 0.0

    def _calc_gc_invoke_times(self, trace_db_path: str, app_pids: list) -> dict:
        try:
            with sqlite3.connect(trace_db_path) as _conn:
                _conn.row_factory = sqlite3.Row
                cursor = _conn.cursor()

                cursor.execute("SELECT max(ts) as end, min(ts) as start FROM callstack")
                row = cursor.fetchall()[0]
                start_time = row['start']
                end_time = row['end']
                result = {"FullGC": 0, "SharedFullGC": 0, "SharedGC": 0, "PartialGC": 0}
                # Get total component builds
                cursor.execute(f"""
                    SELECT * FROM callstack
                    WHERE
                    (name LIKE '%H:FullGC::RunPhases%'
                        or name LIKE '%H:SharedFullGC::RunPhases%'
                        or name LIKE '%H:SharedGC::RunPhases%'
                         or name like '%H:PartialGC::RunPhases%')
                    and callid in (
                        SELECT id FROM thread
                        where
                            ipid in (
                                SELECT ipid FROM process where pid in ({','.join('?' * len(app_pids))})
                                )
                        )
                """, app_pids)

                _sum = 0
                for row in cursor.fetchall():
                    gc_type = self._extract_gc_type(row["name"])
                    result[gc_type] += 1
                    _sum += 1
                # 调用次数大于10次且频率>1次/s，则判定GC异常
                gc_frequency = (end_time - start_time) / 1e9
                if _sum > gc_frequency and _sum > 10:
                    result["GCStatus"] = "Too many GC"
                else:
                    result["GCStatus"] = "OK"

        except sqlite3.Error as e:
            self.logger.error("GCAnalyzer _calc_gc_invoke_times Database error: %s", str(e))

        return result

    def _extract_gc_type(self, name) -> Optional[str]:
        match = self.pattern.search(name)
        if match:
            return match.group(1)
        return None
