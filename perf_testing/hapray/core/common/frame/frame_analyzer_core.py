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
import sys
from typing import Dict, Any, List, Optional

# 设置环境变量
os.environ["PYTHONIOENCODING"] = "utf-8"

from .frame_cache_manager import FrameCacheManager
from .frame_load_calculator import FrameLoadCalculator
from .frame_data_parser import parse_frame_slice_db, get_frame_type, validate_database_compatibility
from .empty_frame_analyzer import EmptyFrameAnalyzer
from .stuttered_frame_analyzer import StutteredFrameAnalyzer


class FrameAnalyzerCore:
    """重构后的卡顿帧分析器核心

    使用模块化组件，职责分离清晰：
    1. 缓存管理 - FrameCacheManager
    2. 负载计算 - FrameLoadCalculator  
    3. 数据解析 - frame_data_parser
    4. 空帧分析 - EmptyFrameAnalyzer
    5. 卡顿帧分析 - StutteredFrameAnalyzer
    6. 核心协调 - 本类
    """

    # 调试开关配置
    _debug_vsync_enabled = False  # VSync调试开关

    # 常量定义
    FRAME_DURATION = 16.67  # 毫秒，60fps基准帧时长
    STUTTER_LEVEL_1_FRAMES = 2  # 1级卡顿阈值：0-2帧
    STUTTER_LEVEL_2_FRAMES = 6  # 2级卡顿阈值：2-6帧
    NS_TO_MS = 1_000_000
    WINDOW_SIZE_MS = 1000  # fps窗口大小：1s

    def __init__(self, debug_vsync_enabled: bool = False):
        """
        初始化FrameAnalyzerCore
        
        Args:
            debug_vsync_enabled: VSync调试开关
        """
        self._debug_vsync_enabled = debug_vsync_enabled
        
        # 初始化各个专门的分析器
        self.load_calculator = FrameLoadCalculator(debug_vsync_enabled)
        self.empty_frame_analyzer = EmptyFrameAnalyzer(debug_vsync_enabled)
        self.stuttered_frame_analyzer = StutteredFrameAnalyzer(debug_vsync_enabled)

    def analyze_empty_frames(
        self,
        trace_db_path: str,
        perf_db_path: str,
        app_pids: list,
        scene_dir: str = None,
        step_id: str = None
    ) -> Optional[dict]:
        """分析空帧（flag=2, type=0）的负载情况

        Args:
            trace_db_path: trace数据库文件路径
            perf_db_path: perf数据库文件路径
            app_pids: 应用进程ID列表
            scene_dir: 场景目录路径，用于更新缓存
            step_id: 步骤ID，用于更新缓存

        Returns:
            dict: 包含分析结果
        """
        return self.empty_frame_analyzer.analyze_empty_frames(
            trace_db_path, perf_db_path, app_pids, scene_dir, step_id
        )

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
        return self.stuttered_frame_analyzer.analyze_stuttered_frames(
            db_path, perf_db_path, step_id
        )

    def analyze_comprehensive_frames(
        self,
        trace_db_path: str,
        perf_db_path: str,
        app_pids: list,
        scene_dir: str = None,
        step_id: str = None
    ) -> Dict[str, Any]:
        """综合分析空帧和卡顿帧

        Args:
            trace_db_path: trace数据库文件路径
            perf_db_path: perf数据库文件路径
            app_pids: 应用进程ID列表
            scene_dir: 场景目录路径
            step_id: 步骤ID

        Returns:
            Dict: 综合分析结果
        """
        result = {
            "empty_frames": None,
            "stuttered_frames": None,
            "cache_stats": None
        }

        try:
            # 分析空帧
            logging.info("开始分析空帧...")
            empty_result = self.analyze_empty_frames(
                trace_db_path, perf_db_path, app_pids, scene_dir, step_id
            )
            result["empty_frames"] = empty_result

            # 分析卡顿帧
            logging.info("开始分析卡顿帧...")
            stuttered_result = self.analyze_stuttered_frames(
                trace_db_path, perf_db_path, step_id
            )
            result["stuttered_frames"] = stuttered_result

            # 获取缓存统计
            result["cache_stats"] = FrameCacheManager.get_cache_stats()

            logging.info("综合分析完成")
            return result

        except Exception as e:
            logging.error("综合分析失败: %s", str(e))
            result["error"] = str(e)
            return result

    def clear_cache(self, step_id: str = None) -> None:
        """清除缓存数据

        Args:
            step_id: 步骤ID，如果为None则清除所有缓存
        """
        FrameCacheManager.clear_cache(step_id)

    def get_cache_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息

        Returns:
            Dict: 缓存统计信息
        """
        return FrameCacheManager.get_cache_stats()

    def validate_database(self, db_path: str) -> bool:
        """验证数据库兼容性

        Args:
            db_path: 数据库文件路径

        Returns:
            bool: 是否兼容
        """
        return validate_database_compatibility(db_path)

    def parse_frame_data(self, db_path: str) -> Dict[int, List[Dict[str, Any]]]:
        """解析帧数据

        Args:
            db_path: 数据库文件路径

        Returns:
            Dict: 按vsync值分组的帧数据
        """
        return parse_frame_slice_db(db_path)

    def calculate_frame_load_simple(
        self,
        frame: Dict[str, Any],
        perf_df,
        perf_conn,
        step_id: str = None
    ) -> tuple:
        """简单计算帧负载（保持向后兼容）

        Args:
            frame: 帧数据
            perf_df: perf样本DataFrame
            perf_conn: perf数据库连接
            step_id: 步骤ID

        Returns:
            tuple: (frame_load, sample_callchains)
        """
        return self.load_calculator.analyze_single_frame(
            frame, perf_df, perf_conn, step_id
        )

    def get_frame_type(self, frame: dict, cursor, step_id: str = None) -> str:
        """获取帧类型（保持向后兼容）

        Args:
            frame: 帧数据字典
            cursor: 数据库游标
            step_id: 步骤ID

        Returns:
            str: 帧类型
        """
        return get_frame_type(frame, cursor, step_id)

    def set_debug_vsync_enabled(self, enabled: bool) -> None:
        """设置VSync调试开关

        Args:
            enabled: 是否启用VSync调试
        """
        self._debug_vsync_enabled = enabled
        self.load_calculator.debug_vsync_enabled = enabled
        self.empty_frame_analyzer.load_calculator.debug_vsync_enabled = enabled
        self.stuttered_frame_analyzer.load_calculator.debug_vsync_enabled = enabled

    def get_analyzer_info(self) -> Dict[str, Any]:
        """获取分析器信息

        Returns:
            Dict: 分析器信息
        """
        return {
            "core_version": "2.0.0",
            "debug_vsync_enabled": self._debug_vsync_enabled,
            "modules": {
                "cache_manager": "FrameCacheManager",
                "load_calculator": "FrameLoadCalculator",
                "empty_frame_analyzer": "EmptyFrameAnalyzer",
                "stuttered_frame_analyzer": "StutteredFrameAnalyzer"
            },
            "constants": {
                "FRAME_DURATION": self.FRAME_DURATION,
                "STUTTER_LEVEL_1_FRAMES": self.STUTTER_LEVEL_1_FRAMES,
                "STUTTER_LEVEL_2_FRAMES": self.STUTTER_LEVEL_2_FRAMES,
                "NS_TO_MS": self.NS_TO_MS,
                "WINDOW_SIZE_MS": self.WINDOW_SIZE_MS
            }
        } 