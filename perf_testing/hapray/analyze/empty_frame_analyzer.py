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
from typing import Dict, Any, Optional

from hapray.analyze.base_analyzer import BaseAnalyzer
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
            pids = self._get_step_pids(step_dir)

            if not pids:
                logging.warning("No process info found for step %s", step_dir)
                return None

            # 记录当前步骤的进程信息
            for name, pid in pids:
                logging.info(f"Step {step_dir} - Process: {name} (PID: {pid})")

            # 提取PID列表
            pid_list = [pid for _, pid in pids]

            # 执行空帧分析
            result = FrameAnalyzer.analyze_empty_frames(trace_db_path, perf_db_path, pid_list, self.scene_dir, step_dir)

            # 如果没有数据，返回None
            if result is None:
                logging.info("No empty frame data found for step %s", step_dir)
                return None

            return result

        except Exception as e:
            logging.error("Empty frame analysis failed: %s", str(e))
            return None

    def _get_step_pids(self, step_dir: str) -> list:
        """获取指定步骤的进程信息"""
        try:
            # 构建pids.json文件路径
            pids_json_path = os.path.join(self.scene_dir, 'hiperf', step_dir, 'pids.json')

            if not os.path.exists(pids_json_path):
                logging.warning("No pids.json found at %s", pids_json_path)
                return []

            # 读取JSON文件
            with open(pids_json_path, 'r', encoding='utf-8') as f:
                pids_data = json.load(f)

            # 提取pids和process_names
            pids = pids_data.get('pids', [])
            process_names = pids_data.get('process_names', [])

            if not pids or not process_names:
                logging.warning("No valid pids or process_names found in %s", pids_json_path)
                return []

            # 确保pids和process_names长度一致
            if len(pids) != len(process_names):
                logging.warning(
                    f"Mismatch between pids ({len(pids)}) and process_names ({len(process_names)}) in {pids_json_path}")
                # 取较短的长度
                min_length = min(len(pids), len(process_names))
                pids = pids[:min_length]
                process_names = process_names[:min_length]

            # 组合成(process_name, pid)的列表
            step_pids = list(zip(process_names, pids))

            logging.debug(f"Found {len(step_pids)} processes for step {step_dir}: {step_pids}")
            return step_pids

        except Exception as e:
            logging.error(f"Failed to get step PIDs from {step_dir}: {str(e)}")
            return []
