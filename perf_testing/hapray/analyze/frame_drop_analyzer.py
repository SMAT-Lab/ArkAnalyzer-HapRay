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

import json
import logging
import os
from typing import Dict, Any

from hapray.analyze.base_analyzer import BaseAnalyzer
from hapray.core.common.frame_analyzer import FrameAnalyzer


class FrameDropAnalyzer(BaseAnalyzer):
    """Analyzer for frame drops analysis"""
    
    def __init__(self, scene_dir: str):
        super().__init__(scene_dir, 'frame_analysis_summary.json')

    def _analyze_impl(self, trace_db_path: str, perf_db_path: str) -> Dict[str, Any]:
        """Analyze frame drops for a single step.
        
        Args:
            trace_db_path: Path to trace database
            perf_db_path: Path to performance database
            
        Returns:
            Dictionary containing frame drop analysis result for this step
        """
        try:
            # 从路径中提取step_dir
            step_dir = self._extract_step_dir(trace_db_path)
            
            # 分析卡顿帧数据
            logging.info(f"Analyzing frame drops for {step_dir}...")
            result = FrameAnalyzer.analyze_stuttered_frames(trace_db_path, perf_db_path, step_dir)
            
            return result
            
        except Exception as e:
            logging.error(f"Frame drop analysis failed: {str(e)}")
            return {"error": f"Frame drop analysis failed: {str(e)}"}

    def _extract_step_dir(self, trace_db_path: str) -> str:
        """从trace数据库路径中提取步骤目录名"""
        # 路径格式：.../htrace/step1/trace.db
        # 提取step1部分
        path_parts = trace_db_path.split(os.sep)
        for i, part in enumerate(path_parts):
            if part == 'htrace' and i + 1 < len(path_parts):
                return path_parts[i + 1]
        return "unknown" 