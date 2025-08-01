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
from typing import Dict, Any, Optional
# import pandas as pd  # 未使用

from hapray.analyze.base_analyzer import BaseAnalyzer
from hapray.core.common.frame.frame_core_analyzer import FrameAnalyzerCore
from hapray.core.common.frame.frame_core_cache_manager import FrameCacheManager
from hapray.core.common.frame.frame_time_utils import FrameTimeUtils


class FrameLoadAnalyzer(BaseAnalyzer):
    """Analyzer for frame load analysis

    帧负载分析器 - 遵循正确的架构设计：
    1. 继承BaseAnalyzer，负责业务逻辑协调
    2. 使用FrameAnalyzerCore进行核心分析
    3. 不直接连接数据库，通过core层访问数据
    4. 专注于帧负载分析的业务逻辑
    """

    def __init__(self, scene_dir: str, top_frames_count: int = 10):
        """
        初始化帧负载分析器

        Args:
            scene_dir: 场景目录路径
            top_frames_count: Top帧数量，默认10
        """
        super().__init__(scene_dir, 'trace/frameLoads')
        self.top_frames_count = top_frames_count
        # 初始化核心分析器
        self.core_analyzer = FrameAnalyzerCore()

    def _analyze_impl(self,
                      step_dir: str,
                      trace_db_path: str,
                      perf_db_path: str,
                      app_pids: list) -> Optional[Dict[str, Any]]:
        """实现帧负载分析逻辑"""

        if not os.path.exists(trace_db_path) or not os.path.exists(perf_db_path):
            logging.warning("数据库文件不存在，跳过帧负载分析")
            return None

        try:
            # 使用核心分析器进行帧负载分析
            # 核心分析器负责所有数据库连接和数据处理
            frame_loads_data = self.core_analyzer.analyze_comprehensive_frames(
                trace_db_path=trace_db_path,
                perf_db_path=perf_db_path,
                app_pids=app_pids,
                scene_dir=self.scene_dir,
                step_id=step_dir
            )

            if not frame_loads_data:
                logging.info("No frame load data found for step %s", step_dir)
                return None

            # 生成帧负载分析结果
            logging.debug("Generating frame load analysis result...")

            # 获取帧负载统计信息
            statistics = FrameCacheManager.get_frame_load_statistics(step_dir)

            # 获取Top帧数据
            top_frames = FrameCacheManager.get_top_frame_loads(step_dir, self.top_frames_count)

            # 获取第一帧时间戳用于相对时间计算
            first_frame_time = FrameCacheManager.get_first_frame_timestamp(None, step_dir)

            # 将top_frames中的ts转换为相对时间戳，与卡顿帧、空刷帧保持一致
            processed_top_frames = []
            for frame in top_frames:
                processed_frame = frame.copy()
                # 将ts转换为相对时间戳
                processed_frame['ts'] = FrameTimeUtils.convert_to_relative_nanoseconds(
                    frame.get('ts', 0), first_frame_time
                )
                processed_top_frames.append(processed_frame)

            # 构建最终结果 - 移除load_timeline字段，简化JSON结构
            result = {
                'statistics': statistics,
                'top_frames': processed_top_frames,
                'total_frames': len(FrameCacheManager.get_frame_loads(step_dir))
            }

            return result

        except Exception as e:
            logging.error("Frame load analysis failed for step %s: %s", step_dir, str(e))
            return None

    def _clean_data_for_json(self, data):
        """清理数据，确保JSON序列化安全"""
        if isinstance(data, dict):
            return {key: self._clean_data_for_json(value) for key, value in data.items()}
        elif isinstance(data, list):
            return [self._clean_data_for_json(item) for item in data]
        elif hasattr(data, 'dtype') and hasattr(data, 'item'):
            # numpy类型
            if hasattr(data, 'isna') and data.isna():
                return 0
            elif 'int' in str(data.dtype):
                return int(data)
            elif 'float' in str(data.dtype):
                return float(data)
            else:
                return data.item()
        else:
            return data
