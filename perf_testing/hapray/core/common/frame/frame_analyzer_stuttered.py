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

from typing import Any

from .frame_constants import (
    FLAG_PROCESS_ERROR,
    STUTTER_LEVEL_1_FRAMES,
    STUTTER_LEVEL_2_FRAMES,
)
from .frame_core_load_calculator import FrameLoadCalculator


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
