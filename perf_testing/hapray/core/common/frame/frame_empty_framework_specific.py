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
import re
import sqlite3
import time
from typing import Optional

import pandas as pd

"""框架特定空刷检测模块

本模块包含所有框架特定的空刷检测逻辑，包括：
1. Flutter 空刷检测（基于 SetPresentInfo frame_damage）
2. RN 空刷检测（待实现）

设计原则：
- Self-contained：所有框架特定的检测逻辑都在本文件中
- 统一接口：所有检测器返回统一格式的 DataFrame
- 易于扩展：新增框架只需添加新的检测器类
- 独立维护：不影响其他模块的代码
"""

logger = logging.getLogger(__name__)


class FrameworkSpecificDetector:
    """框架特定空刷检测器基类

    所有框架特定的检测器都应该继承此类，实现统一的接口。
    """

    def __init__(self, trace_conn: sqlite3.Connection, app_pids: list[int]):
        """
        初始化框架检测器

        Args:
            trace_conn: trace 数据库连接
            app_pids: 应用进程 ID 列表
        """
        self.trace_conn = trace_conn
        self.app_pids = app_pids

    def detect_empty_frames(self) -> pd.DataFrame:
        """
        检测空刷帧（抽象方法，子类必须实现）

        Returns:
            DataFrame: 统一格式的空刷帧数据，包含以下字段：
                - ts: 时间戳
                - dur: 持续时间
                - tid: 线程 ID
                - itid: 内部线程 ID
                - pid: 进程 ID
                - ipid: 内部进程 ID
                - vsync: VSync 标识（如果匹配到 frame_slice）
                - flag: 帧标志（默认 2，表示空刷）
                - type: 帧类型（0=实际帧）
                - thread_name: 线程名
                - process_name: 进程名
                - is_main_thread: 是否主线程（0/1）
                - detection_method: 检测方法（'framework_specific'）
                - framework_type: 框架类型（'flutter'/'rn'）
                - frame_damage: 原始 frame_damage 信息（Flutter 特有）
                - callstack_id: callstack 事件 ID
                - beginframe_id: BeginFrame 事件 ID（Flutter 特有）
        """
        raise NotImplementedError('子类必须实现 detect_empty_frames 方法')

    def _match_frame_slice(
        self,
        itid: int,
        ts: int,
        time_tolerance_ns: int = 5000000,  # 默认 ±5ms 容差
    ) -> Optional[dict]:
        """
        通过 callstack 事件匹配 frame_slice 表中的帧，获取 vsync 等信息

        Args:
            itid: 内部线程 ID（对应 callstack.callid）
            ts: 时间戳（对应 callstack.ts）
            time_tolerance_ns: 时间容差（纳秒），默认 ±5ms

        Returns:
            dict: 匹配到的 frame_slice 信息，包含 vsync, flag, type, ts, dur 等
            如果未匹配到，返回 None
        """
        try:
            cursor = self.trace_conn.cursor()
            cursor.execute(
                """
                SELECT fs.ts, fs.dur, fs.vsync, fs.flag, fs.type, fs.itid, fs.ipid,
                       t.tid, t.name as thread_name, p.pid, p.name as process_name
                FROM frame_slice fs
                INNER JOIN thread t ON fs.itid = t.id
                INNER JOIN process p ON fs.ipid = p.ipid
                WHERE fs.itid = ?
                AND fs.ts BETWEEN ? - ? AND ? + ?
                AND fs.type = 0
                ORDER BY ABS(fs.ts - ?)
                LIMIT 1
            """,
                (itid, ts, time_tolerance_ns, ts, time_tolerance_ns, ts),
            )

            row = cursor.fetchone()
            if row:
                return {
                    'ts': row[0],
                    'dur': row[1],
                    'vsync': row[2],
                    'flag': row[3],
                    'type': row[4],
                    'itid': row[5],
                    'ipid': row[6],
                    'tid': row[7],
                    'thread_name': row[8],
                    'pid': row[9],
                    'process_name': row[10],
                }
        except Exception as e:
            logger.warning(f'匹配 frame_slice 失败: itid={itid}, ts={ts}, error={e}')

        return None


