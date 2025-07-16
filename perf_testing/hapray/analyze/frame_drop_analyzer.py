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
from hapray.core.common.frame_analyzer import FrameAnalyzer


class FrameDropAnalyzer(BaseAnalyzer):
    """Analyzer for frame drops analysis"""

    def __init__(self, scene_dir: str):
        super().__init__(scene_dir, 'trace/frames')

    def _analyze_impl(self,
                      step_dir: str,
                      trace_db_path: str,
                      perf_db_path: str,
                      app_pids: list) -> Optional[Dict[str, Any]]:
        """Analyze frame drops for a single step.

        Args:
            step_dir: Identifier for the current step
            trace_db_path: Path to trace database
            perf_db_path: Path to performance database

        Returns:
            Dictionary containing frame drop analysis result for this step, or None if no data
        """
        if not os.path.exists(trace_db_path):
            logging.warning("Trace database not found: %s", trace_db_path)
            return None

        try:
            # 分析卡顿帧数据
            logging.info("Analyzing frame drops for %s...", step_dir)
            result = FrameAnalyzer.analyze_stuttered_frames(trace_db_path, perf_db_path, step_dir)

            # 如果没有数据，返回None
            if result is None:
                logging.info("No frame drop data found for step %s", step_dir)
                return None

            return result

        except Exception as e:
            logging.error("Frame drop analysis failed: %s", str(e))
            return None
