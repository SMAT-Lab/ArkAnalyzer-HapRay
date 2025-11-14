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
import time
import traceback
from typing import Optional

from .frame_constants import (
    ANALYSIS_TIME_WARNING_SECONDS,
    FLAG_NO_DRAW,
    FLAG_PROCESS_ERROR,
    FLAG_STUTTER,
    FPS_WINDOW_SIZE_MS,
    FRAME_DURATION_MS,
    FRAME_TYPE_EXPECT,
    MILLISECONDS_TO_NANOSECONDS,
    PROCESS_TYPE_RENDER,
    PROCESS_TYPE_SCENEBOARD,
    PROCESS_TYPE_UI,
    STUTTER_LEVEL_1_FRAMES,
    STUTTER_LEVEL_2_FRAMES,
)
from .frame_core_cache_manager import FrameCacheManager
from .frame_time_utils import FrameTimeUtils


class StutteredFrameAnalyzer:
    """卡顿帧分析器

    专门用于分析卡顿帧，包括：
    1. 卡顿帧检测和分级
    2. FPS计算和统计
    3. 卡顿详情分析

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

    def __init__(self, debug_vsync_enabled: bool = False, cache_manager: FrameCacheManager = None):
        """
        初始化卡顿帧分析器

        Args:
            debug_vsync_enabled: VSync调试开关（保留以兼容接口）
            cache_manager: 缓存管理器实例
        """
        self.cache_manager = cache_manager

    def analyze_stuttered_frames(self) -> Optional[dict]:
        """分析卡顿帧数据并计算FPS

        Returns:
            Optional[dict]: 分析结果数据，如果没有数据或分析失败则返回None
        """

        analysis_start_time = time.time()

        try:
            perf_df = self.cache_manager.get_perf_samples()
            data = self._load_frame_data()
            if not data:
                return None

            stats = self._initialize_stats()
            context = self._create_analysis_context(data, perf_df)

            fps_windows = self._analyze_all_frames(data, stats, context)

            self._finalize_fps_stats(stats, fps_windows)
            self._calculate_stutter_rates(stats)

            analysis_total_time = time.time() - analysis_start_time
            self._log_analysis_complete(analysis_total_time, stats)

            return self._build_result(stats)

        except Exception as e:
            analysis_error_time = time.time() - analysis_start_time
            logging.error('=== 卡顿帧分析失败 ===')
            logging.error('失败耗时: %.2f秒', analysis_error_time)
            logging.error('异常信息: %s', str(e))
            logging.error('异常堆栈跟踪:\n%s', traceback.format_exc())
            return None

    def _analyze_single_stuttered_frame(self, frame, vsync_key, context):
        """分析单个卡顿帧

        Args:
            frame: 帧数据
            vsync_key: VSync键
            context: 上下文信息

        Returns:
            tuple: (frame_type, stutter_level, stutter_detail)
        """
        data = context['data']
        frame_type = self.cache_manager.get_frame_type(frame)
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
        exceed_time = exceed_time_ns / MILLISECONDS_TO_NANOSECONDS
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
        try:
            # 从缓存中获取第一帧时间戳
            first_frame_time = self.cache_manager.get_first_frame_timestamp() if self.cache_manager else 0
        except Exception:
            # 如果获取缓存失败，则使用卡顿帧中的最小时间戳作为备选
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

    def _load_frame_data(self) -> dict:
        """加载帧数据"""
        data = self.cache_manager.parse_frame_slice_db() if self.cache_manager else {}
        return data

    def _initialize_stats(self) -> dict:
        """初始化统计信息"""
        return {
            'total_frames': 0,
            'frame_stats': {
                PROCESS_TYPE_UI: {'total': 0, 'stutter': 0},
                PROCESS_TYPE_RENDER: {'total': 0, 'stutter': 0},
                PROCESS_TYPE_SCENEBOARD: {'total': 0, 'stutter': 0},
            },
            'stutter_levels': {'level_1': 0, 'level_2': 0, 'level_3': 0},
            'stutter_details': {
                f'{PROCESS_TYPE_UI}_stutter': [],
                f'{PROCESS_TYPE_RENDER}_stutter': [],
                f'{PROCESS_TYPE_SCENEBOARD}_stutter': [],
            },
            'fps_stats': {
                'average_fps': 0,
                'min_fps': 0,
                'max_fps': 0,
                'fps_windows': [],
            },
        }

    def _create_analysis_context(self, data, perf_df) -> dict:
        """创建分析上下文"""
        return {'data': data, 'perf_df': perf_df}

    def _analyze_all_frames(self, data: dict, stats: dict, context: dict) -> list:
        """分析所有帧并收集卡顿信息"""
        fps_windows = []
        current_window = {'start_time': None, 'end_time': None, 'frame_count': 0, 'frames': set()}
        all_stutter_frames = []
        first_frame_time = None

        for vsync_key in sorted(data.keys()):
            for frame in data[vsync_key]:
                if frame['type'] == FRAME_TYPE_EXPECT or frame['flag'] == FLAG_NO_DRAW:
                    continue

                frame_type, stutter_level, stutter_detail = self._analyze_single_stuttered_frame(
                    frame, vsync_key, context
                )

                stats['frame_stats'][frame_type]['total'] += 1
                stats['total_frames'] += 1

                if stutter_level:
                    stats['stutter_levels'][f'level_{stutter_level}'] += 1
                    stats['frame_stats'][frame_type]['stutter'] += 1
                    all_stutter_frames.append(
                        {
                            'frame': frame,
                            'vsync_key': vsync_key,
                            'frame_type': frame_type,
                            'stutter_level': stutter_level,
                            'stutter_detail': stutter_detail,
                        }
                    )

                first_frame_time, fps_windows = self._process_fps_window(
                    frame, vsync_key, current_window, fps_windows, first_frame_time, stats
                )

        self._add_stutter_details(all_stutter_frames, stats)
        self._finalize_last_fps_window(current_window, fps_windows, first_frame_time, stats)

        return fps_windows

    def _process_fps_window(
        self,
        frame: dict,
        vsync_key: int,
        current_window: dict,
        fps_windows: list,
        first_frame_time: Optional[int],
        stats: dict,
    ) -> tuple:
        """处理FPS窗口"""
        frame_time = frame['ts']
        frame_id = f'{vsync_key}_{frame_time}'

        if current_window['start_time'] is None:
            current_window['start_time'] = frame_time
            current_window['end_time'] = frame_time + FPS_WINDOW_SIZE_MS * MILLISECONDS_TO_NANOSECONDS
            first_frame_time = frame_time

        while frame_time >= current_window['end_time']:
            fps_windows.append(self._create_fps_window(current_window, first_frame_time, stats))
            self._advance_fps_window(current_window)

        if (
            current_window['start_time'] <= frame_time < current_window['end_time']
            and frame_id not in current_window['frames']
        ):
            current_window['frame_count'] += 1
            current_window['frames'].add(frame_id)

        return first_frame_time, fps_windows

    def _create_fps_window(self, current_window: dict, first_frame_time: int, stats: dict) -> dict:
        """创建FPS窗口记录"""
        window_duration_ms = max(
            (current_window['end_time'] - current_window['start_time']) / MILLISECONDS_TO_NANOSECONDS, 1
        )
        window_fps = (current_window['frame_count'] / window_duration_ms) * 1000

        return {
            'start_time': FrameTimeUtils.convert_to_relative_nanoseconds(
                current_window['start_time'], first_frame_time
            ),
            'end_time': FrameTimeUtils.convert_to_relative_nanoseconds(current_window['end_time'], first_frame_time),
            'start_time_ts': int(current_window['start_time']),
            'end_time_ts': int(current_window['end_time']),
            'frame_count': current_window['frame_count'],
            'fps': window_fps,
        }

    def _advance_fps_window(self, current_window: dict) -> None:
        """推进FPS窗口"""
        current_window['start_time'] = current_window['end_time']
        current_window['end_time'] = current_window['start_time'] + FPS_WINDOW_SIZE_MS * MILLISECONDS_TO_NANOSECONDS
        current_window['frame_count'] = 0
        current_window['frames'] = set()

    def _add_stutter_details(self, all_stutter_frames: list, stats: dict) -> None:
        """添加卡顿详情到统计信息"""
        for stutter_info in all_stutter_frames:
            simplified_detail = stutter_info['stutter_detail'].copy()
            simplified_detail['sample_callchains'] = []
            simplified_detail['frame_load'] = 0
            stutter_type = f'{stutter_info["frame_type"]}_stutter'
            stats['stutter_details'][stutter_type].append(simplified_detail)

    def _finalize_last_fps_window(
        self, current_window: dict, fps_windows: list, first_frame_time: Optional[int], stats: dict
    ) -> None:
        """处理最后一个FPS窗口"""
        if current_window['frame_count'] > 0:
            fps_windows.append(self._create_fps_window(current_window, first_frame_time, stats))

    def _finalize_fps_stats(self, stats: dict, fps_windows: list) -> None:
        """完成FPS统计信息"""
        if not fps_windows:
            return

        fps_values = [w['fps'] for w in fps_windows]
        stats['fps_stats']['fps_windows'] = fps_windows
        stats['fps_stats']['average_fps'] = sum(fps_values) / len(fps_values)
        stats['fps_stats']['min_fps'] = min(fps_values)
        stats['fps_stats']['max_fps'] = max(fps_values)

    def _calculate_stutter_rates(self, stats: dict) -> None:
        """计算卡顿率"""
        for process_type in stats['frame_stats']:
            total = stats['frame_stats'][process_type]['total']
            stutter = stats['frame_stats'][process_type]['stutter']
            stats['frame_stats'][process_type]['stutter_rate'] = round(stutter / total, 4) if total > 0 else 0

        total_stutter = int(sum(stats['frame_stats'][p]['stutter'] for p in stats['frame_stats']))
        stats['total_stutter_frames'] = total_stutter
        stats['stutter_rate'] = round(total_stutter / stats['total_frames'], 4) if stats['total_frames'] > 0 else 0.0

    def _log_analysis_complete(self, analysis_total_time: float, stats: dict) -> None:
        """记录分析完成日志"""
        if analysis_total_time > ANALYSIS_TIME_WARNING_SECONDS:
            logging.warning('卡顿帧分析耗时较长: %.2f秒', analysis_total_time)

    def _build_result(self, stats: dict) -> dict:
        """构建分析结果"""
        return {
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
