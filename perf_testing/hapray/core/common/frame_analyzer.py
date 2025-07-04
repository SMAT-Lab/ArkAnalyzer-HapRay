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

import codecs
import logging
import os
import sqlite3
import sys
import traceback
from typing import Dict, Any, List, Optional

import pandas as pd

# 同时设置标准输出编码
os.environ["PYTHONIOENCODING"] = "utf-8"
sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')


class FrameAnalyzer:
    """卡顿帧分析器

    用于分析htrace文件中的卡顿帧数据，包括：
    1. 将htrace文件转换为db文件
    2. 分析卡顿帧数据
    3. 生成分析报告
    """

    # 类变量用于存储缓存
    _callchain_cache = {}  # 缓存callchain数据，格式: {step_id: pd.DataFrame}
    _files_cache = {}      # 缓存files数据，格式: {step_id: pd.DataFrame}
    _pid_cache = {}        # 缓存pid数据，格式: {step_id: [pids]}
    _tid_cache = {}        # 缓存tid数据，格式: {step_id: [tids]}
    _process_cache = {}    # 缓存process数据，格式: {step_id: pd.DataFrame}

    # 调试开关配置
    _debug_vsync_enabled = False  # VSync调试开关，True时正常判断，False时永远不触发VSync条件

    FRAME_DURATION = 16.67  # 毫秒，60fps基准帧时长
    STUTTER_LEVEL_1_FRAMES = 2  # 1级卡顿阈值：0-2帧
    STUTTER_LEVEL_2_FRAMES = 6  # 2级卡顿阈值：2-6帧
    NS_TO_MS = 1_000_000
    WINDOW_SIZE_MS = 1000  # fps窗口大小：1s

    @staticmethod
    def _update_pid_tid_cache(step_id: str, trace_df: pd.DataFrame) -> None:
        """根据trace_df中的数据更新PID和TID缓存

        Args:
            step_id: 步骤ID，如'step1'或'1'
            trace_df: 包含pid和tid信息的DataFrame
        """
        try:
            if trace_df.empty:
                return

            # 提取唯一的PID和TID
            unique_pids = set(trace_df['pid'].dropna().unique())
            unique_tids = set(trace_df['tid'].dropna().unique())

            # 更新PID缓存
            FrameAnalyzer._pid_cache[step_id] = list(unique_pids)

            # 更新TID缓存
            FrameAnalyzer._tid_cache[step_id] = list(unique_tids)

            logging.debug("从trace_df更新缓存: %s, PIDs: %s, TIDs: %s", step_id, len(unique_pids), len(unique_tids))

        except Exception as e:
            logging.error("更新PID/TID缓存失败: %s", str(e))

    @staticmethod
    def _get_callchain_cache(perf_conn, step_id: str = None) -> pd.DataFrame:
        """
        获取并缓存perf_callchain表的数据

        Args:
            perf_conn: perf数据库连接
            step_id: 步骤ID，用作缓存key

        Returns:
            pd.DataFrame: callchain缓存数据
        """
        # 如果没有提供step_id，使用连接对象作为key
        cache_key = step_id if step_id else str(perf_conn)

        # 如果已有缓存且不为空，直接返回
        if cache_key in FrameAnalyzer._callchain_cache and not FrameAnalyzer._callchain_cache[cache_key].empty:
            logging.debug("使用已存在的callchain缓存，共 %s 条记录", len(FrameAnalyzer._callchain_cache[cache_key]))
            return FrameAnalyzer._callchain_cache[cache_key]

        try:
            callchain_cache = pd.read_sql_query("""
                SELECT
                    id,
                    callchain_id,
                    depth,
                    file_id,
                    symbol_id
                FROM perf_callchain
            """, perf_conn)

            # 保存到类变量
            FrameAnalyzer._callchain_cache[cache_key] = callchain_cache
            logging.debug("缓存了 %s 条callchain记录，key: %s", len(callchain_cache), cache_key)
            return callchain_cache

        except Exception as e:
            logging.error("获取callchain缓存数据失败: %s", str(e))
            return pd.DataFrame()

    @staticmethod
    def _get_files_cache(perf_conn, step_id: str = None) -> pd.DataFrame:
        """
        获取并缓存perf_files表的数据

        Args:
            perf_conn: perf数据库连接
            step_id: 步骤ID，用作缓存key

        Returns:
            pd.DataFrame: files缓存数据
        """
        # 如果没有提供step_id，使用连接对象作为key
        cache_key = step_id if step_id else str(perf_conn)

        # 如果已有缓存且不为空，直接返回
        if cache_key in FrameAnalyzer._files_cache and not FrameAnalyzer._files_cache[cache_key].empty:
            logging.debug("使用已存在的files缓存，共 %s 条记录", len(FrameAnalyzer._files_cache[cache_key]))
            return FrameAnalyzer._files_cache[cache_key]

        try:
            files_cache = pd.read_sql_query("""
                SELECT
                    file_id,
                    serial_id,
                    symbol,
                    path
                FROM perf_files
            """, perf_conn)

            # 保存到类变量
            FrameAnalyzer._files_cache[cache_key] = files_cache
            logging.debug("缓存了 %s 条files记录，key: %s", len(files_cache), cache_key)
            return files_cache

        except Exception as e:
            logging.error("获取files缓存数据失败: %s", str(e))
            return pd.DataFrame()

    @staticmethod
    def _get_process_cache(trace_conn, step_id: str = None) -> pd.DataFrame:
        """
        获取并缓存process表的数据

        Args:
            trace_conn: trace数据库连接
            step_id: 步骤ID，用作缓存key

        Returns:
            pd.DataFrame: process缓存数据
        """
        # 如果没有提供step_id，使用连接对象作为key
        cache_key = step_id if step_id else str(trace_conn)

        # 如果已有缓存且不为空，直接返回
        if cache_key in FrameAnalyzer._process_cache and not FrameAnalyzer._process_cache[cache_key].empty:
            logging.debug("使用已存在的process缓存，共 %s 条记录", len(FrameAnalyzer._process_cache[cache_key]))
            return FrameAnalyzer._process_cache[cache_key]

        try:
            process_cache = pd.read_sql_query("""
                SELECT
                    ipid,
                    name
                FROM process
            """, trace_conn)

            # 保存到类变量
            FrameAnalyzer._process_cache[cache_key] = process_cache
            logging.debug("缓存了 %s 条process记录，key: %s", len(process_cache), cache_key)
            return process_cache

        except Exception as e:
            logging.error("获取process缓存数据失败: %s", str(e))
            return pd.DataFrame()

    @staticmethod
    def get_process_cache_by_key(cache_key: str) -> pd.DataFrame:
        """
        通过缓存key获取process缓存数据（公开方法）

        Args:
            cache_key: 缓存key

        Returns:
            pd.DataFrame: process缓存数据
        """
        if cache_key in FrameAnalyzer._process_cache:
            return FrameAnalyzer._process_cache[cache_key]
        return pd.DataFrame()

    @staticmethod
    def get_process_cache(trace_conn, step_id: str = None) -> pd.DataFrame:
        """
        获取并缓存process表的数据（公开方法）

        Args:
            trace_conn: trace数据库连接
            step_id: 步骤ID，用作缓存key

        Returns:
            pd.DataFrame: process缓存数据
        """
        return FrameAnalyzer._get_process_cache(trace_conn, step_id)

    @staticmethod
    def _analyze_perf_callchain(perf_conn, callchain_id: int, callchain_cache: pd.DataFrame = None,
                                files_cache: pd.DataFrame = None, step_id: str = None) -> list:
        """
        分析perf样本的调用链信息

        Args:
            perf_conn: perf数据库连接
            callchain_id: 调用链ID
            callchain_cache: 缓存的callchain数据
            files_cache: 缓存的文件数据
            step_id: 步骤ID，用于缓存key

        Returns:
            list: 调用链信息列表，每个元素包含symbol和path信息
        """
        try:
            # 如果没有缓存，先获取缓存
            if callchain_cache is None or callchain_cache.empty:
                callchain_cache = FrameAnalyzer._get_callchain_cache(perf_conn, step_id)
            if files_cache is None or files_cache.empty:
                files_cache = FrameAnalyzer._get_files_cache(perf_conn, step_id)

            # 确定缓存key
            cache_key = step_id if step_id else str(perf_conn)

            # 检查缓存是否为空
            if cache_key not in FrameAnalyzer._callchain_cache or FrameAnalyzer._callchain_cache[cache_key].empty or \
                    cache_key not in FrameAnalyzer._files_cache or FrameAnalyzer._files_cache[cache_key].empty:
                logging.warning("缓存数据为空，无法分析调用链")
                return []

            # 从缓存中获取callchain数据
            callchain_records = FrameAnalyzer._callchain_cache[cache_key][
                FrameAnalyzer._callchain_cache[cache_key]['callchain_id'] == callchain_id]

            if callchain_records.empty:
                logging.warning("未找到callchain_id=%s的记录", callchain_id)
                return []

            # 构建调用链信息
            callchain_info = []
            for _, record in callchain_records.iterrows():
                # 从缓存中获取文件信息
                file_info = FrameAnalyzer._files_cache[cache_key][
                    (FrameAnalyzer._files_cache[cache_key]['file_id'] == record['file_id']) & (
                        FrameAnalyzer._files_cache[cache_key]['serial_id'] == record['symbol_id'])]
                symbol = file_info['symbol'].iloc[0] if not file_info.empty else 'unknown'
                path = file_info['path'].iloc[0] if not file_info.empty else 'unknown'

                callchain_info.append({
                    'depth': int(record['depth']),
                    'file_id': int(record['file_id']),
                    'path': path,
                    'symbol_id': int(record['symbol_id']),
                    'symbol': symbol
                })

            return callchain_info

        except Exception as e:
            logging.error("分析调用链失败: %s", str(e))
            return []

    @staticmethod
    def analyze_single_frame(frame, perf_df, perf_conn, step_id):
        """
        分析单个帧的负载和调用链，返回frame_load和sample_callchains
        """
        # 在函数内部获取缓存
        callchain_cache = FrameAnalyzer._get_callchain_cache(perf_conn, step_id)
        files_cache = FrameAnalyzer._get_files_cache(perf_conn, step_id)
        frame_load = 0
        sample_callchains = []
        mask = (
            (perf_df['timestamp_trace'] >= frame['start_time'])
            & (perf_df['timestamp_trace'] <= frame['end_time'])
            & (perf_df['thread_id'] == frame['tid'])
        )
        frame_samples = perf_df[mask]
        if frame_samples.empty:
            return frame_load, sample_callchains
        for _, sample in frame_samples.iterrows():
            if not pd.notna(sample['callchain_id']):
                continue
            try:
                callchain_info = FrameAnalyzer._analyze_perf_callchain(
                    perf_conn,
                    int(sample['callchain_id']),
                    callchain_cache,
                    files_cache,
                    step_id
                )
                if callchain_info:
                    is_vsync_chain = False
                    for i in range(len(callchain_info) - 1):
                        current_symbol = callchain_info[i]['symbol']
                        next_symbol = callchain_info[i + 1]['symbol']
                        event_count = sample['event_count']
                        if not current_symbol or not next_symbol:
                            continue
                        if FrameAnalyzer._debug_vsync_enabled and (
                                'OHOS::Rosen::VSyncCallBackListener::OnReadable' in current_symbol
                                and 'OHOS::Rosen::VSyncCallBackListener::HandleVsyncCallbacks' in next_symbol
                                and event_count < 2000000
                        ):
                            is_vsync_chain = True
                            break
                    if not is_vsync_chain:
                        frame_load += sample['event_count']
                        try:
                            sample_load_percentage = (sample['event_count'] / frame_load) * 100
                            sample_callchains.append({
                                'timestamp': int(sample['timestamp_trace']),
                                'event_count': int(sample['event_count']),
                                'load_percentage': float(sample_load_percentage),
                                'callchain': callchain_info
                            })
                        except Exception as e:
                            logging.error(
                                "处理样本时出错: %s, sample: %s, frame_load: %s", str(e), sample.to_dict(),
                                frame_load)
                            continue
            except Exception as e:
                logging.error("分析调用链时出错: %s", str(e))
                continue
        return frame_load, sample_callchains

    @staticmethod
    def analyze_empty_frames(trace_db_path: str, perf_db_path: str, app_pids: list, scene_dir: str = None,
                             step_id: str = None) -> Optional[dict]:
        """
        分析空帧（flag=2, type=0）的负载情况

        参数:
        - trace_db_path: str，trace数据库文件路径
        - perf_db_path: str，perf数据库文件路径
        - app_pids: list，应用进程ID列表
        - scene_dir: str，场景目录路径，用于更新缓存
        - step_id: str，步骤ID，用于更新缓存

        返回:
        - dict，包含分析结果
        """
        # 连接trace数据库
        trace_conn = sqlite3.connect(trace_db_path)
        perf_conn = sqlite3.connect(perf_db_path)

        try:
            # 检查SQLite版本是否支持WITH子句
            cursor = trace_conn.cursor()
            cursor.execute("SELECT sqlite_version()")
            version = cursor.fetchone()[0]
            version_parts = [int(x) for x in version.split('.')]
            if version_parts[0] < 3 or (version_parts[0] == 3 and version_parts[1] < 8):
                logging.error("SQLite版本 %s 不支持WITH子句，需要3.8.3或更高版本", version)
                return None

            # 确保所需表存在
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            required_tables = ['frame_slice', 'process', 'thread', 'callstack']
            if not all(table in tables for table in required_tables):
                logging.error("数据库中缺少必要的表，需要: %s", required_tables)
                return None

            # 执行查询获取帧信息
            query = f"""
            WITH filtered_frames AS (
                -- 首先获取符合条件的帧
                SELECT fs.ts, fs.dur, fs.ipid, fs.itid, fs.callstack_id
                FROM frame_slice fs
                WHERE fs.flag = 2
                AND fs.type = 0
            ),
            process_filtered AS (
                -- 通过process表过滤出app_pids中的帧
                SELECT ff.*, p.pid, p.name as process_name, t.tid, t.name as thread_name, t.is_main_thread
                FROM filtered_frames ff
                JOIN process p ON ff.ipid = p.ipid
                JOIN thread t ON ff.itid = t.itid
                WHERE p.pid IN ({','.join('?' * len(app_pids))})
            )
            -- 最后获取调用栈信息
            SELECT pf.*, cs.name as callstack_name
            FROM process_filtered pf
            JOIN callstack cs ON pf.callstack_id = cs.id
            """

            # 获取帧信息
            trace_df = pd.read_sql_query(query, trace_conn, params=app_pids)

            # 更新PID和TID缓存（如果提供了scene_dir和step_id）
            if scene_dir and step_id:
                FrameAnalyzer._update_pid_tid_cache(step_id, trace_df)

            if trace_df.empty:
                logging.info("未找到符合条件的帧")
                return None

            # 获取总负载
            total_load_query = "SELECT SUM(event_count) as total_load FROM perf_sample"
            total_load = pd.read_sql_query(total_load_query, perf_conn)['total_load'].iloc[0]

            # 获取所有perf样本
            perf_query = "SELECT callchain_id, timestamp_trace, thread_id, event_count FROM perf_sample"
            perf_df = pd.read_sql_query(perf_query, perf_conn)

            # 为每个帧创建时间区间
            trace_df['start_time'] = trace_df['ts']
            trace_df['end_time'] = trace_df['ts'] + trace_df['dur']

            # 初始化结果列表
            frame_loads = []
            empty_frame_load = 0  # 主线程空帧总负载（即空刷主线程负载）
            background_thread_load = 0  # 后台线程空帧总负载

            # 对每个帧进行分析
            for _, frame in trace_df.iterrows():
                frame_load, sample_callchains = FrameAnalyzer.analyze_single_frame(
                    frame, perf_df, perf_conn, step_id)
                if frame['is_main_thread'] == 1:
                    empty_frame_load += frame_load
                else:
                    background_thread_load += frame_load
                frame_loads.append({
                    'ts': frame['ts'],
                    'dur': frame['dur'],
                    'ipid': frame['ipid'],
                    'itid': frame['itid'],
                    'pid': frame['pid'],
                    'tid': frame['tid'],
                    'callstack_id': frame['callstack_id'],
                    'process_name': frame['process_name'],
                    'thread_name': frame['thread_name'],
                    'callstack_name': frame['callstack_name'],
                    'frame_load': frame_load,
                    'is_main_thread': frame['is_main_thread'],
                    'sample_callchains': sorted(sample_callchains, key=lambda x: x['event_count'], reverse=True)
                })

            # 转换为DataFrame并按负载排序
            result_df = pd.DataFrame(frame_loads)
            if not result_df.empty:
                # 分别获取主线程和后台线程的top5帧
                main_thread_frames = result_df[result_df['is_main_thread'] == 1].sort_values('frame_load',
                                                                                             ascending=False).head(5)
                background_thread_frames = (result_df[result_df['is_main_thread'] == 0]
                                            .sort_values('frame_load', ascending=False).head(5))

                # 只统计主线程空帧负载和后台线程负载
                empty_frame_percentage = (empty_frame_load / total_load) * 100
                background_thread_percentage = (background_thread_load / total_load) * 100

                # 构建结果字典
                return {
                    "status": "success",
                    "summary": {
                        "total_load": int(total_load),
                        "empty_frame_load": int(empty_frame_load),
                        "empty_frame_percentage": float(empty_frame_percentage),
                        "background_thread_load": int(background_thread_load),
                        "background_thread_percentage": float(background_thread_percentage),
                        "total_empty_frames": int(len(trace_df[trace_df['is_main_thread'] == 1])),
                        "empty_frames_with_load": int(len([f for f in frame_loads if f['is_main_thread'] == 1]))
                    },
                    "top_frames": {
                        "main_thread_empty_frames": main_thread_frames.to_dict('records'),
                        "background_thread": background_thread_frames.to_dict('records')
                    }
                }

            logging.info("未找到任何帧负载数据")
            return None

        except Exception as e:
            logging.error("分析空帧时发生异常: %s", str(e))
            return None

        finally:
            trace_conn.close()
            perf_conn.close()

    @staticmethod
    def analyze_single_stuttered_frame(frame, vsync_key, context):
        """
        分析单个卡顿帧，返回分析结果和统计信息
        """
        data = context["data"]
        perf_df = context["perf_df"]
        perf_conn = context["perf_conn"]
        step_id = context["step_id"]
        cursor = context.get("cursor")  # 从context中获取cursor
        callchain_cache = FrameAnalyzer._get_callchain_cache(perf_conn, step_id)
        files_cache = FrameAnalyzer._get_files_cache(perf_conn, step_id)
        frame_type = get_frame_type(frame, cursor, step_id=step_id)
        stutter_detail = None
        stutter_level = None
        level_desc = None
        frame_load = 0
        sample_callchains = []
        if frame.get("flag") != 1:
            return frame_type, stutter_level, stutter_detail
        expected_frame = next((f for f in data[vsync_key] if f["type"] == 1), None)
        if expected_frame is None:
            return frame_type, stutter_level, stutter_detail

        exceed_time_ns = frame["dur"] - expected_frame["dur"]
        exceed_time = exceed_time_ns / FrameAnalyzer.NS_TO_MS
        exceed_frames = exceed_time / FrameAnalyzer.FRAME_DURATION
        if perf_df is not None and perf_conn is not None:
            frame_start_time = frame["ts"]
            frame_end_time = frame["ts"] + frame["dur"]
            mask = (
                (perf_df['timestamp_trace'] >= frame_start_time)
                & (perf_df['timestamp_trace'] <= frame_end_time)
                & (perf_df['thread_id'] == frame['tid'])
            )
            frame_samples = perf_df[mask]
            if not frame_samples.empty:
                frame_load = frame_samples['event_count'].sum()
                for _, sample in frame_samples.iterrows():
                    if not pd.notna(sample['callchain_id']):
                        continue
                    try:
                        callchain_info = FrameAnalyzer._analyze_perf_callchain(
                            perf_conn,
                            int(sample['callchain_id']),
                            callchain_cache,
                            files_cache,
                            step_id
                        )
                        if len(callchain_info) == 0:
                            continue
                        try:
                            sample_load_percentage = (sample['event_count'] / frame_load) * 100
                            sample_callchains.append({
                                'timestamp': int(sample['timestamp_trace']),
                                'event_count': int(sample['event_count']),
                                'load_percentage': float(sample_load_percentage),
                                'callchain': callchain_info
                            })
                        except Exception as e:
                            logging.error(
                                "处理样本时出错: %s, sample: %s, frame_load: %s",
                                str(e), sample.to_dict(), frame_load)
                            continue
                    except Exception as e:
                        logging.error("分析调用链时出错: %s", str(e))
                        continue
        if frame.get("flag") == 3 or exceed_frames < FrameAnalyzer.STUTTER_LEVEL_1_FRAMES:
            stutter_level = 1
            level_desc = "轻微卡顿"
        elif exceed_frames < FrameAnalyzer.STUTTER_LEVEL_2_FRAMES:
            stutter_level = 2
            level_desc = "中度卡顿"
        else:
            stutter_level = 3
            level_desc = "严重卡顿"
        stutter_detail = {
            "vsync": vsync_key,
            "timestamp": frame["ts"],
            "actual_duration": frame["dur"],
            "expected_duration": expected_frame["dur"],
            "exceed_time": exceed_time,
            "exceed_frames": exceed_frames,
            "stutter_level": stutter_level,
            "level_description": level_desc,
            "src": frame.get("src"),
            "dst": frame.get("dst"),
            "frame_load": int(frame_load),
            "sample_callchains": sorted(sample_callchains, key=lambda x: x['event_count'], reverse=True)
        }
        return frame_type, stutter_level, stutter_detail

    @staticmethod
    def analyze_stuttered_frames(db_path: str, perf_db_path: str = None, step_id: str = None) -> Optional[dict]:
        """
        分析卡顿帧数据并计算FPS

        Args:
            db_path: 数据库文件路径
            perf_db_path: perf数据库文件路径，用于调用链分析
            step_id: 步骤ID，用于缓存key

        Returns:
            dict | None: 分析结果数据，如果没有数据或分析失败则返回None
        """
        # 连接数据库
        conn = None
        perf_conn = None

        try:
            # 连接数据库
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            # 连接perf数据库（如果提供）
            perf_conn = None
            if perf_db_path:
                try:
                    perf_conn = sqlite3.connect(perf_db_path)
                    # 获取perf样本数据用于调用链分析
                    perf_query = "SELECT callchain_id, timestamp_trace, thread_id, event_count FROM perf_sample"
                    perf_df = pd.read_sql_query(perf_query, perf_conn)
                except Exception as e:
                    logging.warning("无法连接perf数据库或获取数据: %s", str(e))
                    perf_df = None
            else:
                perf_df = None

            # 获取runtime时间
            try:
                cursor.execute("SELECT value FROM meta WHERE name = 'runtime'")
                runtime_result = cursor.fetchone()
                runtime = runtime_result[0] if runtime_result else None
            except sqlite3.DatabaseError:
                logging.warning("Failed to get runtime from database, setting to None")
                runtime = None

            data = parse_frame_slice_db(db_path)

            # 检查是否有有效数据
            if not data:
                logging.info("未找到任何帧数据")
                return None

            NS_TO_MS = 1_000_000
            LOW_FPS_THRESHOLD = 45  # 低FPS阈值

            # 初始化第一帧时间戳
            first_frame_time = None

            stats = {
                "total_frames": 0,
                "frame_stats": {
                    "ui": {
                        "total": 0,
                        "stutter": 0
                    },
                    "render": {
                        "total": 0,
                        "stutter": 0
                    },
                    "sceneboard": {
                        "total": 0,
                        "stutter": 0
                    }
                },
                "stutter_levels": {
                    "level_1": 0,
                    "level_2": 0,
                    "level_3": 0
                },
                "stutter_details": {
                    "ui_stutter": [],
                    "render_stutter": [],
                    "sceneboard_stutter": []
                },
                "fps_stats": {
                    "average_fps": 0,
                    "min_fps": 0,
                    "max_fps": 0,
                    "low_fps_window_count": 0,
                    "low_fps_threshold": LOW_FPS_THRESHOLD,
                    "fps_windows": []
                }
            }

            fps_windows = []
            current_window = {
                "start_time": None,
                "end_time": None,
                "frame_count": 0,
                "frames": set()  # 使用集合来跟踪已处理的帧
            }

            vsync_keys = sorted(data.keys())

            context = {
                "data": data,
                "perf_df": perf_df,
                "perf_conn": perf_conn,
                "step_id": step_id,
                "cursor": cursor  # 添加cursor到context中
            }
            for vsync_key in vsync_keys:
                for frame in data[vsync_key]:
                    if frame["type"] == 1 or frame["flag"] == 2:
                        continue
                    frame_type, stutter_level, stutter_detail = FrameAnalyzer.analyze_single_stuttered_frame(
                        frame, vsync_key, context)
                    stats["frame_stats"][frame_type]["total"] += 1
                    stats["total_frames"] += 1
                    if stutter_level:
                        stats["stutter_levels"][f"level_{stutter_level}"] += 1
                        stats["frame_stats"][frame_type]["stutter"] += 1
                        stutter_type = f"{frame_type}_stutter"
                        stats["stutter_details"][stutter_type].append(stutter_detail)

                    frame_time = frame["ts"]
                    frame_id = f"{vsync_key}_{frame_time}"  # 创建唯一帧标识符

                    # 初始化窗口
                    if current_window["start_time"] is None:
                        current_window["start_time"] = frame_time
                        current_window["end_time"] = frame_time + FrameAnalyzer.WINDOW_SIZE_MS * NS_TO_MS
                        first_frame_time = frame_time

                    # 处理跨多个窗口的情况
                    while frame_time >= current_window["end_time"]:
                        # 计算当前窗口的fps
                        window_duration_ms = max((current_window["end_time"] - current_window["start_time"]) / NS_TO_MS,
                                                 1)
                        window_fps = (current_window["frame_count"] / window_duration_ms) * 1000
                        if window_fps < LOW_FPS_THRESHOLD:
                            stats["fps_stats"]["low_fps_window_count"] += 1

                        # 计算相对于第一帧的偏移时间（秒）
                        start_offset = (current_window["start_time"] - first_frame_time) / NS_TO_MS / 1000  # 转换为秒
                        end_offset = (current_window["end_time"] - first_frame_time) / NS_TO_MS / 1000  # 转换为秒

                        # 保存当前窗口的fps数据
                        fps_windows.append({
                            "start_time": start_offset,
                            "end_time": end_offset,
                            "start_time_ts": current_window["start_time"],
                            "end_time_ts": current_window["end_time"],
                            "frame_count": current_window["frame_count"],
                            "fps": window_fps
                        })

                        # 新窗口推进 - 使用固定窗口大小
                        current_window["start_time"] = current_window["end_time"]
                        current_window["end_time"] = (current_window["start_time"]
                                                      + FrameAnalyzer.WINDOW_SIZE_MS * NS_TO_MS)
                        current_window["frame_count"] = 0
                        current_window["frames"] = set()

                    # 当前窗口更新 - 只计算时间戳在窗口范围内的帧
                    if current_window["start_time"] <= frame_time < current_window["end_time"] and frame_id not in \
                            current_window["frames"]:
                        current_window["frame_count"] += 1
                        current_window["frames"].add(frame_id)

            # 处理最后一个窗口
            if current_window["frame_count"] > 0:
                window_duration_ms = max((current_window["end_time"] - current_window["start_time"]) / NS_TO_MS, 1)
                window_fps = (current_window["frame_count"] / window_duration_ms) * 1000
                if window_fps < LOW_FPS_THRESHOLD:
                    stats["fps_stats"]["low_fps_window_count"] += 1

                # 计算最后一个窗口的偏移时间
                start_offset = (current_window["start_time"] - first_frame_time) / NS_TO_MS / 1000
                end_offset = (current_window["end_time"] - first_frame_time) / NS_TO_MS / 1000

                fps_windows.append({
                    "start_time": start_offset,
                    "end_time": end_offset,
                    "start_time_ts": current_window["start_time"],
                    "end_time_ts": current_window["end_time"],
                    "frame_count": current_window["frame_count"],
                    "fps": window_fps
                })

            # 计算 FPS 概览
            if fps_windows:
                fps_values = [w["fps"] for w in fps_windows]
                stats["fps_stats"]["fps_windows"] = fps_windows
                stats["fps_stats"]["average_fps"] = sum(fps_values) / len(fps_values)
                stats["fps_stats"]["min_fps"] = min(fps_values)
                stats["fps_stats"]["max_fps"] = max(fps_values)
                stats["fps_stats"]["low_fps_window_count"] = stats["fps_stats"]["low_fps_window_count"]
                del stats["fps_stats"]["low_fps_window_count"]
                del stats["fps_stats"]["low_fps_threshold"]

            # 计算各进程的卡顿率
            for process_type in stats["frame_stats"]:
                total = stats["frame_stats"][process_type]["total"]
                stutter = stats["frame_stats"][process_type]["stutter"]
                if total > 0:
                    stats["frame_stats"][process_type]["stutter_rate"] = round(stutter / total, 4)
                else:
                    stats["frame_stats"][process_type]["stutter_rate"] = 0

            # 计算总卡顿率
            total_stutter = sum(stats["frame_stats"][p]["stutter"] for p in stats["frame_stats"])
            stats["total_stutter_frames"] = total_stutter
            stats["stutter_rate"] = round(total_stutter / stats["total_frames"], 4)

            result = {
                "runtime": runtime,
                "statistics": {
                    "total_frames": stats["total_frames"],
                    "frame_stats": stats["frame_stats"],
                    "total_stutter_frames": stats["total_stutter_frames"],
                    "stutter_rate": stats["stutter_rate"],
                    "stutter_levels": stats["stutter_levels"]
                },
                "stutter_details": stats["stutter_details"],
                "fps_stats": stats["fps_stats"]
            }

            return result

        except Exception as e:
            logging.error("分析卡顿帧时发生异常: %s", str(e))
            return None

        finally:
            # 确保数据库连接被正确关闭
            if conn:
                conn.close()
            if perf_conn:
                perf_conn.close()


