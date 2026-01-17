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
import threading
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from typing import Optional

from hapray.core.report import ReportGenerator


class RealTimeAnalysisProcess:
    """
    Real-time analysis process - responsible for real-time analysis after data collection completes.

    According to the architecture diagram, the real-time analysis process includes three types of analysis:
    1. Image analysis - analyze image size and optimization
    2. Empty frame detection - detect empty frames
    3. hilog analysis - analyze system logs

    This process runs synchronously with the main process, sharing data through the file system.

    This class implements a singleton pattern to ensure only one instance exists across the application.
    """

    _instance: Optional['RealTimeAnalysisProcess'] = None
    _lock = threading.Lock()

    def __new__(cls, max_workers: int = 4, logger: Optional[logging.Logger] = None):
        """Singleton pattern implementation"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self, max_workers: int = 4, logger: Optional[logging.Logger] = None):
        """
        Initialize real-time analysis process.

        Args:
            max_workers: Maximum number of worker threads in thread pool
            logger: Logger instance
        """
        # Only initialize once
        if self._initialized:
            return

        self.max_workers = max_workers
        self.logger = logger or logging.getLogger(__name__)
        self.executor: Optional[ThreadPoolExecutor] = None
        self.futures: dict[Future, dict] = {}
        self.lock = threading.Lock()
        self.task_analysis_status: dict[str, list[Future]] = {}  # Task name -> analysis task list
        self._initialized = True

    @classmethod
    def get_instance(cls) -> Optional['RealTimeAnalysisProcess']:
        """Get the singleton instance (must be initialized first)"""
        return cls._instance

    def start(self):
        """Start real-time analysis process"""
        self.executor = ThreadPoolExecutor(max_workers=self.max_workers)
        self.logger.info('Real-time analysis process started (workers: %d)', self.max_workers)

    def notify_data_collected(self, report_path: str, step_id: int = 0) -> None:
        """
        Notify that data collection is complete, trigger real-time analysis task.

        According to the architecture diagram, after collection completes, notify data analysis tasks, including:
        - perf/trace data
        - Screenshots
        - Component tree
        - hilog

        Args:
            report_path: Step data path
            step_id: Step number
        """
        if not self.executor:
            self.logger.warning('Real-time analysis process not started, skipping analysis task')
            return

        self.logger.info(
            'Data collection completed, submitting real-time analysis task: path=%s, step=%d', report_path, step_id
        )

        task_key = f'task{report_path}'
        if task_key not in self.task_analysis_status:
            self.task_analysis_status[task_key] = []

        # Submit real-time step analysis task (use analyze_data and ReportGenerator to execute complete analysis pipeline)
        def analyze_and_generate_report(scene_dir: str) -> bool:
            """Analyze data and generate report"""
            try:
                # Generate report
                report_generator = ReportGenerator()
                return report_generator.generate_report(
                    scene_dirs=[scene_dir],
                    scene_dir=scene_dir,
                )
            except Exception as e:
                self.logger.error('Analysis task execution failed: %s', str(e))
                return False

        future = self.executor.submit(analyze_and_generate_report, report_path)
        with self.lock:
            self.futures[future] = {'type': 'scene_analysis', 'step': step_id, 'path': report_path}
            self.task_analysis_status[task_key].append(future)

    def wait_completion(self) -> None:
        """Wait for all analysis tasks to complete"""
        if not self.executor:
            return

        self.logger.info('Waiting for all real-time analysis tasks to complete...')

        for future in as_completed(self.futures):
            task_info = self.futures[future]
            try:
                success = future.result()
                status = 'Success' if success else 'Failed'
                self.logger.info(
                    'Analysis task completed [%s]: %s (step=%d, path=%s)',
                    status,
                    task_info['type'],
                    task_info['step'],
                    task_info['path'],
                )
            except Exception as e:
                self.logger.error('Analysis task exception: %s, Error: %s', task_info['type'], str(e))

    def shutdown(self) -> None:
        """Shutdown real-time analysis process"""
        if self.executor:
            self.logger.info('Shutting down real-time analysis process...')
            self.executor.shutdown(wait=True)
            self.executor = None
            self.logger.info('Real-time analysis process shutdown')
