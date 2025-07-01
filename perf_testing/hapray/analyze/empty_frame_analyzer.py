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
import traceback
from typing import Dict, Any, Optional

from hapray.analyze.base_analyzer import AnalyzerHelper, BaseAnalyzer
from hapray.core.common.frame_analyzer import FrameAnalyzer


class EmptyFrameAnalyzer(BaseAnalyzer):
    """Analyzer for empty frames analysis"""

    def __init__(self, scene_dir: str):
        super().__init__(scene_dir, 'empty_frames_analysis.json')

    def _analyze_impl(self, step_dir: str, trace_db_path: str, perf_db_path: str) -> Optional[Dict[str, Any]]:
        """Analyze empty frames for a single step.

        Args:
            step_dir: Identifier for the current step
            trace_db_path: Path to trace database
            perf_db_path: Path to performance database

        Returns:
            Dictionary containing empty frame analysis result for this step, or None if no data
        """
        if not os.path.exists(trace_db_path):
            logging.warning("Trace database not found: %s", trace_db_path)
            return None

        try:
            # 获取该步骤的进程信息
            pids = AnalyzerHelper.get_app_pids(self.scene_dir, step_dir)
            if not pids:
                logging.warning("No process info found for step %s", step_dir)
                return None

            # 执行空帧分析
            result = FrameAnalyzer.analyze_empty_frames(trace_db_path, perf_db_path, pids, self.scene_dir, step_dir)

            # 如果没有数据，返回None
            if result is None:
                logging.info("No empty frame data found for step %s", step_dir)
                return None

            return result

        except Exception as e:
            logging.error("Empty frame analysis failed: %s %s", str(e), traceback.format_exc())
            return None