def parse_frame_slice_db(db_path: str) -> Dict[int, List[Dict[str, Any]]]:
    """
    解析数据库文件，按vsync值分组数据
    结果按vsync值（key）从小到大排序
    只保留flag=0和flag=0, 1, 3的帧（实际渲染的帧）

    Args:
        db_path: 数据库文件路径

    Returns:
        Dict[int, List[Dict[str, Any]]]: 按vsync值分组的帧数据
    """
    try:
        # 连接数据库
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # 直接获取所有数据，不排序
        cursor.execute("""
            SELECT fs.*, t.tid
            FROM frame_slice fs
            LEFT JOIN thread t ON fs.itid = t.itid
        """)

        # 获取列名
        columns = [description[0] for description in cursor.description]

        # 按vsync值分组
        vsync_groups: Dict[int, List[Dict[str, Any]]] = {}
        total_frames = 0

        # 遍历所有行，将数据转换为字典并按vsync分组
        for row in cursor.fetchall():
            row_dict = dict(zip(columns, row))

            vsync_value = row_dict['vsync']
            # 跳过vsync为None的数据
            if vsync_value is None:
                continue
            try:
                # 确保vsync_value是整数
                vsync_value = int(vsync_value)
            except (ValueError, TypeError):
                continue

            if vsync_value not in vsync_groups:
                vsync_groups[vsync_value] = []

            vsync_groups[vsync_value].append(row_dict)
            total_frames += 1

        # 关闭数据库连接
        conn.close()

        # 创建有序字典，按key值排序
        return dict(sorted(vsync_groups.items()))

    except sqlite3.Error as e:
        raise RuntimeError(f"数据库操作错误: {str(e)}\n{traceback.format_exc()}") from e
    except Exception as e:
        raise RuntimeError(f"处理过程中发生错误: {str(e)}\n{traceback.format_exc()}") from e


