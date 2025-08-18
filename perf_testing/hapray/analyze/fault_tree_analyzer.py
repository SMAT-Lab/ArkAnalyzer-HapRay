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
from typing import Any, Dict, Optional

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
                "soft_decoder": False,
                "BroadcastControlInstructions": 0,  # 播控框架指令数
                "VideoDecodingInputFrameCount": 0,  # 视频解码输入帧
                "VideoDecodingConsumptionFrame": 0  # 视频解码消费帧
            },
            "Audio": {  # 计算音频线程-应用读写数据的指令数
                "AudioWriteCB": 0,  # 1、应用进程的OS_AudioWriteCB线程指令数 - RendererInClientInner::OnWriteData函数指令数
                "AudioReadCB": 0,  # 2、应用进程的OS_AudioReadCB线程指令数 - CapturerInClientInner::OnReadData函数指令数
                "AudioPlayCb": 0,  # 3、应用进程的OS_AudioPlayCb线程指令数 - AudioProcessInClient::CallClientHandleCurrent函数指令数
                "AudioRecCb": 0  # 4、应用进程的OS_AudioRecCb线程指令数 - AudioProcessInClient::CallClientHandleCurrent函数指令数
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
                result['av_codec']['BroadcastControlInstructions'] = (
                    self._collect_broadcast_control_instructions(cursor)
                )
                result['av_codec']['VideoDecodingInputFrameCount'] = (
                    self._collect_video_decoding_input_frames(cursor)
                )
                result['av_codec']['VideoDecodingConsumptionFrame'] = (
                    self._collect_video_decoding_consumption_frames(cursor)
                )

                # 音频分析
                result['Audio']['AudioWriteCB'] = self._collect_audio_write_cb_instructions(cursor)
                result['Audio']['AudioReadCB'] = self._collect_audio_read_cb_instructions(cursor)
                result['Audio']['AudioPlayCb'] = self._collect_audio_play_cb_instructions(cursor)
                result['Audio']['AudioRecCb'] = self._collect_audio_rec_cb_instructions(cursor)

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

    def _collect_broadcast_control_instructions(self, cursor) -> int:
        """
        4.2 播控框架指令数高
        统计 av_session 进程中 OS_AVSessionHdl 线程的性能采样事件数
        """
        try:
            cursor.execute("""
                SELECT sum(event_count)
                FROM perf_sample
                WHERE callchain_id IN (
                    SELECT id
                    FROM thread
                    WHERE ipid IN (
                        SELECT ipid
                        FROM process
                        WHERE name LIKE '%av_session%'
                    )
                    AND name LIKE '%OS_AVSessionHdl%'
                )
            """)
            rows = cursor.fetchall()
            result = rows[0][0] if rows and rows[0][0] is not None else 0
            self.logger.debug("Broadcast control instructions count: %d", result)
            return result
        except sqlite3.Error as e:
            self.logger.error("FaultTreeAnalyzer broadcast_control Database error: %s", str(e))
            return 0

    def _collect_video_decoding_input_frames(self, cursor) -> int:
        """
        4.3 视频解码输入帧
        统计 av_codec_service 进程中 OnQueueInputBuffer 调用次数
        """
        try:
            cursor.execute("""
                SELECT count(name)
                FROM callstack
                WHERE name LIKE '%OnQueueInputBuffer%'
                AND callid IN (
                    SELECT id FROM thread
                    WHERE ipid IN (
                        SELECT ipid FROM process
                        WHERE name LIKE 'av_codec_servic%'
                    )
                )
            """)
            rows = cursor.fetchall()
            result = rows[0][0] if rows and rows[0][0] is not None else 0
            self.logger.debug("Video decoding input frames count: %d", result)
            return result
        except sqlite3.Error as e:
            self.logger.error("FaultTreeAnalyzer video_input_frames Database error: %s", str(e))
            return 0

    def _collect_video_decoding_consumption_frames(self, cursor) -> int:
        """
        4.4 视频解码消费帧
        统计 av_codec_service 进程中 OnRenderOutputBuffer 和 OnReleaseOutputBuffer 调用次数
        """
        try:
            cursor.execute("""
                SELECT count(name)
                FROM callstack
                WHERE (name LIKE '%OnRenderOutputBuffer%' OR name LIKE '%OnReleaseOutputBuffer%')
                AND callid IN (
                    SELECT id FROM thread
                    WHERE ipid IN (
                        SELECT ipid FROM process
                        WHERE name LIKE 'av_codec_servic%'
                    )
                )
            """)
            rows = cursor.fetchall()
            result = rows[0][0] if rows and rows[0][0] is not None else 0
            self.logger.debug("Video decoding consumption frames count: %d", result)
            return result
        except sqlite3.Error as e:
            self.logger.error("FaultTreeAnalyzer video_consumption_frames Database error: %s", str(e))
            return 0

    # ==================== 公共方法 ====================

    def _collect_thread_event_count(self, cursor, thread_name_pattern: str, description: str = "") -> int:
        """
        通用方法：根据线程名模式统计性能采样事件数

        Args:
            cursor: 数据库游标
            thread_name_pattern: 线程名匹配模式
            description: 描述信息，用于日志

        Returns:
            int: 事件总数
        """
        try:
            cursor.execute("""
                SELECT sum(event_count)
                FROM perf_sample
                WHERE callchain_id IN (
                    SELECT id
                    FROM thread
                    WHERE name LIKE ?
                )
            """, (thread_name_pattern,))

            rows = cursor.fetchall()
            result = rows[0][0] if rows and rows[0][0] is not None else 0
            self.logger.debug("%s thread event count: %d", description or thread_name_pattern, result)
            return result
        except sqlite3.Error as e:
            self.logger.error("FaultTreeAnalyzer thread_event_count Database error: %s", str(e))
            return 0

    def _collect_function_event_count(self, cursor, function_name_pattern: str, description: str = "") -> int:
        """
        通用方法：根据函数名模式统计性能采样事件数

        Args:
            cursor: 数据库游标
            function_name_pattern: 函数名匹配模式
            description: 描述信息，用于日志

        Returns:
            int: 事件总数
        """
        try:
            cursor.execute("""
                SELECT count(event_count)
                FROM perf_sample
                WHERE callchain_id IN (
                    SELECT callchain_id
                    FROM perf_callchain cc
                    JOIN data_dict dd ON cc.name = dd.id
                    WHERE dd.data LIKE ?
                )
            """, (function_name_pattern,))

            rows = cursor.fetchall()
            result = rows[0][0] if rows and rows[0][0] is not None else 0
            self.logger.debug("%s function event count: %d", description or function_name_pattern, result)
            return result
        except sqlite3.Error as e:
            self.logger.error("FaultTreeAnalyzer function_event_count Database error: %s", str(e))
            return 0

    # ==================== 音频分析方法 ====================

    def _collect_audio_write_cb_instructions(self, cursor) -> int:
        """
        1、应用进程的OS_AudioWriteCB线程指令数 - RendererInClientInner::OnWriteData函数指令数
        """
        thread_count = self._collect_thread_event_count(cursor, '%OS_AudioWriteCB%', 'AudioWriteCB thread')
        function_count = self._collect_function_event_count(
            cursor, '%RendererInClientInner::OnWriteData%', 'RendererInClientInner::OnWriteData function'
        )

        # 返回线程事件数，函数事件数作为补充信息记录在日志中
        self.logger.debug("AudioWriteCB - Thread events: %d, Function events: %d", thread_count, function_count)
        return thread_count

    def _collect_audio_read_cb_instructions(self, cursor) -> int:
        """
        2、应用进程的OS_AudioReadCB线程指令数 - CapturerInClientInner::OnReadData函数指令数
        """
        thread_count = self._collect_thread_event_count(cursor, '%OS_AudioReadCB%', 'AudioReadCB thread')
        function_count = self._collect_function_event_count(
            cursor, '%CapturerInClientInner::OnReadData%', 'CapturerInClientInner::OnReadData function'
        )

        self.logger.debug("AudioReadCB - Thread events: %d, Function events: %d", thread_count, function_count)
        return thread_count

    def _collect_audio_play_cb_instructions(self, cursor) -> int:
        """
        3、应用进程的OS_AudioPlayCb线程指令数 - AudioProcessInClient::CallClientHandleCurrent函数指令数
        """
        thread_count = self._collect_thread_event_count(cursor, '%OS_AudioPlayCb%', 'AudioPlayCb thread')
        function_count = self._collect_function_event_count(
            cursor, '%AudioProcessInClient::CallClientHandleCurrent%',
            'AudioProcessInClient::CallClientHandleCurrent function'
        )

        self.logger.debug("AudioPlayCb - Thread events: %d, Function events: %d", thread_count, function_count)
        return thread_count

    def _collect_audio_rec_cb_instructions(self, cursor) -> int:
        """
        4、应用进程的OS_AudioRecCb线程指令数 - AudioProcessInClient::CallClientHandleCurrent函数指令数
        """
        thread_count = self._collect_thread_event_count(cursor, '%OS_AudioRecCb%', 'AudioRecCb thread')
        function_count = self._collect_function_event_count(
            cursor, '%AudioProcessInClient::CallClientHandleCurrent%',
            'AudioProcessInClient::CallClientHandleCurrent function'
        )

        self.logger.debug("AudioRecCb - Thread events: %d, Function events: %d", thread_count, function_count)
        return thread_count
