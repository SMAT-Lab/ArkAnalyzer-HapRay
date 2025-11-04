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
import time
from typing import Any

from .memory_classifier import MemoryClassifier
from .memory_data_loader import MemoryDataLoader
from .memory_record_generator import MemoryRecordGenerator


class MemoryAnalyzerCore:
    """内存分析器核心

    参考 FrameAnalyzerCore 的架构，使用模块化组件：
    1. 数据加载 - MemoryDataLoader
    2. 分类器 - MemoryClassifier
    3. 记录生成 - MemoryRecordGenerator
    4. 核心协调 - 本类
    """

    def __init__(self):
        """初始化内存分析器核心"""
        self.classifier = MemoryClassifier()
        self.record_generator = MemoryRecordGenerator(self.classifier)
        self.data_loader = MemoryDataLoader()

    def analyze_memory(
        self,
        scene_dir: str,
        memory_db_path: str,
        app_pids: list,
    ) -> dict[str, Any]:
        """分析内存数据

        Args:
            scene_dir: 场景目录
            memory_db_path: trace.db 文件路径列表（每个 step 一个，包含 native_hook 数据）
            time_ranges: 时间范围列表（可选）

        Returns:
            分析结果字典，包含每个 step 的记录和统计信息
        """
        start_time = time.time()

        try:
            # 存储每个 step 的数据
            step_memory_data = {}

            if not os.path.exists(memory_db_path):
                logging.warning('Memory database not found: %s', memory_db_path)
                return step_memory_data

            logging.info('Analyzing memory for %s', memory_db_path)
            step_start = time.time()

            # 加载数据（仅分析目标 app 进程）
            data = self.data_loader.load_all_data(memory_db_path, app_pids)

            # 生成记录与峰值
            gen_result = self.record_generator.generate_records(
                events=data['events'],
                processes=data['processes'],
                threads=data['threads'],
                data_dict=data['data_dict'],
                trace_start_ts=data['trace_start_ts'],
            )
            records = gen_result['records']

            step_memory_data = {
                'peak_time': gen_result.get('peak_time', 0),
                'peak_value': gen_result.get('peak_value', 0),
                'records': records,
                'callchains': self.record_generator.generate_callchain(data['callchains'], data['data_dict']),
            }

            step_time = time.time() - step_start
            logging.info(
                'Native Memory analysis for %s completed, %d records, %.2f seconds',
                scene_dir,
                len(records),
                step_time,
            )

            total_time = time.time() - start_time
            logging.info('Memory analysis completed in %.2f seconds', total_time)

            return step_memory_data

        except Exception as e:
            logging.error('Memory analysis failed: %s', str(e))
            return {
                'status': 'error',
                'error': str(e),
            }
