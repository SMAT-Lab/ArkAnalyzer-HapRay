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
from typing import Dict, Any, List, Optional

import pandas as pd

from .frame_load_calculator import FrameLoadCalculator
from .frame_data_parser import parse_frame_slice_db, get_frame_type


class StutteredFrameAnalyzer:
    """卡顿帧分析器

    专门用于分析卡顿帧，包括：
    1. 卡顿帧检测和分级
    2. FPS计算和统计
    3. 卡顿详情分析
    4. 调用链分析

    帧标志 (flag) 定义：
    - flag = 0: 实际渲染帧不卡帧（正常帧）
    - flag = 1: 实际渲染帧卡帧（expectEndTime < actualEndTime为异常）
    - flag = 2: 数据不需要绘制（空帧，不参与卡顿分析）
    - flag = 3: rs进程与app进程起止异常（|expRsStartTime - expUiEndTime| < 1ms 正常，否则异常）

    卡顿分级策略：
    - 等级 1 (轻微卡顿): flag=3 或 flag=1 且超出帧数 < 2
    - 等级 2 (中度卡顿): flag=1 且超出帧数 2-6
    - 等级 3 (严重卡顿): flag=1 且超出帧数 > 6

    注意：flag=3 归类为轻微卡顿的原因：
    1. 时间尺度：flag=3 异常阈值仅 1ms，远小于轻微卡顿的 33.34ms 阈值
    2. 异常性质：进程间协调异常对用户体验影响较小
    3. 保守评估：避免将轻微异常误判为严重问题
    """

    # 帧标志常量
    FLAG_NORMAL = 0      # 实际渲染帧不卡帧
    FLAG_STUTTER = 1     # 实际渲染帧卡帧
    FLAG_NO_DRAW = 2     # 数据不需要绘制
    FLAG_PROCESS_ERROR = 3  # rs进程与app进程起止异常

    # 卡顿分级阈值常量
    FRAME_DURATION = 16.67  # 毫秒，60fps基准帧时长
    STUTTER_LEVEL_1_FRAMES = 2  # 1级卡顿阈值：0-2帧（33.34ms）
    STUTTER_LEVEL_2_FRAMES = 6  # 2级卡顿阈值：2-6帧（100ms）
    NS_TO_MS = 1_000_000
    WINDOW_SIZE_MS = 1000  # fps窗口大小：1s

    def __init__(self, debug_vsync_enabled: bool = False):
        """
        初始化卡顿帧分析器

        Args:
            debug_vsync_enabled: VSync调试开关
        """
        self.load_calculator = FrameLoadCalculator(debug_vsync_enabled)

    def analyze_stuttered_frames(
        self,
        db_path: str,
        perf_db_path: str = None,
        step_id: str = None
    ) -> Optional[dict]:
        """分析卡顿帧数据并计算FPS

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

            LOW_FPS_THRESHOLD = 45  # 低FPS阈值

            # 初始化第一帧时间戳
            first_frame_time = None

            stats = {
                "total_frames": 0,
                "frame_stats": {
                    "ui": {"total": 0, "stutter": 0},
                    "render": {"total": 0, "stutter": 0},
                    "sceneboard": {"total": 0, "stutter": 0}
                },
                "stutter_levels": {"level_1": 0, "level_2": 0, "level_3": 0},
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

                    frame_type, stutter_level, stutter_detail = self.analyze_single_stuttered_frame(
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
                        current_window["end_time"] = frame_time + self.WINDOW_SIZE_MS * self.NS_TO_MS
                        first_frame_time = frame_time

                    # 处理跨多个窗口的情况
                    while frame_time >= current_window["end_time"]:
                        # 计算当前窗口的fps
                        window_duration_ms = max(
                            (current_window["end_time"] - current_window["start_time"]) / self.NS_TO_MS, 1)
                        window_fps = (current_window["frame_count"] / window_duration_ms) * 1000
                        if window_fps < LOW_FPS_THRESHOLD:
                            stats["fps_stats"]["low_fps_window_count"] += 1

                        # 计算相对于第一帧的偏移时间（秒）
                        start_offset = (current_window["start_time"] - first_frame_time) / self.NS_TO_MS / 1000
                        end_offset = (current_window["end_time"] - first_frame_time) / self.NS_TO_MS / 1000

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
                        current_window["end_time"] = (
                            current_window["start_time"] + self.WINDOW_SIZE_MS * self.NS_TO_MS)
                        current_window["frame_count"] = 0
                        current_window["frames"] = set()

                    # 当前窗口更新 - 只计算时间戳在窗口范围内的帧
                    if (current_window["start_time"] <= frame_time < current_window["end_time"]
                            and frame_id not in current_window["frames"]):
                        current_window["frame_count"] += 1
                        current_window["frames"].add(frame_id)

            # 处理最后一个窗口
            if current_window["frame_count"] > 0:
                window_duration_ms = max((current_window["end_time"] - current_window["start_time"]) / self.NS_TO_MS, 1)
                window_fps = (current_window["frame_count"] / window_duration_ms) * 1000
                if window_fps < LOW_FPS_THRESHOLD:
                    stats["fps_stats"]["low_fps_window_count"] += 1

                # 计算最后一个窗口的偏移时间
                start_offset = (current_window["start_time"] - first_frame_time) / self.NS_TO_MS / 1000
                end_offset = (current_window["end_time"] - first_frame_time) / self.NS_TO_MS / 1000

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

    def analyze_single_stuttered_frame(self, frame, vsync_key, context):
        """分析单个卡顿帧，返回分析结果和统计信息"""
        data = context["data"]
        perf_df = context["perf_df"]
        perf_conn = context["perf_conn"]
        step_id = context["step_id"]
        cursor = context.get("cursor")  # 从context中获取cursor

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
        exceed_time = exceed_time_ns / self.NS_TO_MS
        exceed_frames = exceed_time / self.FRAME_DURATION

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
                        callchain_info = self.load_calculator.analyze_perf_callchain(
                            perf_conn,
                            int(sample['callchain_id']),
                            step_id=step_id
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

        # 卡顿分级逻辑
        # flag=3 归类为轻微卡顿：进程间异常阈值仅 1ms，远小于轻微卡顿的 33.34ms 阈值
        if frame.get("flag") == 3 or exceed_frames < self.STUTTER_LEVEL_1_FRAMES:
            stutter_level = 1
            level_desc = "轻微卡顿"
        elif exceed_frames < self.STUTTER_LEVEL_2_FRAMES:
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

    def classify_stutter_level(self, exceed_frames: float, flag: int = None) -> tuple:
        """分类卡顿等级

        根据卡顿定义进行分级：
        
        帧标志 (flag) 含义：
        - flag = 0: 实际渲染帧不卡帧（正常帧）
        - flag = 1: 实际渲染帧卡帧（expectEndTime < actualEndTime为异常）
        - flag = 2: 数据不需要绘制（空帧，不参与卡顿分析）
        - flag = 3: rs进程与app进程起止异常（|expRsStartTime - expUiEndTime| < 1ms 正常，否则异常）

        卡顿分级逻辑：
        1. 轻微卡顿 (Level 1): 
           - flag=3: 进程间异常（1ms阈值 < 33.34ms轻微卡顿阈值，保守评估）
           - flag=1 且超出帧数 < 2: 实际渲染卡帧但超出时间较少（0-33.34ms）
        
        2. 中度卡顿 (Level 2): 
           - flag=1 且超出帧数 2-6: 实际渲染卡帧且超出时间明显（33.34-100ms）
        
        3. 严重卡顿 (Level 3): 
           - flag=1 且超出帧数 > 6: 实际渲染卡帧且超出时间严重（>100ms）

        Args:
            exceed_frames: 超出的帧数（基于60fps基准：16.67ms/帧）
            flag: 帧标志（0-3）

        Returns:
            tuple: (stutter_level, level_desc)
        """
        # flag=3 归类为轻微卡顿的原因：
        # 1. 时间尺度：flag=3 异常阈值仅 1ms，远小于轻微卡顿的 33.34ms 阈值
        # 2. 异常性质：进程间协调异常对用户体验影响较小
        # 3. 保守评估：避免将轻微异常误判为严重问题
        if flag == 3 or exceed_frames < self.STUTTER_LEVEL_1_FRAMES:
            return 1, "轻微卡顿"
        if exceed_frames < self.STUTTER_LEVEL_2_FRAMES:
            return 2, "中度卡顿"
        return 3, "严重卡顿"

    def calculate_fps_statistics(self, fps_windows: List[Dict[str, Any]]) -> Dict[str, Any]:
        """计算FPS统计信息

        Args:
            fps_windows: FPS窗口列表

        Returns:
            Dict: FPS统计信息
        """
        if not fps_windows:
            return {
                "average_fps": 0,
                "min_fps": 0,
                "max_fps": 0,
                "fps_windows": []
            }

        fps_values = [w["fps"] for w in fps_windows]

        return {
            "average_fps": sum(fps_values) / len(fps_values),
            "min_fps": min(fps_values),
            "max_fps": max(fps_values),
            "fps_windows": fps_windows
        }
