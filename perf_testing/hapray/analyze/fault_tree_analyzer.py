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
import re
import sqlite3
from typing import Dict, Any, Optional

from hapray.analyze.base_analyzer import BaseAnalyzer


class FaultTreeAnalyzer(BaseAnalyzer):
    """Analyzer for cold start redundant file analysis"""

    def __init__(self, scene_dir: str):
        super().__init__(scene_dir, 'trace/fault_tree')

    def _analyze_impl(self,
                      step_dir: str,
                      trace_db_path: str,
                      perf_db_path: str,
                      app_pids: list) -> Optional[Dict[str, Any]]:
        result = {
            "arkui": {
                "animator": 0,  # 帧动画多
                "HandleOnAreaChangeEvent": 0,  # 监听区域变化负载
                "HandleVisibleAreaChangeEvent": 0,  # 监听可见区域变化负载
                "GetDefaultDisplay": 0,  # 获取屏幕宽高负载
                "MarshRSTransactionData": 0,  # 单帧cmdCount多
            },
            "RS": {
                "ProcessedNodes": {"ts": 0.0, "count": 0},  # 应用绘制节点数多
                "DisplayNodeSkipTimes": 0,  # RS进程DisplayNode skip的次数
                "UnMarshRSTransactionData": 0,  # RS反序列化数量
                "AnimateSize": {"nodeSizeSum": 0, "totalAnimationSizeSum": 0}  # RS动画节点数
            },
            "av_codec": {
                "soft_decoder": False
            }
        }

        try:
            with sqlite3.connect(trace_db_path) as _conn:
                _conn.row_factory = sqlite3.Row
                cursor = _conn.cursor()
                result['arkui']['animator'] = self._collect_app_invoke_times(cursor, '%ohos.animator%', app_pids)
                result['arkui']['HandleOnAreaChangeEvent'] = (
                    self._collect_app_invoke_times(cursor, '%H:HandleOnAreaChangeEvent%', app_pids))
                result['arkui']['HandleVisibleAreaChangeEvent'] = (
                    self._collect_app_invoke_times(cursor, '%H:HandleVisibleAreaChangeEvent%', app_pids))
                result['arkui']['GetDefaultDisplay'] = (
                    self._collect_app_invoke_times(cursor, '%GetDefaultDisplay%', app_pids))
                result['arkui']['MarshRSTransactionData'] = (
                    self._collect_app_invoke_times(cursor, '%H:MarshRSTransactionData cmdCount%', app_pids))

                result['RS']['ProcessedNodes'] = self._collect_rs_max_processed_node(cursor)
                result['RS']['DisplayNodeSkipTimes'] = self._collect_rs_invoke_times(cursor, '%DisplayNode skip|%')
                result['RS']['UnMarshRSTransactionData'] = (
                    self._collect_rs_invoke_times(cursor, '%H:UnMarsh RSTransactionData: data size:%'))
                result['RS']['AnimateSize'] = self._collect_rs_animate_nodes(cursor)

                result['av_codec']['soft_decoder'] = self._collect_av_codec_soft_decoder(cursor)

        except sqlite3.Error as e:
            self.logger.error("FaultTreeAnalyzer _analyze_impl Database error: %s", str(e))

        return result

    def _collect_app_invoke_times(self, cursor, name_match: str, app_pids: list) -> int:
        return self._collect_invoke_times(cursor, name_match, f"pid in ({','.join(map(str, app_pids))})")

    def _collect_rs_invoke_times(self, cursor, name_match: str) -> int:
        return self._collect_invoke_times(cursor, name_match, "name = 'render_service'")

    def _collect_invoke_times(self, cursor, name_match: str, process_match: str) -> int:
        try:
            cursor.execute(f"""
                SELECT count(*) FROM callstack
                WHERE
                name LIKE '{name_match}'
                and callid in (
                    SELECT id FROM thread
                    where
                        ipid in (
                            SELECT ipid
                            FROM process
                            where {process_match}
                        )
                    )
            """)

            rows = cursor.fetchall()
            return rows[0][0]
        except sqlite3.Error as e:
            self.logger.error("FaultTreeAnalyzer invoke Database error: %s", str(e))
        return 0

    @staticmethod
    def _collect_rs_max_processed_node(cursor) -> dict:
        cursor.execute("select start_ts, end_ts from trace_range")
        start_ts = cursor.fetchall()[0][0]

        cursor.execute("""
            select ts, name from callstack
            where
            name like '%ProcessedNodes%'
            and callid in (
                SELECT id FROM thread
                where
                    ipid in (
                        SELECT ipid FROM process  where name = 'render_service'
                    )
           )"""
                       )

        max_processed = {"ts": 0, "count": 0}
        for row in cursor.fetchall():
            match = re.search(r"ProcessedNodes:\s*(\d+)", row[1])
            if match:
                nodes = int(match.group(1))
                if nodes > max_processed["count"]:
                    max_processed["count"] = nodes
                    max_processed["ts"] = (row[0] - start_ts) / 1e9
        return max_processed

    @staticmethod
    def _collect_rs_animate_nodes(cursor) -> dict:
        cursor.execute("""
                    select name from callstack
                    where
                    name like '%H:Animate [nodeSize, totalAnimationSize]%'
                    and callid in (
                        SELECT id FROM thread
                        where
                            ipid in (
                                SELECT ipid FROM process  where name = 'render_service'
                            )
                   )"""
                       )
        node_size = 0
        total_animation_size = 0

        for row in cursor.fetchall():
            match = re.search(r'\[(\d+),\s*(\d+)\]', row[0])
            if match:
                node_size += int(match.group(1))
                total_animation_size += int(match.group(2))

        return {"nodeSizeSum": node_size, "totalAnimationSizeSum": total_animation_size}

    def _collect_av_codec_soft_decoder(self, cursor) -> bool:
        try:
            cursor.execute("""
                select count(*) from callstack
                   where
                   (name like '%hevcdecoder%'
                   or name like '%H:Fcodec%')
                   and callid in (
                       SELECT id FROM thread
                       where
                           ipid in (
                               SELECT ipid FROM process  where name like 'av_codec_servic%'
                           )
                   )
        """)
            rows = cursor.fetchall()
            return rows[0][0] > 0
        except sqlite3.Error as e:
            self.logger.error("FaultTreeAnalyzer av_codec Database error: %s", str(e))
        return False
