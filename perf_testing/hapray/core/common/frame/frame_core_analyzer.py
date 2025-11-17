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
from typing import Any, Optional

from .frame_analyzer_empty import EmptyFrameAnalyzer
from .frame_analyzer_stuttered import StutteredFrameAnalyzer
from .frame_analyzer_vsync import VSyncAnomalyAnalyzer

# 导入新的模块化组件
from .frame_constants import TOP_FRAMES_FOR_CALLCHAIN
from .frame_core_cache_manager import FrameCacheManager
from .frame_core_load_calculator import FrameLoadCalculator
from .frame_time_utils import FrameTimeUtils


class FrameAnalyzerCore:
    """

    使用模块化组件，职责分离清晰：
    1. 数据访问 - FrameCacheManager
    2. 负载计算 - FrameLoadCalculator
    3. 空帧分析 - EmptyFrameAnalyzer
    4. 卡顿帧分析 - StutteredFrameAnalyzer
    5. 核心协调 - 本类

    帧标志 (flag) 定义：
    - flag = 0: 实际渲染帧不卡帧（正常帧）
    - flag = 1: 实际渲染帧卡帧（expectEndTime < actualEndTime为异常）
    - flag = 2: 数据不需要绘制（空帧，不参与卡顿分析）
    - flag = 3: rs进程与app进程起止异常（|expRsStartTime - expUiEndTime| < 1ms 正常，否则异常）
    """

    def __init__(
        self,
        debug_vsync_enabled: bool = False,
        trace_db_path: Optional[str] = None,
        perf_db_path: Optional[str] = None,
        app_pids: Optional[list] = None,
        step_dir: Optional[str] = None,
    ):
        """
        初始化FrameAnalyzerCore

        Args:
            debug_vsync_enabled: VSync调试开关
            trace_db_path: trace数据库文件路径
            perf_db_path: perf数据库文件路径
            app_pids: 应用进程ID列表
            step_dir: 步骤标识符
        """
        # 保存数据库路径和参数
        self.trace_db_path = trace_db_path
        self.perf_db_path = perf_db_path
        self.app_pids = app_pids
        self.step_dir = step_dir

        # 初始化缓存管理器（包含数据库连接初始化）
        self.cache_manager = FrameCacheManager(trace_db_path, perf_db_path, app_pids)

        # 初始化各个专门的分析器
        self.load_calculator = FrameLoadCalculator(debug_vsync_enabled, self.cache_manager)
        self.empty_frame_analyzer = EmptyFrameAnalyzer(debug_vsync_enabled, self.cache_manager)
        self.stuttered_frame_analyzer = StutteredFrameAnalyzer(debug_vsync_enabled, self.cache_manager)
        self.vsync_anomaly_analyzer = VSyncAnomalyAnalyzer(self.cache_manager)

    def analyze_empty_frames(self) -> Optional[dict]:
        """分析空帧（flag=2, type=0）的负载情况

        Returns:
            dict: 包含分析结果
        """
        return self.empty_frame_analyzer.analyze_empty_frames()

    def analyze_stuttered_frames(self) -> Optional[dict]:
        """分析卡顿帧数据并计算FPS

        Returns:
            Optional[dict]: 分析结果数据，如果没有数据或分析失败则返回None
        """
        return self.stuttered_frame_analyzer.analyze_stuttered_frames()

    def analyze_vsync_anomalies(self) -> Optional[dict[str, Any]]:
        """分析VSync异常

        Returns:
            Optional[dict[str, Any]]: VSync异常分析结果，如果没有数据或分析失败则返回None
        """
        return self.vsync_anomaly_analyzer.analyze_vsync_anomalies(self.app_pids)

    def analyze_frame_loads_fast(self, step_id: str = None) -> dict[str, Any]:
        """快速分析所有帧的负载值（不分析调用链）

        这是FrameLoad阶段的优化版本，只计算负载值，不进行调用链分析

        Args:
            step_id: 步骤ID

        Returns:
            Dict: 帧负载分析结果
        """
        # 从cache_manager获取参数
        trace_conn = self.cache_manager.trace_conn
        perf_conn = self.cache_manager.perf_conn
        app_pids = self.cache_manager.app_pids

        if not trace_conn or not perf_conn:
            logging.error('[%s] 缺少必要的数据库连接', step_id)
            return None

        try:
            # 阶段1：获取数据
            trace_df = self.cache_manager.get_frames_data(app_pids)
            perf_df = self.cache_manager.get_perf_samples()

            if trace_df.empty:
                return None

            # 阶段2：快速计算帧负载
            frame_loads = self.load_calculator.calculate_all_frame_loads_fast(trace_df, perf_df)

            # 阶段3：保存到缓存
            for frame_load in frame_loads:
                self.cache_manager.add_frame_load(frame_load)

            # 阶段4：获取统计信息
            statistics = self.cache_manager.get_frame_load_statistics()
            top_frames = self.cache_manager.get_top_frame_loads(TOP_FRAMES_FOR_CALLCHAIN)
            first_frame_time = self.cache_manager.get_first_frame_timestamp()

            # 阶段5：处理Top帧时间戳
            processed_top_frames = []
            for frame in top_frames:
                processed_frame = frame.copy()
                processed_frame['ts'] = FrameTimeUtils.convert_to_relative_nanoseconds(
                    frame.get('ts', 0), first_frame_time
                )
                processed_top_frames.append(processed_frame)

            return {'statistics': statistics, 'top_frames': processed_top_frames, 'total_frames': len(frame_loads)}

        except Exception as e:
            logging.error('快速帧负载分析失败: %s', str(e))
            return None

    def close_connections(self) -> None:
        """关闭数据库连接"""
        if self.cache_manager:
            self.cache_manager.close_connections()
