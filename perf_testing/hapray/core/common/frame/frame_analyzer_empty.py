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

import pandas as pd

from .frame_constants import TOP_FRAMES_FOR_CALLCHAIN
from .frame_core_cache_manager import FrameCacheManager
from .frame_core_load_calculator import FrameLoadCalculator
from .frame_time_utils import FrameTimeUtils


class EmptyFrameAnalyzer:
    """空帧分析器

    专门用于分析空帧（flag=2, type=0）的负载情况，包括：
    1. 空帧负载计算
    2. 主线程vs后台线程分析
    3. 空帧调用链分析

    帧标志 (flag) 定义：
    - flag = 0: 实际渲染帧不卡帧（正常帧）
    - flag = 1: 实际渲染帧卡帧（expectEndTime < actualEndTime为异常）
    - flag = 2: 数据不需要绘制（空帧，本分析器专门分析此类帧）
    - flag = 3: rs进程与app进程起止异常（|expRsStartTime - expUiEndTime| < 1ms 正常，否则异常）
    """

    def __init__(self, debug_vsync_enabled: bool = False, cache_manager: FrameCacheManager = None):
        """
        初始化空帧分析器

        Args:
            debug_vsync_enabled: VSync调试开关
            cache_manager: 缓存管理器实例
        """
        self.cache_manager = cache_manager
        self.load_calculator = FrameLoadCalculator(debug_vsync_enabled, cache_manager)

    def analyze_empty_frames(self) -> Optional[dict]:
        """分析空帧（flag=2, type=0）的负载情况

        空帧定义：flag=2 表示数据不需要绘制（没有frameNum信息）

        返回:
        - dict，包含分析结果
        """
        # 从cache_manager获取数据库连接和参数
        trace_conn = self.cache_manager.trace_conn
        perf_conn = self.cache_manager.perf_conn
        app_pids = self.cache_manager.app_pids

        if not trace_conn or not perf_conn:
            logging.error('数据库连接未建立')
            return None

        total_start_time = time.time()
        timing_stats = {}

        try:
            # 阶段1：加载数据
            trace_df, total_load, perf_df = self._load_empty_frame_data(app_pids, timing_stats)
            if trace_df is None or trace_df.empty:
                return None

            # 阶段2：数据预处理
            self._prepare_frame_data(trace_df, timing_stats)

            # 阶段3：快速帧负载计算
            frame_loads = self._calculate_frame_loads(trace_df, perf_df, timing_stats)

            # 阶段4：Top帧调用链分析
            self._analyze_top_frames_callchains(frame_loads, trace_df, perf_df, perf_conn, timing_stats)

            # 阶段5：结果构建
            result = self._build_result(frame_loads, trace_df, total_load, timing_stats)

            # 总耗时统计
            total_time = time.time() - total_start_time
            self._log_analysis_complete(total_time, timing_stats)

            return result

        except Exception as e:
            logging.error('分析空帧时发生异常: %s', str(e))
            logging.error('异常堆栈跟踪:\n%s', traceback.format_exc())
            return None

    def _load_empty_frame_data(self, app_pids: list, timing_stats: dict) -> tuple:
        """加载空帧相关数据

        Args:
            trace_conn: trace数据库连接
            perf_conn: perf数据库连接
            app_pids: 应用进程ID列表
            timing_stats: 耗时统计字典，函数内部会设置相关时间值

        Returns:
            tuple: (trace_df, total_load, perf_df)
        """
        # 获取空帧数据
        query_start = time.time()
        trace_df = self.cache_manager.get_empty_frames_with_details(app_pids)
        timing_stats['query'] = time.time() - query_start

        if trace_df.empty:
            return None, None, None

        # 获取总负载数据
        total_load_start = time.time()
        total_load = self.cache_manager.get_total_load_for_pids(app_pids)
        timing_stats['total_load'] = time.time() - total_load_start

        # 获取性能样本
        perf_start = time.time()
        perf_df = self.cache_manager.get_perf_samples() if self.cache_manager else pd.DataFrame()
        timing_stats['perf'] = time.time() - perf_start

        return trace_df, total_load, perf_df

    def _prepare_frame_data(self, trace_df: pd.DataFrame, timing_stats: dict) -> None:
        """数据预处理

        Args:
            trace_df: 帧数据DataFrame
            timing_stats: 耗时统计字典，函数内部会设置相关时间值
        """
        data_prep_start = time.time()
        trace_df['start_time'] = trace_df['ts']
        trace_df['end_time'] = trace_df['ts'] + trace_df['dur']
        timing_stats['data_prep'] = time.time() - data_prep_start

    def _calculate_frame_loads(self, trace_df: pd.DataFrame, perf_df: pd.DataFrame, timing_stats: dict) -> list:
        """快速帧负载计算

        Args:
            trace_df: 帧数据DataFrame
            perf_df: 性能数据DataFrame
            timing_stats: 耗时统计字典，函数内部会设置相关时间值

        Returns:
            list: 帧负载数据列表
        """
        fast_calc_start = time.time()
        frame_loads = self.load_calculator.calculate_all_frame_loads_fast(trace_df, perf_df)
        timing_stats['fast_calc'] = time.time() - fast_calc_start
        return frame_loads

    def _analyze_top_frames_callchains(
        self, frame_loads: list, trace_df: pd.DataFrame, perf_df: pd.DataFrame, perf_conn, timing_stats: dict
    ) -> None:
        """识别Top帧并进行调用链分析

        Args:
            frame_loads: 帧负载数据列表
            trace_df: 帧数据DataFrame
            perf_df: 性能数据DataFrame
            perf_conn: perf数据库连接
            timing_stats: 耗时统计字典，函数内部会设置相关时间值
        """
        top_analysis_start = time.time()

        # 按负载排序，获取前N帧进行详细调用链分析
        sorted_frames = sorted(frame_loads, key=lambda x: x['frame_load'], reverse=True)
        top_10_frames = sorted_frames[:TOP_FRAMES_FOR_CALLCHAIN]

        # 只对Top N帧进行调用链分析
        for frame_data in top_10_frames:
            # 找到对应的原始帧数据
            frame_mask = (
                (trace_df['ts'] == frame_data['ts'])
                & (trace_df['dur'] == frame_data['dur'])
                & (trace_df['tid'] == frame_data['thread_id'])
            )
            original_frame = trace_df[frame_mask].iloc[0] if not trace_df[frame_mask].empty else None

            if original_frame is not None:
                try:
                    _, sample_callchains = self.load_calculator.analyze_single_frame(
                        original_frame, perf_df, perf_conn, None
                    )
                    frame_data['sample_callchains'] = sample_callchains
                except Exception as e:
                    logging.warning('帧调用链分析失败: ts=%s, error=%s', frame_data['ts'], str(e))
                    frame_data['sample_callchains'] = []
            else:
                frame_data['sample_callchains'] = []

        # 对于非Top 10帧，设置空的调用链信息
        for frame_data in frame_loads:
            if frame_data not in top_10_frames:
                frame_data['sample_callchains'] = []

        timing_stats['top_analysis'] = time.time() - top_analysis_start

    def _build_result(self, frame_loads: list, trace_df: pd.DataFrame, total_load: int, timing_stats: dict) -> dict:
        """构建分析结果

        Args:
            frame_loads: 帧负载数据列表
            trace_df: 帧数据DataFrame
            total_load: 总负载
            timing_stats: 耗时统计字典，函数内部会设置相关时间值

        Returns:
            dict: 分析结果
        """
        result_build_start = time.time()
        result_df = pd.DataFrame(frame_loads)

        if result_df.empty:
            timing_stats['result_build'] = time.time() - result_build_start
            return None

        # 获取第一帧时间戳用于相对时间计算
        first_frame_time = self.cache_manager.get_first_frame_timestamp() if self.cache_manager else 0

        # 分别获取主线程和后台线程的top5帧
        main_thread_frames = (
            result_df[result_df['is_main_thread'] == 1].sort_values('frame_load', ascending=False).head(5)
        )
        background_thread_frames = (
            result_df[result_df['is_main_thread'] == 0].sort_values('frame_load', ascending=False).head(5)
        )

        # 处理主线程帧的时间戳
        processed_main_thread_frames = self._process_frame_timestamps(main_thread_frames, first_frame_time)

        # 处理后台线程帧的时间戳
        processed_bg_thread_frames = self._process_frame_timestamps(background_thread_frames, first_frame_time)

        # 计算统计信息
        empty_frame_load = int(sum(f['frame_load'] for f in frame_loads if f.get('is_main_thread') == 1))
        background_thread_load = int(sum(f['frame_load'] for f in frame_loads if f.get('is_main_thread') != 1))

        if total_load > 0:
            empty_frame_percentage = (empty_frame_load / total_load) * 100
            background_thread_percentage = (background_thread_load / total_load) * 100
        else:
            empty_frame_percentage = 0.0
            background_thread_percentage = 0.0

        # 构建结果字典
        result = {
            'status': 'success',
            'summary': {
                'total_load': int(total_load),
                'empty_frame_load': int(empty_frame_load),
                'empty_frame_percentage': float(empty_frame_percentage),
                'background_thread_load': int(background_thread_load),
                'background_thread_percentage': float(background_thread_percentage),
                'total_empty_frames': int(len(trace_df[trace_df['is_main_thread'] == 1])),
                'empty_frames_with_load': int(len([f for f in frame_loads if f.get('is_main_thread') == 1])),
            },
            'top_frames': {
                'main_thread_empty_frames': processed_main_thread_frames,
                'background_thread': processed_bg_thread_frames,
            },
        }

        timing_stats['result_build'] = time.time() - result_build_start
        return result

    def _process_frame_timestamps(self, frames_df: pd.DataFrame, first_frame_time: int) -> list:
        """处理帧时间戳，转换为相对时间

        Args:
            frames_df: 帧数据DataFrame
            first_frame_time: 第一帧时间戳

        Returns:
            list: 处理后的帧列表
        """
        processed_frames = []
        for _, frame in frames_df.iterrows():
            processed_frame = frame.to_dict()
            original_ts = frame.get('ts', 0)
            # 转换为相对时间戳（纳秒）- 与卡顿帧分析器保持一致
            processed_frame['ts'] = FrameTimeUtils.convert_to_relative_nanoseconds(original_ts, first_frame_time)
            # 保存原始时间戳用于调试
            processed_frame['original_ts'] = original_ts
            processed_frames.append(processed_frame)
        return processed_frames

    def _log_analysis_complete(self, total_time: float, timing_stats: dict) -> None:
        """记录分析完成日志

        Args:
            total_time: 总耗时
            timing_stats: 各阶段耗时统计
        """
        logging.info('空帧分析总耗时: %.3f秒', total_time)
        logging.info(
            '各阶段耗时占比: '
            '缓存检查%.1f%%, '
            '查询%.1f%%, '
            '总负载%.1f%%, '
            '性能样本%.1f%%, '
            '预处理%.1f%%, '
            '快速计算%.1f%%, '
            'Top帧分析%.1f%%, '
            '结果构建%.1f%%',
            timing_stats.get('cache_check', 0) / total_time * 100 if total_time > 0 else 0,
            timing_stats.get('query', 0) / total_time * 100 if total_time > 0 else 0,
            timing_stats.get('total_load', 0) / total_time * 100 if total_time > 0 else 0,
            timing_stats.get('perf', 0) / total_time * 100 if total_time > 0 else 0,
            timing_stats.get('data_prep', 0) / total_time * 100 if total_time > 0 else 0,
            timing_stats.get('fast_calc', 0) / total_time * 100 if total_time > 0 else 0,
            timing_stats.get('top_analysis', 0) / total_time * 100 if total_time > 0 else 0,
            timing_stats.get('result_build', 0) / total_time * 100 if total_time > 0 else 0,
        )
