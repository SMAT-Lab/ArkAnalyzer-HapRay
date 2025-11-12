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
import os
import sqlite3
import time
import traceback
from typing import Any, Optional

from ...config.config import Config
from .frame_constants import (
    ANALYSIS_TIME_WARNING_SECONDS,
    FLAG_NO_DRAW,
    FLAG_PROCESS_ERROR,
    FLAG_STUTTER,
    FPS_WINDOW_SIZE_MS,
    FRAME_DURATION_MS,
    FRAME_TYPE_EXPECT,
    LOW_FPS_THRESHOLD,
    NANOSECONDS_TO_MILLISECONDS,
    PERF_DB_SIZE_ERROR_MB,
    PERF_DB_SIZE_WARNING_MB,
    STUTTER_LEVEL_1_FRAMES,
    STUTTER_LEVEL_2_FRAMES,
    TOP_FRAMES_FOR_CALLCHAIN,
)
from .frame_core_cache_manager import FrameCacheManager
from .frame_core_load_calculator import FrameLoadCalculator
from .frame_data_parser import get_frame_type, parse_frame_slice_db
from .frame_time_utils import FrameTimeUtils

# import pandas as pd  # 未使用


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
        step_id: str = None,
        top_n_analysis: int = None,
        app_pids: list = None,
    ) -> Optional[dict]:
        """分析卡顿帧数据并计算FPS

        Args:
            db_path: 数据库文件路径
            perf_db_path: perf数据库文件路径，用于调用链分析
            step_id: 步骤ID，用于缓存key
            top_n_analysis: 进行深度分析的top卡顿帧数量，为None时使用配置文件的值
            app_pids: 应用进程ID列表，用于过滤应用相关的帧数据

        Returns:
            Optional[dict]: 分析结果数据，如果没有数据或分析失败则返回None
        """
        # 从配置获取参数
        if top_n_analysis is None:
            top_n_analysis = Config.get('frame_analysis.top_n_analysis', TOP_FRAMES_FOR_CALLCHAIN)

        analysis_start_time = time.time()

        # 记录分析日志
        logging.info('=== 开始卡顿帧分析（轻量模式） ===')
        logging.info('Step ID: %s', step_id)
        logging.info('Trace DB: %s', db_path)
        logging.info('Perf DB: %s', perf_db_path)
        logging.info('TOP N分析: %d', top_n_analysis)

        # 检查数据库文件大小
        if perf_db_path and os.path.exists(perf_db_path):
            try:
                perf_file_size = os.path.getsize(perf_db_path) / (1024 * 1024)  # MB
                logging.info('性能数据库大小: %.1f MB', perf_file_size)

                large_threshold = PERF_DB_SIZE_WARNING_MB
                huge_threshold = PERF_DB_SIZE_ERROR_MB

                if perf_file_size > huge_threshold:
                    logging.error('性能数据库过大 (%.1f MB)，可能导致内存不足或处理超时', perf_file_size)
                elif perf_file_size > large_threshold:
                    logging.warning('性能数据库较大 (%.1f MB)，处理可能需要较长时间', perf_file_size)
            except Exception as e:
                logging.warning('无法检查性能数据库文件大小: %s', str(e))

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

                    # ==================== 标准化缓存检查和使用 ====================
                    # 在分析开始前，确保所有需要的数据都已缓存
                    if step_id:
                        # 确保帧负载数据缓存已初始化
                        FrameCacheManager.ensure_data_cached('frame_loads', step_id=step_id)

                    # 使用缓存管理器获取perf样本数据
                    perf_df = FrameCacheManager.get_perf_samples(perf_conn, step_id)
                except Exception as e:
                    logging.warning('无法连接perf数据库或获取数据: %s', str(e))
                    perf_df = None
            else:
                perf_df = None

            # 获取runtime时间
            try:
                cursor.execute("SELECT value FROM meta WHERE name = 'runtime'")
                runtime_result = cursor.fetchone()
                runtime = runtime_result[0] if runtime_result else None
            except sqlite3.DatabaseError:
                logging.warning('Failed to get runtime from database, setting to None')
                runtime = None

            # 始终获取所有帧数据用于统计（fps_stats, frame_stats等）
            logging.info('获取所有进程的帧数据用于统计分析')
            data = parse_frame_slice_db(db_path)

            # 检查是否有有效数据
            if not data:
                logging.info('未找到任何帧数据')
                return None

            # 如果提供了app_pids，记录用于后续的调用链分析过滤
            if app_pids:
                logging.info('应用进程PID列表: %s (用于调用链分析过滤)', app_pids)

            # 初始化第一帧时间戳（用于相对时间计算）
            first_frame_time = None

            stats = {
                'total_frames': 0,
                'frame_stats': {
                    'ui': {'total': 0, 'stutter': 0},
                    'render': {'total': 0, 'stutter': 0},
                    'sceneboard': {'total': 0, 'stutter': 0},
                },
                'stutter_levels': {'level_1': 0, 'level_2': 0, 'level_3': 0},
                'stutter_details': {'ui_stutter': [], 'render_stutter': [], 'sceneboard_stutter': []},
                'fps_stats': {
                    'average_fps': 0,
                    'min_fps': 0,
                    'max_fps': 0,
                    'low_fps_window_count': 0,
                    'low_fps_threshold': LOW_FPS_THRESHOLD,
                    'fps_windows': [],
                },
            }

            fps_windows = []
            current_window = {
                'start_time': None,
                'end_time': None,
                'frame_count': 0,
                'frames': set(),  # 使用集合来跟踪已处理的帧
            }

            vsync_keys = sorted(data.keys())

            # 轻量模式：快速收集所有卡顿帧信息（不进行调用链分析）
            logging.info('轻量模式：快速收集卡顿帧信息...')
            all_stutter_frames = []

            context = {
                'data': data,
                'perf_df': perf_df,
                'perf_conn': perf_conn,
                'step_id': step_id,
                'cursor': cursor,
            }

            for vsync_key in vsync_keys:
                for frame in data[vsync_key]:
                    if frame['type'] == FRAME_TYPE_EXPECT or frame['flag'] == FLAG_NO_DRAW:
                        continue

                    # 始终使用轻量级模式进行初步分析
                    frame_type, stutter_level, stutter_detail = self.analyze_single_stuttered_frame(
                        frame, vsync_key, context
                    )

                    stats['frame_stats'][frame_type]['total'] += 1
                    stats['total_frames'] += 1

                    if stutter_level:
                        stats['stutter_levels'][f'level_{stutter_level}'] += 1
                        stats['frame_stats'][frame_type]['stutter'] += 1

                        # 收集卡顿帧信息用于排序
                        all_stutter_frames.append(
                            {
                                'frame': frame,
                                'vsync_key': vsync_key,
                                'frame_type': frame_type,
                                'stutter_level': stutter_level,
                                'stutter_detail': stutter_detail,
                                'severity_score': self._calculate_severity_score(stutter_detail),
                            }
                        )

                    # FPS计算逻辑保持不变
                    frame_time = frame['ts']
                    frame_id = f'{vsync_key}_{frame_time}'

                    if current_window['start_time'] is None:
                        current_window['start_time'] = frame_time
                        current_window['end_time'] = frame_time + FPS_WINDOW_SIZE_MS * NANOSECONDS_TO_MILLISECONDS
                        first_frame_time = frame_time

                    while frame_time >= current_window['end_time']:
                        window_duration_ms = max(
                            (current_window['end_time'] - current_window['start_time']) / NANOSECONDS_TO_MILLISECONDS, 1
                        )
                        window_fps = (current_window['frame_count'] / window_duration_ms) * 1000
                        if window_fps < LOW_FPS_THRESHOLD:
                            stats['fps_stats']['low_fps_window_count'] += 1

                        start_offset = FrameTimeUtils.convert_to_relative_nanoseconds(
                            current_window['start_time'], first_frame_time
                        )
                        end_offset = FrameTimeUtils.convert_to_relative_nanoseconds(
                            current_window['end_time'], first_frame_time
                        )

                        fps_windows.append(
                            {
                                'start_time': start_offset,
                                'end_time': end_offset,
                                'start_time_ts': int(current_window['start_time']),
                                'end_time_ts': int(current_window['end_time']),
                                'frame_count': current_window['frame_count'],
                                'fps': window_fps,
                            }
                        )

                        current_window['start_time'] = current_window['end_time']
                        current_window['end_time'] = (
                            current_window['start_time'] + FPS_WINDOW_SIZE_MS * NANOSECONDS_TO_MILLISECONDS
                        )
                        current_window['frame_count'] = 0
                        current_window['frames'] = set()

                    if (
                        current_window['start_time'] <= frame_time < current_window['end_time']
                        and frame_id not in current_window['frames']
                    ):
                        current_window['frame_count'] += 1
                        current_window['frames'].add(frame_id)

            if all_stutter_frames:
                # 简化记录其余卡顿帧（不包含调用链分析）
                for stutter_info in all_stutter_frames:
                    frame_type = stutter_info['frame_type']
                    stutter_detail = stutter_info['stutter_detail']

                    # 移除调用链信息以节省内存
                    simplified_detail = stutter_detail.copy()
                    simplified_detail['sample_callchains'] = []  # 清空调用链
                    simplified_detail['frame_load'] = 0  # 清空帧负载

                    stutter_type = f'{frame_type}_stutter'
                    stats['stutter_details'][stutter_type].append(simplified_detail)

            # 处理最后一个窗口
            if current_window['frame_count'] > 0:
                window_duration_ms = max(
                    (current_window['end_time'] - current_window['start_time']) / NANOSECONDS_TO_MILLISECONDS, 1
                )
                window_fps = (current_window['frame_count'] / window_duration_ms) * 1000
                if window_fps < LOW_FPS_THRESHOLD:
                    stats['fps_stats']['low_fps_window_count'] += 1

                # 计算相对于第一帧的时间（纳秒）
                start_offset = FrameTimeUtils.convert_to_relative_nanoseconds(
                    current_window['start_time'], first_frame_time
                )
                end_offset = FrameTimeUtils.convert_to_relative_nanoseconds(
                    current_window['end_time'], first_frame_time
                )

                fps_windows.append(
                    {
                        'start_time': start_offset,
                        'end_time': end_offset,
                        'start_time_ts': int(current_window['start_time']),  # 确保返回Python原生int类型
                        'end_time_ts': int(current_window['end_time']),  # 确保返回Python原生int类型
                        'frame_count': current_window['frame_count'],
                        'fps': window_fps,
                    }
                )

            # 计算 FPS 概览
            if fps_windows:
                fps_values = [w['fps'] for w in fps_windows]
                stats['fps_stats']['fps_windows'] = fps_windows
                stats['fps_stats']['average_fps'] = sum(fps_values) / len(fps_values)
                stats['fps_stats']['min_fps'] = min(fps_values)
                stats['fps_stats']['max_fps'] = max(fps_values)
                stats['fps_stats']['low_fps_window_count'] = stats['fps_stats']['low_fps_window_count']
                del stats['fps_stats']['low_fps_window_count']
                del stats['fps_stats']['low_fps_threshold']

            # 计算各进程的卡顿率
            for process_type in stats['frame_stats']:
                total = stats['frame_stats'][process_type]['total']
                stutter = stats['frame_stats'][process_type]['stutter']
                if total > 0:
                    stats['frame_stats'][process_type]['stutter_rate'] = round(stutter / total, 4)
                else:
                    stats['frame_stats'][process_type]['stutter_rate'] = 0

            # 计算总卡顿率
            total_stutter = int(
                sum(stats['frame_stats'][p]['stutter'] for p in stats['frame_stats'])
            )  # 确保返回Python原生int类型
            stats['total_stutter_frames'] = total_stutter
            # 防止除零错误
            if stats['total_frames'] > 0:
                stats['stutter_rate'] = round(total_stutter / stats['total_frames'], 4)
            else:
                stats['stutter_rate'] = 0.0

            # 分析完成，记录总结信息
            analysis_total_time = time.time() - analysis_start_time
            logging.info('=== 卡顿帧分析完成 ===')
            logging.info('总耗时: %.2f秒', analysis_total_time)
            logging.info(
                '分析结果: 总帧数=%d, 卡顿帧数=%d, 卡顿率=%.2f%%',
                stats['total_frames'],
                stats['total_stutter_frames'],
                stats['stutter_rate'] * 100,
            )

            if analysis_total_time > ANALYSIS_TIME_WARNING_SECONDS:
                logging.warning('卡顿帧分析耗时较长: %.2f秒', analysis_total_time)

            return {
                'runtime': runtime,
                'statistics': {
                    'total_frames': stats['total_frames'],
                    'frame_stats': stats['frame_stats'],
                    'total_stutter_frames': stats['total_stutter_frames'],
                    'stutter_rate': stats['stutter_rate'],
                    'stutter_levels': stats['stutter_levels'],
                },
                'stutter_details': stats['stutter_details'],
                'fps_stats': stats['fps_stats'],
            }

        except Exception as e:
            analysis_error_time = time.time() - analysis_start_time
            logging.error('=== 卡顿帧分析失败 ===')
            logging.error('失败耗时: %.2f秒', analysis_error_time)
            logging.error('异常信息: %s', str(e))
            logging.error('异常堆栈跟踪:\n%s', traceback.format_exc())
            return None

        finally:
            # 确保数据库连接被正确关闭
            if conn:
                conn.close()
            if perf_conn:
                perf_conn.close()

    def analyze_single_stuttered_frame(self, frame, vsync_key, context):
        """分析单个卡顿帧

        Args:
            frame: 帧数据
            vsync_key: VSync键
            context: 上下文信息

        Returns:
            tuple: (frame_type, stutter_level, stutter_detail)
        """
        data = context['data']
        step_id = context['step_id']
        cursor = context.get('cursor')  # 从context中获取cursor

        frame_type = get_frame_type(frame, cursor, step_id=step_id)
        stutter_detail = None
        stutter_level = None
        level_desc = None
        frame_load = 0
        sample_callchains = []

        if frame.get('flag') != FLAG_STUTTER:
            return frame_type, stutter_level, stutter_detail

        expected_frame = next((f for f in data[vsync_key] if f['type'] == FRAME_TYPE_EXPECT), None)
        if expected_frame is None:
            return frame_type, stutter_level, stutter_detail

        exceed_time_ns = frame['dur'] - expected_frame['dur']
        exceed_time = exceed_time_ns / NANOSECONDS_TO_MILLISECONDS
        exceed_frames = exceed_time / FRAME_DURATION_MS

        # 卡顿分级逻辑
        # flag=3 归类为轻微卡顿：进程间异常阈值仅 1ms，远小于轻微卡顿的 33.34ms 阈值
        if frame.get('flag') == FLAG_PROCESS_ERROR or exceed_frames < STUTTER_LEVEL_1_FRAMES:
            stutter_level = 1
            level_desc = '轻微卡顿'
        elif exceed_frames < STUTTER_LEVEL_2_FRAMES:
            stutter_level = 2
            level_desc = '中度卡顿'
        else:
            stutter_level = 3
            level_desc = '严重卡顿'

        # 获取第一帧时间戳用于相对时间计算
        # 从缓存中获取第一帧时间戳
        if context and 'step_id' in context:
            step_id = context['step_id']
            try:
                # 从缓存中获取第一帧时间戳
                first_frame_time = FrameCacheManager.get_first_frame_timestamp(None, step_id)
            except Exception:
                # 如果获取缓存失败，则使用卡顿帧中的最小时间戳作为备选
                first_frame_time = min(f['ts'] for vsync in data.values() for f in vsync) if data else 0
        else:
            # 如果无法获取step_id，则使用卡顿帧中的最小时间戳作为备选
            first_frame_time = min(f['ts'] for vsync in data.values() for f in vsync) if data else 0

        stutter_detail = {
            'vsync': vsync_key,
            'ts': FrameTimeUtils.convert_to_relative_nanoseconds(frame['ts'], first_frame_time),
            'actual_duration': frame['dur'],
            'expected_duration': expected_frame['dur'],
            'exceed_time': exceed_time,
            'exceed_frames': exceed_frames,
            'stutter_level': stutter_level,
            'level_description': level_desc,
            'src': frame.get('src'),
            'dst': frame.get('dst'),
            'frame_load': int(frame_load),
            'sample_callchains': sorted(sample_callchains, key=lambda x: x['event_count'], reverse=True),
        }

        return frame_type, stutter_level, stutter_detail

    def _calculate_severity_score(self, stutter_detail: dict) -> float:
        """计算卡顿严重程度评分，用于排序

        使用配置文件中的权重进行评分计算

        Args:
            stutter_detail: 卡顿详情

        Returns:
            float: 严重程度评分，分数越高越严重
        """
        if not stutter_detail:
            return 0.0

        # 使用默认权重
        weights = {'level_1': 10, 'level_2': 50, 'level_3': 100, 'exceed_frames_weight': 5.0, 'exceed_time_weight': 0.1}

        # 基础分数：根据卡顿等级
        stutter_level = stutter_detail.get('stutter_level', 1)
        level_key = f'level_{stutter_level}'
        base_score = weights.get(level_key, weights.get('level_1', 10))

        # 超出帧数权重
        exceed_frames = stutter_detail.get('exceed_frames', 0)
        frame_score = exceed_frames * weights.get('exceed_frames_weight', 5.0)

        # 超出时间权重（毫秒）
        exceed_time = stutter_detail.get('exceed_time', 0)
        time_score = exceed_time * weights.get('exceed_time_weight', 0.1)

        return base_score + frame_score + time_score

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
        if flag == FLAG_PROCESS_ERROR or exceed_frames < STUTTER_LEVEL_1_FRAMES:
            return 1, '轻微卡顿'
        if exceed_frames < STUTTER_LEVEL_2_FRAMES:
            return 2, '中度卡顿'
        return 3, '严重卡顿'

    def calculate_fps_statistics(self, fps_windows: list[dict[str, Any]]) -> dict[str, Any]:
        """计算FPS统计信息

        Args:
            fps_windows: FPS窗口列表

        Returns:
            Dict: FPS统计信息
        """
        if not fps_windows:
            return {'average_fps': 0, 'min_fps': 0, 'max_fps': 0, 'fps_windows': []}

        fps_values = [w['fps'] for w in fps_windows]

        return {
            'average_fps': sum(fps_values) / len(fps_values),
            'min_fps': min(fps_values),
            'max_fps': max(fps_values),
            'fps_windows': fps_windows,
        }

    def _convert_dataframe_to_vsync_groups(self, frames_df) -> dict[int, list[dict[str, Any]]]:
        """将DataFrame转换为按vsync分组的字典格式

        Args:
            frames_df: 帧数据DataFrame

        Returns:
            Dict[int, List[Dict]]: 按vsync值分组的帧数据
        """
        vsync_groups = {}

        for _, row in frames_df.iterrows():
            vsync_value = row.get('vsync')

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

            # 将pandas Series转换为字典
            row_dict = row.to_dict()
            vsync_groups[vsync_value].append(row_dict)

        # 按vsync值排序
        return dict(sorted(vsync_groups.items()))
