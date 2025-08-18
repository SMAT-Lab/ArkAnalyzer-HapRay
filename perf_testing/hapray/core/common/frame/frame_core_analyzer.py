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
from typing import Dict, Any, List, Optional

from .frame_analyzer_empty import EmptyFrameAnalyzer
from .frame_analyzer_stuttered import StutteredFrameAnalyzer
from .frame_core_cache_manager import FrameCacheManager
# 导入新的模块化组件
from .frame_core_load_calculator import FrameLoadCalculator
from .frame_data_parser import parse_frame_slice_db, get_frame_type, validate_database_compatibility
from .frame_time_utils import FrameTimeUtils

# 设置环境变量
os.environ["PYTHONIOENCODING"] = "utf-8"


class FrameAnalyzerCore:  # pylint: disable=duplicate-code
    """重构后的卡顿帧分析器核心

    使用模块化组件，职责分离清晰：
    1. 缓存管理 - FrameCacheManager
    2. 负载计算 - FrameLoadCalculator
    3. 数据解析 - frame_data_parser
    4. 空帧分析 - EmptyFrameAnalyzer
    5. 卡顿帧分析 - StutteredFrameAnalyzer
    6. 核心协调 - 本类

    帧标志 (flag) 定义：
    - flag = 0: 实际渲染帧不卡帧（正常帧）
    - flag = 1: 实际渲染帧卡帧（expectEndTime < actualEndTime为异常）
    - flag = 2: 数据不需要绘制（空帧，不参与卡顿分析）
    - flag = 3: rs进程与app进程起止异常（|expRsStartTime - expUiEndTime| < 1ms 正常，否则异常）
    """

    # 调试开关配置
    _debug_vsync_enabled = False  # VSync调试开关

    # 卡顿分级阈值常量
    FRAME_DURATION = 16.67  # 毫秒，60fps基准帧时长
    STUTTER_LEVEL_1_FRAMES = 2  # 1级卡顿阈值：0-2帧（33.34ms）
    STUTTER_LEVEL_2_FRAMES = 6  # 2级卡顿阈值：2-6帧（100ms）
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
            step_id: str = None,
            app_pids: list = None
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
            trace_db_path, perf_db_path, app_pids, step_id
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
            step_id: str = None
    ) -> Dict[str, Any]:
        """综合分析空帧和卡顿帧

        Args:
            trace_db_path: trace数据库文件路径
            perf_db_path: perf数据库文件路径
            app_pids: 应用进程ID列表
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
                trace_db_path, perf_db_path, step_id, app_pids
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

            # logging.info("综合分析完成")
            return result

        except Exception as e:
            logging.error("综合分析失败: %s", str(e))
            result["error"] = str(e)
            return result

    def analyze_frame_loads_fast(
            self,
            trace_db_path: str,
            perf_db_path: str,
            app_pids: list,
            step_id: str = None
    ) -> Dict[str, Any]:
        """快速分析所有帧的负载值（不分析调用链）

        这是FrameLoad阶段的优化版本，只计算负载值，不进行调用链分析

        Args:
            trace_db_path: trace数据库文件路径
            perf_db_path: perf数据库文件路径
            app_pids: 应用进程ID列表
            step_id: 步骤ID

        Returns:
            Dict: 帧负载分析结果
        """
        start_time = time.time()
        trace_conn = None
        perf_conn = None

        try:
            # 阶段1：数据库连接
            db_connect_start = time.time()
            trace_conn = sqlite3.connect(trace_db_path)
            perf_conn = sqlite3.connect(perf_db_path)
            db_connect_time = time.time() - db_connect_start
            logging.info("[%s] 数据库连接耗时: %.3f秒", step_id, db_connect_time)

            # 阶段2：数据预加载
            preload_start = time.time()
            if step_id:
                # FrameCacheManager.preload_analyzer_data(
                #     trace_conn, perf_conn, step_id, app_pids
                # )  # 删除预加载以提升性能
                FrameCacheManager.ensure_data_cached('frame_loads', trace_conn, perf_conn, step_id, app_pids)
            preload_time = time.time() - preload_start
            logging.info("[%s] 数据预加载耗时: %.3f秒", step_id, preload_time)

            # 阶段3：获取数据
            data_fetch_start = time.time()
            trace_df = FrameCacheManager.get_frames_data(trace_conn, step_id, app_pids)
            perf_df = FrameCacheManager.get_perf_samples(perf_conn, step_id)
            data_fetch_time = time.time() - data_fetch_start
            logging.info("[%s] 数据获取耗时: %.3f秒", step_id, data_fetch_time)
            logging.info("[%s] 帧数据量: %d行, 性能数据量: %d行", step_id, len(trace_df), len(perf_df))

            if trace_df.empty:
                logging.info("未找到帧数据")
                return None

            # 阶段4：快速计算帧负载
            calc_start = time.time()
            frame_loads = self.load_calculator.calculate_all_frame_loads_fast(trace_df, perf_df)
            calc_time = time.time() - calc_start
            logging.info("[%s] 帧负载计算耗时: %.3f秒, 计算了%d个帧", step_id, calc_time, len(frame_loads))

            # 阶段5：保存到缓存
            cache_save_start = time.time()
            for frame_load in frame_loads:
                if step_id:
                    FrameCacheManager.add_frame_load(step_id, frame_load)
            cache_save_time = time.time() - cache_save_start
            logging.info("[%s] 缓存保存耗时: %.3f秒", step_id, cache_save_time)

            # 阶段6：获取统计信息
            stats_start = time.time()
            statistics = FrameCacheManager.get_frame_load_statistics(step_id)
            top_frames = FrameCacheManager.get_top_frame_loads(step_id, 10)
            first_frame_time = FrameCacheManager.get_first_frame_timestamp(None, step_id)
            stats_time = time.time() - stats_start
            logging.info("[%s] 统计信息获取耗时: %.3f秒", step_id, stats_time)

            # 阶段7：处理Top帧时间戳
            process_start = time.time()
            processed_top_frames = []
            for frame in top_frames:
                processed_frame = frame.copy()
                processed_frame['ts'] = FrameTimeUtils.convert_to_relative_nanoseconds(
                    frame.get('ts', 0), first_frame_time
                )
                processed_top_frames.append(processed_frame)
            process_time = time.time() - process_start
            logging.info("[%s] Top帧处理耗时: %.3f秒", step_id, process_time)

            result = {
                'statistics': statistics,
                'top_frames': processed_top_frames,
                'total_frames': len(frame_loads)
            }

            total_time = time.time() - start_time
            logging.info("[%s] 快速帧负载分析总耗时: %.3f秒", step_id, total_time)
            logging.info(
                "[%s] 各阶段耗时占比: "
                "连接%.1f%%, "
                "预加载%.1f%%, "
                "获取%.1f%%, "
                "计算%.1f%%, "
                "缓存%.1f%%, "
                "统计%.1f%%, "
                "处理%.1f%%",
                step_id,
                db_connect_time / total_time * 100,
                preload_time / total_time * 100,
                data_fetch_time / total_time * 100,
                calc_time / total_time * 100,
                cache_save_time / total_time * 100,
                stats_time / total_time * 100,
                process_time / total_time * 100)

            return result

        except Exception as e:
            logging.error("快速帧负载分析失败: %s", str(e))
            return None
        finally:
            if trace_conn:
                trace_conn.close()
            if perf_conn:
                perf_conn.close()

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
        # 注意：这个方法实际上调用的是完整的分析，不是简单计算
        # 为了保持向后兼容，保留此方法
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