class FlutterEmptyFrameDetector(FrameworkSpecificDetector):
    """Flutter 空刷检测器

    基于 SetPresentInfo 事件的 frame_damage 检测空刷。
    核心逻辑：
    1. 查找 SetPresentInfo 事件（在 1.raster 线程）
    2. 提取 frame_damage，判断是否为空刷
    3. 匹配 frame_slice 获取 vsync 等信息
    4. 追溯到最近的 BeginFrame（在 1.ui 线程）
    5. 转换为统一格式
    """

    def __init__(self, trace_conn: sqlite3.Connection, app_pids: list[int]):
        super().__init__(trace_conn, app_pids)
        self.framework_type = 'flutter'
        self.total_detected_count = 0  # 记录检测到的空刷帧数量（frame_damage为空）

    def detect_empty_frames(self) -> pd.DataFrame:
        """检测 Flutter 空刷帧"""
        try:
            # 1. 查找 Flutter 应用进程和线程
            flutter_info = self._find_flutter_process_and_threads()
            if not flutter_info:
                logger.info('未找到 Flutter 应用进程或线程')
                return pd.DataFrame()

            app_ipid, app_pid, app_name, raster_itid, raster_tid, ui_itid, ui_tid = flutter_info

            # 2. 查找 SetPresentInfo 事件
            setpresent_events = self._get_setpresent_events(raster_itid)
            total_setpresent_count = len(setpresent_events)  # 所有SetPresentInfo事件数量
            logger.info(f'找到 {total_setpresent_count} 个 SetPresentInfo 事件')
            if not setpresent_events:
                logger.info('未找到 SetPresentInfo 事件')
                # 即使没有事件，也记录检测器运行了（检测到0个）
                self.total_detected_count = 0
                return pd.DataFrame()

            # 3. 识别空刷并构建帧数据
            empty_frames = []
            for event_item in setpresent_events:
                # 兼容不同的返回格式
                if len(event_item) == 5:
                    event_id, ts, dur, name, frame_damage = event_item
                elif len(event_item) == 6:
                    event_id, ts, dur, name, frame_damage, is_empty = event_item
                else:
                    logger.warning(f'意外的 SetPresentInfo 事件格式: {event_item}')
                    continue
                # 提取 frame_damage 并判断是否为空刷
                # 如果 frame_damage 不为空（有脏区），跳过，不算作检测到一帧
                if not self._is_empty_frame_damage(frame_damage):
                    continue

                # 匹配 frame_slice 获取 vsync 等信息
                matched_frame = self._match_frame_slice(raster_itid, ts)

                # 追溯到最近的 BeginFrame
                beginframe = self._find_nearest_beginframe(ui_itid, ts)

                # 构建统一格式的帧数据
                frame_data = self._build_frame_data(
                    event_id,
                    ts,
                    dur,
                    name,
                    frame_damage,
                    raster_itid,
                    raster_tid,
                    ui_itid,
                    ui_tid,
                    app_ipid,
                    app_pid,
                    app_name,
                    matched_frame,
                    beginframe,
                )

                if frame_data:
                    empty_frames.append(frame_data)

            # 统计检测到的空刷帧数量（frame_damage为空的事件）
            self.total_detected_count = len(empty_frames)
            if total_setpresent_count > 0:
                logger.info(
                    f'其中 {self.total_detected_count} 个是空刷帧（frame_damage为空），{total_setpresent_count - self.total_detected_count} 个有脏区（非空刷，已跳过）'
                )

            if not empty_frames:
                logger.info('Flutter 检测器：未检测到空刷帧（在合并去重之前）')
                return pd.DataFrame()

            return pd.DataFrame(empty_frames)
            # 注意：这里不输出日志，因为 detect_framework_specific_empty_frames 中已经会输出

        except Exception as e:
            logger.error(f'Flutter 空刷检测失败: {e}', exc_info=True)
            return pd.DataFrame()

    def _find_flutter_process_and_threads(self) -> Optional[tuple]:
        """
        查找 Flutter 应用进程和关键线程（1.raster 和 1.ui）

        Returns:
            tuple: (app_ipid, app_pid, app_name, raster_itid, raster_tid, ui_itid, ui_tid)
            如果未找到，返回 None
        """
        cursor = self.trace_conn.cursor()

        # 查找 Flutter 应用进程（匹配 %_with_animation% 或 app_pids）
        if self.app_pids:
            cursor.execute(
                """
                SELECT p.ipid, p.pid, p.name
                FROM process p
                WHERE p.pid IN ({})
                AND (p.name LIKE '%_with_animation%' OR p.name LIKE '%.flutter%')
                LIMIT 1
            """.format(','.join('?' * len(self.app_pids))),
                self.app_pids,
            )
        else:
            cursor.execute("""
                SELECT p.ipid, p.pid, p.name
                FROM process p
                WHERE p.name LIKE '%_with_animation%'
                LIMIT 1
            """)

        process_row = cursor.fetchone()
        if not process_row:
            return None

        app_ipid, app_pid, app_name = process_row

        # 查找 1.raster 线程
        cursor.execute(
            """
            SELECT t.id, t.tid
            FROM thread t
            WHERE t.name LIKE '%1.raster%'
            AND t.ipid = ?
            LIMIT 1
        """,
            (app_ipid,),
        )

        raster_row = cursor.fetchone()
        if not raster_row:
            return None

        raster_itid, raster_tid = raster_row

        # 查找 1.ui 线程
        cursor.execute(
            """
            SELECT t.id, t.tid
            FROM thread t
            WHERE t.name LIKE '%1.ui%'
            AND t.ipid = ?
            LIMIT 1
        """,
            (app_ipid,),
        )

        ui_row = cursor.fetchone()
        if not ui_row:
            return None

        ui_itid, ui_tid = ui_row

        return (app_ipid, app_pid, app_name, raster_itid, raster_tid, ui_itid, ui_tid)

    def _get_setpresent_events(self, raster_itid: int) -> list[tuple]:
        """
        查找所有 SetPresentInfo 事件（包含 frame_damage）

        Args:
            raster_itid: 1.raster 线程的内部 ID

        Returns:
            List[Tuple]: [(event_id, ts, dur, name, frame_damage), ...]
        """
        cursor = self.trace_conn.cursor()
        cursor.execute(
            """
            SELECT id, ts, dur, name
            FROM callstack
            WHERE callid = ?
            AND name LIKE '%SetPresentInfo%'
            AND name LIKE '%frame_damage%'
            ORDER BY ts
        """,
            (raster_itid,),
        )

        results = []
        for event_id, ts, dur, name in cursor.fetchall():
            frame_damage = self._extract_frame_damage(name)
            if frame_damage is not None:
                results.append((event_id, ts, dur, name, frame_damage))

        return results

    def _extract_frame_damage(self, name: str) -> Optional[str]:
        """
        从事件名称中提取 frame_damage 信息

        Args:
            name: 事件名称，如 "SetPresentInfo frame_damage:<0,0,0,0>"

        Returns:
            str: frame_damage 字符串，如 "<0,0,0,0>"，如果未找到返回 None
        """
        match = re.search(r'frame_damage:<([^>]+)>', name)
        if match:
            return f'<{match.group(1)}>'
        return None

    def _is_empty_frame_damage(self, frame_damage: str) -> bool:
        """
        判断 frame_damage 是否表示空刷

        Args:
            frame_damage: frame_damage 字符串，如 "<0,0,0,0>" 或 "<x,y,w,h>"

        Returns:
            bool: True 表示空刷，False 表示非空刷
        """
        if not frame_damage:
            return False

        # 提取 x, y, w, h
        match = re.search(r'<(\d+),(\d+),(\d+),(\d+)>', frame_damage)
        if not match:
            return False

        x, y, w, h = map(int, match.groups())

        # 空刷判断：w == 0 或 h == 0 或 (x == 0 and y == 0 and w == 0 and h == 0)
        return w == 0 or h == 0 or (x == 0 and y == 0 and w == 0 and h == 0)

    def _find_nearest_beginframe(self, ui_itid: int, setpresent_ts: int) -> Optional[dict]:
        """
        查找最近的 BeginFrame 事件（在 1.ui 线程）

        Args:
            ui_itid: 1.ui 线程的内部 ID
            setpresent_ts: SetPresentInfo 的时间戳

        Returns:
            dict: BeginFrame 信息，包含 id, ts, dur, name
            如果未找到，返回 None
        """
        try:
            cursor = self.trace_conn.cursor()
            cursor.execute(
                """
                SELECT id, ts, dur, name
                FROM callstack
                WHERE callid = ?
                AND name LIKE '%BeginFrame%'
                AND ts <= ?
                ORDER BY ts DESC
                LIMIT 1
            """,
                (ui_itid, setpresent_ts),
            )

            row = cursor.fetchone()
            if row:
                return {'id': row[0], 'ts': row[1], 'dur': row[2], 'name': row[3]}
        except Exception as e:
            logger.warning(f'查找 BeginFrame 失败: ui_itid={ui_itid}, ts={setpresent_ts}, error={e}')

        return None

    def _build_frame_data(
        self,
        setpresent_id: int,
        setpresent_ts: int,
        setpresent_dur: int,
        setpresent_name: str,
        frame_damage: str,
        raster_itid: int,
        raster_tid: int,
        ui_itid: int,
        ui_tid: int,
        app_ipid: int,
        app_pid: int,
        app_name: str,
        matched_frame: Optional[dict],
        beginframe: Optional[dict],
    ) -> Optional[dict]:
        """
        构建统一格式的帧数据

        Args:
            setpresent_id: SetPresentInfo 事件 ID
            setpresent_ts: SetPresentInfo 时间戳
            setpresent_dur: SetPresentInfo 持续时间
            setpresent_name: SetPresentInfo 事件名称
            frame_damage: frame_damage 字符串
            raster_itid: 1.raster 线程的内部 ID
            raster_tid: 1.raster 线程的系统 ID
            ui_itid: 1.ui 线程的内部 ID
            ui_tid: 1.ui 线程的系统 ID
            app_ipid: 应用进程的内部 ID
            app_pid: 应用进程的系统 ID
            app_name: 应用进程名称
            matched_frame: 匹配到的 frame_slice 信息（可选）
            beginframe: BeginFrame 信息（可选）

        Returns:
            dict: 统一格式的帧数据
        """
        # 确定时间戳和持续时间
        if matched_frame:
            # 优先使用匹配到的 frame_slice 的时间
            ts = matched_frame['ts']
            dur = matched_frame['dur']
            vsync = matched_frame['vsync']
            flag = matched_frame.get('flag', 2)
        elif beginframe:
            # 使用 BeginFrame 到 SetPresentInfo 的时间区间
            ts = beginframe['ts']
            dur = setpresent_ts + setpresent_dur - beginframe['ts']
            vsync = None
            flag = 2
        else:
            # 如果没有 BeginFrame，使用 SetPresentInfo 的时间
            ts = setpresent_ts
            dur = setpresent_dur
            vsync = None
            flag = 2

        # 判断是否主线程（线程名 == 进程名）
        is_main_thread = 1 if app_name in {'1.ui', '1.raster'} else 0

        return {
            'ts': ts,
            'dur': dur,
            'tid': raster_tid,  # 使用 1.raster 线程的 tid
            'itid': raster_itid,  # 使用 1.raster 线程的 itid
            'pid': app_pid,
            'ipid': app_ipid,
            'vsync': vsync,
            'flag': flag,
            'type': 0,  # 实际帧
            'thread_name': '1.raster',
            'process_name': app_name,
            'is_main_thread': is_main_thread,
            'callstack_id': setpresent_id,
            'detection_method': 'framework_specific',
            'framework_type': self.framework_type,
            'frame_damage': frame_damage,
            'beginframe_id': beginframe['id'] if beginframe else None,
        }


