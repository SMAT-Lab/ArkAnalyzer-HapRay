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
from hapray.core.common.memory import MemoryAnalyzerCore, MemoryDataLoader


class MemoryAnalyzer(BaseAnalyzer):
    """内存分析器

    参考 FrameLoadAnalyzer 的架构，使用核心分析器进行分析
    所有计算逻辑都在 Python 中完成，不再依赖 SA

    注意：
    1. 内存分析是全局分析，不是按步骤分析
       - 第一次调用时（step1）：收集所有包含 native_hook 数据的 trace.db 文件并执行分析
       - 后续调用时（step2, step3...）：直接返回已有结果
    2. 内存数据从 htrace/stepX/trace.htrace 中获取，不再使用单独的 memory 目录
    3. 只处理包含 native_hook 表且有数据的 trace.db
    """

    def __init__(self, scene_dir: str, time_ranges: list[dict] = None):
        super().__init__(scene_dir, 'more/memory_analysis')
        self.time_ranges = time_ranges
        self.core_analyzer = MemoryAnalyzerCore()
        self._analysis_done = False  # 标记是否已完成分析

    def _analyze_impl(
        self, step_dir: str, trace_db_path: str, perf_db_path: str, app_pids: list
    ) -> Optional[dict[str, Any]]:
        """执行内存分析

        内存分析是全局分析，只在第一次调用时执行
        后续调用直接返回已有结果

        Args:
            step_dir: 步骤目录（未使用，保留用于接口兼容）
            trace_db_path: trace.db 路径（未使用，保留用于接口兼容）
            perf_db_path: perf.db 路径（未使用，保留用于接口兼容）
            app_pids: 应用进程 ID 列表（未使用，保留用于接口兼容）
        """
        # 如果已经完成分析，直接返回结果
        if self._analysis_done:
            return self._load_memory_analysis_result()

        # 第一次调用时执行分析
        # 收集所有包含 native_hook 数据的 trace.db 路径
        trace_db_paths = self._collect_memory_db_paths()

        if not trace_db_paths:
            logging.warning('No trace database files with native_hook data found')
            self._analysis_done = True
            return None

        logging.info('Found %d trace database files with native_hook data', len(trace_db_paths))

        # 使用核心分析器进行分析
        result = self.core_analyzer.analyze_memory(
            scene_dir=self.scene_dir,
            memory_db_paths=trace_db_paths,
            time_ranges=self.time_ranges,
        )

        self._analysis_done = True

        if result.get('status') == 'success':
            return self._load_memory_analysis_result()

        return None

    def _collect_memory_db_paths(self) -> list[str]:
        """收集所有 step 的 trace.db 文件路径（包含 native_hook 数据）

        从 htrace/stepX/trace.htrace 获取数据，如果 trace.db 不存在则自动转换
        只返回包含 native_hook 表且有数据的数据库

        Returns:
            包含 native_hook 数据的 trace.db 文件路径列表
        """
        trace_db_paths = []

        # 遍历所有可能的 step 目录
        step_idx = 1
        while True:
            htrace_step_dir = os.path.join(self.scene_dir, 'htrace', f'step{step_idx}')
            trace_db_path = os.path.join(htrace_step_dir, 'trace.db')
            trace_htrace_path = os.path.join(htrace_step_dir, 'trace.htrace')

            logging.debug('Checking trace database path: %s', trace_db_path)

            # 如果 trace.db 已存在
            if os.path.exists(trace_db_path):
                # 检查是否包含 native_hook 数据
                if MemoryDataLoader.has_native_hook_data(trace_db_path):
                    trace_db_paths.append(trace_db_path)
                    logging.info('Found trace database with native_hook data: %s', trace_db_path)
                else:
                    logging.info('Trace database exists but has no native_hook data: %s', trace_db_path)
                step_idx += 1
                continue

            # 如果 trace.htrace 存在，转换为 trace.db
            if os.path.exists(trace_htrace_path):
                logging.info('Converting trace.htrace to trace.db for step%d...', step_idx)
                if ExeUtils.convert_data_to_db(trace_htrace_path, trace_db_path):
                    # 检查转换后的数据库是否包含 native_hook 数据
                    if MemoryDataLoader.has_native_hook_data(trace_db_path):
                        trace_db_paths.append(trace_db_path)
                        logging.info('Successfully converted trace.htrace with native_hook data: %s', trace_db_path)
                    else:
                        logging.info('Converted trace.db but has no native_hook data: %s', trace_db_path)
                    step_idx += 1
                    continue
                logging.error('Failed to convert trace.htrace to trace.db: %s', trace_htrace_path)
                break

            # 既没有 .db 也没有 .htrace，结束循环
            logging.debug('No trace data found for step%d', step_idx)
            break

        if not trace_db_paths:
            logging.warning(
                'No trace databases with native_hook data found in %s', os.path.join(self.scene_dir, 'htrace')
            )

        return trace_db_paths

    def _load_memory_analysis_result(self) -> Optional[dict[str, Any]]:
        """加载内存分析结果

        Returns:
            包含内存分析结果的字典，如果未找到则返回 None
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
