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

"""
Abstract base class for all data analyzers.
"""

import json
import logging
import os
import time
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional


class BaseAnalyzer(ABC):
    def __init__(self, scene_dir: str, report_name: str):
        """Initialize base analyzer.

        Args:
            scene_dir: Root directory of the scene
            report_name: Output report filename
        """
        self.results: Dict[str, Any] = {}
        self.scene_dir = scene_dir
        self.report_path = os.path.join(self.scene_dir, 'htrace', report_name)
        self.logger = logging.getLogger(self.__class__.__name__)
        self.report_name = report_name

    def analyze(self, step_dir: str, trace_db_path: str, perf_db_path: str):
        """Public method to execute analysis for a single step.

        Args:
            step_dir: Identifier for the current step
            trace_db_path: Path to trace database
            perf_db_path: Path to performance database
        """
        try:
            start_time = time.time()
            result = self._analyze_impl(step_dir, trace_db_path, perf_db_path)
            if result:
                self.results[step_dir] = result
            self.logger.info(
                f"Analysis completed for step {step_dir} in {time.time() - start_time:.2f} seconds [{self.report_name}]")
        except Exception as e:
            self.logger.error(f"Analysis failed for step {step_dir}: {str(e)} [{self.report_name}]")
            self.results[step_dir] = {"error": str(e)}

    @abstractmethod
    def _analyze_impl(self, step_dir: str, trace_db_path: str, perf_db_path: str) -> Optional[Dict[str, Any]]:
        """Implementation of the analysis logic.

        Args:
            step_dir: Identifier for the current step
            trace_db_path: Path to trace database
            perf_db_path: Path to performance database

        Returns:
            Analysis results as a dictionary
        """
        pass

    def write_report(self):
        """Write analysis results to JSON report."""
        if not self.results:
            self.logger.warning("No results to write. Skipping report generation.")
            return

        try:
            os.makedirs(os.path.dirname(self.report_path), exist_ok=True)
            with open(self.report_path, 'w', encoding='utf-8') as f:
                json.dump(self.results, f, ensure_ascii=False, indent=2)
            self.logger.info(f"Report successfully written to {self.report_path}")
        except Exception as e:
            self.logger.exception(f"Failed to write report: {str(e)}")
