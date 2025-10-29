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
from typing import Any, Optional

from hapray.analyze import BaseAnalyzer
from hapray.core.common.exe_utils import ExeUtils


class MemoryAnalyzer(BaseAnalyzer):
    """独立的内存分析器，参考 PerfAnalyzer 的结构"""

    def __init__(self, scene_dir: str, time_ranges: list[dict] = None):
        super().__init__(scene_dir, 'more/memory_analysis')
        self.time_ranges = time_ranges

    def _analyze_impl(
        self, step_dir: str, trace_db_path: str, perf_db_path: str, app_pids: list
    ) -> Optional[dict[str, Any]]:
        """Run memory analysis

        Note: Memory analysis is typically executed only once (in step1)
        to analyze the entire memory trace data.
        """
        # Execute only in step1
        if step_dir == 'step1':
            args = ['memory', '-i', self.scene_dir]

            # Add time ranges if provided
            if self.time_ranges:
                time_range_strings = []
                for tr in self.time_ranges:
                    time_range_str = f'{tr["startTime"]}-{tr["endTime"]}'
                    time_range_strings.append(time_range_str)
                args.extend(['--time-ranges'] + time_range_strings)
                logging.info('Adding time ranges to memory command: %s', time_range_strings)

            logging.debug('Running memory analysis with command: %s', ' '.join(args))
            ExeUtils.execute_hapray_cmd(args)

            # Return memory analysis result (if any)
            return self._load_memory_analysis_result()

        return None

    def _load_memory_analysis_result(self) -> Optional[dict[str, Any]]:
        """Load memory analysis result from generated files

        Returns:
            Dictionary containing memory analysis results or None if not found
        """
        try:
            memory_json_path = os.path.join(self.scene_dir, 'report', 'native_memory.json')
            if os.path.exists(memory_json_path):
                logging.info('Memory analysis result found at %s', memory_json_path)
                return {'memory_data_path': memory_json_path}
            logging.warning('Memory analysis result not found at %s', memory_json_path)
            return None
        except Exception as e:
            logging.error('Failed to load memory analysis result: %s', str(e))
            return None
