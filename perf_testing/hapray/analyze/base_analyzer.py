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
import time
from abc import ABC, abstractmethod
from typing import Any, Optional


class BaseAnalyzer(ABC):
    """
    Abstract base class for all data analyzers.
    """

    def __init__(self, scene_dir: str, report_path: str):
        """Initialize base analyzer.

        Args:
            scene_dir: Root directory of the scene
            report_path: report path of result dict
        """
        self.results: dict[str, Any] = {}
        self.scene_dir = scene_dir
        self.report_path = report_path
        self.logger = logging.getLogger(self.__class__.__name__)

    def analyze(self, step_dir: str, trace_db_path: str, perf_db_path: str):
        """Public method to execute analysis for a single step.

        Args:
            step_dir: Identifier for the current step
            trace_db_path: Path to trace database
            perf_db_path: Path to performance database
        """
        try:
            start_time = time.time()
            pids = AnalyzerHelper.get_app_pids(self.scene_dir, step_dir)
            result = self._analyze_impl(step_dir, trace_db_path, perf_db_path, pids)
            if result:
                self.results[step_dir] = result
            self.logger.info(
                'Analysis completed for step %s in %.2f seconds [%s]',
                step_dir,
                time.time() - start_time,
                self.report_path,
            )
        except Exception as e:
            self.logger.error('Analysis failed for step %s: %s [%s]', step_dir, str(e), self.report_path)
            self.results[step_dir] = {'error': str(e)}

    @abstractmethod
    def _analyze_impl(
        self, step_dir: str, trace_db_path: str, perf_db_path: str, app_pids: list
    ) -> Optional[dict[str, Any]]:
        """Implementation of the analysis logic.

        Args:
            step_dir: Identifier for the current step
            trace_db_path: Path to trace database
            perf_db_path: Path to performance database

        Returns:
            Analysis results as a dictionary
        """

    def write_report(self, result: dict):
        """Write analysis results to JSON report."""
        if not self.results:
            self.logger.warning('No results to write. Skipping report generation for %s', self.report_path)
            return

        try:
            file_path = os.path.join(self.scene_dir, 'report', self.report_path.replace('/', '_') + '.json')
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(sorted(self.results.items()), f, ensure_ascii=False)
            self.logger.info('Report successfully written to %s', file_path)
        except Exception as e:
            self.logger.exception('Failed to write report: %s', str(e))

        dict_path = self.report_path.split('/')
        v = result
        for key in dict_path:
            if key == dict_path[-1]:
                break
            if key not in v:
                v[key] = {}
            v = v[key]
        v[dict_path[-1]] = self.results


class AnalyzerHelper:
    _pid_cache = {}

    @staticmethod
    def get_app_pids(scene_dir: str, step_id: str) -> list:
        """获取应用进程ID列表

        Args:
            scene_dir: 场景目录路径
            step_id: 步骤ID，如'step1'或'1'

        Returns:
            list: 进程ID列表
        """
        # 检查缓存
        cache_key = f'{scene_dir}-{step_id}'
        if cache_key in AnalyzerHelper._pid_cache:
            logging.debug('使用已缓存的PID数据: %s', cache_key)
            return AnalyzerHelper._pid_cache[cache_key]

        try:
            # 处理step_id，去掉'step'前缀
            step_number = int(step_id.replace('step', ''))

            # 构建pids.json文件路径
            pids_json_path = os.path.join(scene_dir, 'hiperf', f'step{step_number}', 'pids.json')

            if not os.path.exists(pids_json_path):
                logging.warning('No pids.json found at %s', pids_json_path)
                return []

            # 读取JSON文件
            with open(pids_json_path, encoding='utf-8') as f:
                pids_data = json.load(f)

            # 提取pids和process_names
            pids = pids_data.get('pids', [])
            process_names = pids_data.get('process_names', [])

            if not pids or not process_names:
                logging.warning('No valid pids or process_names found in %s', pids_json_path)
                return []

            # 确保pids和process_names长度一致
            if len(pids) != len(process_names):
                logging.warning(
                    'Mismatch between pids (%s) and process_names (%s) in %s',
                    len(pids),
                    len(process_names),
                    pids_json_path,
                )
                # 取较短的长度
                min_length = min(len(pids), len(process_names))
                pids = pids[:min_length]
                process_names = process_names[:min_length]

            # 缓存PID数据
            AnalyzerHelper._pid_cache[cache_key] = pids

            logging.debug('缓存PID数据: %s, PIDs: %s', step_id, len(pids))
            return pids

        except Exception as e:
            logging.error('Failed to get app PIDs: %s', str(e))
            return []
