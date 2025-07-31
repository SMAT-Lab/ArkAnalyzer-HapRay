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

from hapray.analyze.base_analyzer import BaseAnalyzer
from hapray.core.common.frame import FrameAnalyzerCore


class FrameDropAnalyzer(BaseAnalyzer):
    """Analyzer for frame drops analysis
    
    卡顿帧分析器 - 遵循正确的架构设计：
    1. 继承BaseAnalyzer，负责业务逻辑协调
    2. 使用FrameAnalyzerCore进行核心分析
    3. 不直接连接数据库，通过core层访问数据
    4. 专注于卡顿帧分析的业务逻辑
    """

    def __init__(self, scene_dir: str):
        super().__init__(scene_dir, 'trace/frames')
        # 初始化核心分析器
        self.core_analyzer = FrameAnalyzerCore()

    def _analyze_impl(self,
                      step_dir: str,
                      trace_db_path: str,
                      perf_db_path: str,
                      app_pids: list) -> Optional[Dict[str, Any]]:
        """分析卡顿帧数据

        Args:
            step_dir: 步骤标识符
            trace_db_path: trace数据库路径
            perf_db_path: perf数据库路径
            app_pids: 应用进程ID列表

        Returns:
            Dictionary containing frame drop analysis result for this step, or None if no data
        """
        if not os.path.exists(trace_db_path):
            logging.warning("Trace database not found: %s", trace_db_path)
            return None

        try:
            # 使用核心分析器进行卡顿帧分析
            # 核心分析器负责所有数据库连接和数据处理
            result = self.core_analyzer.analyze_stuttered_frames(
                db_path=trace_db_path,
                perf_db_path=perf_db_path,
                step_id=step_dir
            )

            if result is None:
                logging.info("No frame drop data found for step %s", step_dir)
                return None

            return result

        except Exception as e:
            logging.error("Frame drop analysis failed for step %s: %s", step_dir, str(e))
            return None