class RNEmptyFrameDetector(FrameworkSpecificDetector):
    """RN 空刷检测器（待实现）

    RN 的空刷检测逻辑需要根据实际数据验证后实现。
    可能的检测方法：
    1. 检测 RNOH_JS 线程的特定事件
    2. 检测渲染相关的空刷标志
    3. 其他框架特定的检测方法
    """

    def __init__(self, trace_conn: sqlite3.Connection, app_pids: list[int]):
        super().__init__(trace_conn, app_pids)
        self.framework_type = 'rn'

    def detect_empty_frames(self) -> pd.DataFrame:
        """检测 RN 空刷帧（待实现）"""
        # TODO: 实现 RN 空刷检测逻辑
        logger.warning('RN 空刷检测尚未实现')
        return pd.DataFrame()


# ==================== 统一入口函数 ====================


def detect_framework_specific_empty_frames(
    trace_conn: sqlite3.Connection, app_pids: list[int], framework_types: list[str] = None, timing_stats: dict = None
) -> pd.DataFrame:
    """
    检测框架特定的空刷帧（统一入口函数）

    本函数是 EmptyFrameAnalyzer 调用框架检测的唯一入口。
    所有框架特定的检测逻辑都封装在本模块中，便于维护和扩展。

    Args:
        trace_conn: trace 数据库连接
        app_pids: 应用进程 ID 列表
        framework_types: 要检测的框架类型列表，如 ['flutter']
                        如果为 None，则自动检测所有支持的框架
        timing_stats: 耗时统计字典（可选，用于记录检测耗时）

    Returns:
        DataFrame: 统一格式的空刷帧数据，包含所有检测到的框架特定空刷帧
    """
    if framework_types is None:
        # 默认检测所有支持的框架
        framework_types = ['flutter']

    all_frames = []

    for framework_type in framework_types:
        try:
            if timing_stats:
                start_time = time.time()

            detector = None
            if framework_type == 'flutter':
                detector = FlutterEmptyFrameDetector(trace_conn, app_pids)
            elif framework_type == 'rn':
                detector = RNEmptyFrameDetector(trace_conn, app_pids)
            else:
                logger.warning(f'不支持的框架类型: {framework_type}')
                continue

            if detector:
                frames_df = detector.detect_empty_frames()
                empty_frame_count = len(frames_df)  # 空刷帧数量（frame_damage为空）

                # 获取检测到的空刷帧数量（只统计frame_damage为空的事件）
                # 有脏区的事件不算作检测到一帧
                if hasattr(detector, 'total_detected_count'):
                    detected_count = detector.total_detected_count
                else:
                    # 兼容旧版本：如果没有total_detected_count，使用空刷帧数量
                    detected_count = empty_frame_count

                # 输出检测结果
                if detected_count > 0:
                    logger.info(
                        f'{framework_type} 框架检测器：检测到 {detected_count} 个空刷帧（frame_damage为空，在合并去重之前，可能与 flag=2 或 RS skip 重叠）'
                    )
                else:
                    logger.info(f'{framework_type} 框架检测器：检测到 0 个空刷帧')

                if not frames_df.empty:
                    all_frames.append(frames_df)

                # 记录到 timing_stats 中，方便后续统计
                # detected_count 只记录空刷帧数量（frame_damage为空的事件）
                # 有脏区的事件不算作检测到一帧
                if timing_stats:
                    timing_stats[f'{framework_type}_detection'] = time.time() - start_time
                    timing_stats[f'{framework_type}_detected_count'] = detected_count

        except Exception as e:
            logger.error(f'{framework_type} 框架检测失败: {e}', exc_info=True)
            if timing_stats:
                timing_stats[f'{framework_type}_detection'] = -1  # 标记为失败

    if not all_frames:
        return pd.DataFrame()

    # 合并所有框架的检测结果
    return pd.concat(all_frames, ignore_index=True)