def get_frame_type(frame: dict, cursor, step_id: str = None) -> str:
    """
    获取帧的类型（进程名）

    参数:
        frame: 帧数据字典
        cursor: 数据库游标
        step_id: 步骤ID，用于缓存key

    返回:
        str: 'ui'/'render'/'sceneboard'
    """
    ipid = frame.get("ipid")
    if ipid is None or cursor is None:
        return "ui"

    # 确定缓存key
    cache_key = step_id if step_id else str(cursor.connection)

    # 检查缓存是否存在，如果不存在则先获取
    process_cache_data = FrameAnalyzer.get_process_cache_by_key(cache_key)
    if process_cache_data.empty:
        # 缓存不存在，需要先获取并缓存
        trace_conn = cursor.connection
        FrameAnalyzer.get_process_cache(trace_conn, step_id)
        # 再次获取缓存
        process_cache_data = FrameAnalyzer.get_process_cache_by_key(cache_key)
        if process_cache_data.empty:
            logging.warning("process缓存为空，无法获取进程类型")
            return "ui"

    # 从缓存中查找进程名
    process_info = process_cache_data[process_cache_data['ipid'] == ipid]

    if process_info.empty:
        return "ui"

    process_name = process_info['name'].iloc[0]

    # 根据进程名返回类型
    if process_name == "render_service":
        return "render"
    if process_name == "ohos.sceneboard":
        return "sceneboard"
    return "ui"
