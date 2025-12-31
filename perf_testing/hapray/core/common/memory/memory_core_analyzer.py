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
import sqlite3
import time
from typing import Any

from .memory_classifier import MemoryClassifier
from .memory_data_loader import MemoryDataLoader
from .memory_record_generator import MemoryRecordGenerator
from .memory_statistic_loader import MemoryStatisticLoader
from .memory_statistic_record_generator import MemoryStatisticRecordGenerator


class MemoryAnalyzerCore:
    """内存分析器核心

    参考 FrameAnalyzerCore 的架构，使用模块化组件：
    1. 数据加载 - MemoryDataLoader
    2. 分类器 - MemoryClassifier
    3. 记录生成 - MemoryRecordGenerator
    4. 核心协调 - 本类
    """

    def __init__(self, use_refined_lib_symbol: bool = False, collect_comparison_data: bool = False):
        """初始化内存分析器核心

        Args:
            use_refined_lib_symbol: 是否使用refined的lib_id和symbol_id
            collect_comparison_data: 是否收集对比数据（不立即导出，由调用方统一导出）
        """
        self.classifier = MemoryClassifier()
        self.record_generator = MemoryRecordGenerator(self.classifier, use_refined_lib_symbol)
        self.statistic_generator = MemoryStatisticRecordGenerator(self.classifier, use_refined_lib_symbol)
        self.data_loader = MemoryDataLoader()
        self.use_refined_lib_symbol = use_refined_lib_symbol
        self.collect_comparison_data = collect_comparison_data

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
            app_pids: 应用进程ID列表

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

            # 优先检查 native_hook 表是否有数据
            has_native_hook = MemoryDataLoader.has_native_hook_data(memory_db_path)
            has_statistic = MemoryStatisticLoader.has_native_hook_statistic_data(memory_db_path)

            if not has_native_hook and not has_statistic:
                logging.error('❌ 无可用的内存数据（native_hook 和 native_hook_statistic 表均无数据）')
                return step_memory_data

            # 根据数据源选择不同的分析路径
            if has_native_hook:
                logging.info('✅ 使用 native_hook 表数据（明细数据，精度最高）')
                step_memory_data = self._analyze_from_native_hook(memory_db_path, app_pids, scene_dir, step_start)
            else:
                logging.warning('⚠️ native_hook 表无数据，使用 native_hook_statistic 表数据（统计数据）')
                logging.warning('   注意：统计数据会损失时间精度、线程信息和地址信息')
                step_memory_data = self._analyze_from_statistic(memory_db_path, app_pids, scene_dir, step_start)

            total_time = time.time() - start_time
            logging.info('Memory analysis completed in %.2f seconds', total_time)

            return step_memory_data

        except Exception as e:
            logging.error('Memory analysis failed: %s', str(e))
            return {
                'status': 'error',
                'error': str(e),
            }

    def _analyze_from_native_hook(
        self,
        memory_db_path: str,
        app_pids: list,
        scene_dir: str,
        step_start: float,
    ) -> dict[str, Any]:
        """从 native_hook 表分析内存数据（原有逻辑）

        Args:
            memory_db_path: trace.db 文件路径
            app_pids: 应用进程ID列表
            scene_dir: 场景目录
            step_start: 步骤开始时间

        Returns:
            分析结果字典
        """
        # 加载数据（仅分析目标 app 进程）
        data = self.data_loader.load_all_data(memory_db_path, app_pids)

        # 如果启用了refined模式，设置数据库连接
        if self.use_refined_lib_symbol:
            try:
                conn = sqlite3.connect(memory_db_path)
                self.record_generator.set_db_connection(conn)
            except Exception as e:
                logging.warning('Failed to set db connection for refined mode: %s', str(e))

        # 生成记录与峰值
        if self.collect_comparison_data and self.use_refined_lib_symbol:
            # 如果启用了对比数据收集，同时生成原始值和refined值的记录
            gen_result = self.record_generator.generate_records_with_original(
                events=data['events'],
                processes=data['processes'],
                threads=data['threads'],
                data_dict=data['data_dict'],
                trace_start_ts=data['trace_start_ts'],
                sub_type_names=data.get('sub_type_names', {}),
            )
            records = gen_result['refined_records']
            original_records = gen_result['original_records']
            # 获取已缓存的调用链数据
            callchain_cache = self.record_generator.callchain_cache

            # 返回对比数据，由调用方决定何时导出
            step_memory_data = {
                'peak_time': gen_result.get('peak_time', 0),
                'peak_value': gen_result.get('peak_value', 0),
                'records': records,
                'callchains': self.record_generator.generate_callchain(data['callchains'], data['data_dict']),
                'dataDict': data.get('data_dict', {}),
                # 对比数据
                'original_records': original_records,
                'callchain_cache': callchain_cache,
                'data_source': 'native_hook',  # 标记数据源
            }
        else:
            # 正常模式：只生成refined值的记录
            gen_result = self.record_generator.generate_records(
                events=data['events'],
                processes=data['processes'],
                threads=data['threads'],
                data_dict=data['data_dict'],
                trace_start_ts=data['trace_start_ts'],
                sub_type_names=data.get('sub_type_names', {}),
            )
            records = gen_result['records']

            step_memory_data = {
                'peak_time': gen_result.get('peak_time', 0),
                'peak_value': gen_result.get('peak_value', 0),
                'records': records,
                'callchains': self.record_generator.generate_callchain(data['callchains'], data['data_dict']),
                'dataDict': data.get('data_dict', {}),
                'data_source': 'native_hook',  # 标记数据源
            }

        step_time = time.time() - step_start
        logging.info(
            'Native Memory analysis for %s completed, %d records, %.2f seconds',
            scene_dir,
            len(records),
            step_time,
        )

        return step_memory_data

    def _analyze_from_statistic(
        self,
        memory_db_path: str,
        app_pids: list,
        scene_dir: str,
        step_start: float,
    ) -> dict[str, Any]:
        """从 native_hook_statistic 表分析内存数据（新增逻辑）

        Args:
            memory_db_path: trace.db 文件路径
            app_pids: 应用进程ID列表
            scene_dir: 场景目录
            step_start: 步骤开始时间

        Returns:
            分析结果字典
        """
        # 加载统计数据
        data = MemoryStatisticLoader.load_statistic_data(memory_db_path, app_pids)

        # 如果启用了refined模式，设置数据库连接
        if self.use_refined_lib_symbol:
            try:
                conn = sqlite3.connect(memory_db_path)
                self.statistic_generator.set_db_connection(conn)
                logging.info('✓ Enabled refined mode for statistic data analysis')
            except Exception as e:
                logging.warning('Failed to set db connection for refined mode: %s', str(e))

        # 生成记录（从统计数据展开）
        gen_result = self.statistic_generator.generate_records_from_statistic(
            statistic_events=data['statistic_events'],
            processes=data['processes'],
            threads=data['threads'],
            data_dict=data['data_dict'],
            trace_start_ts=data['trace_start_ts'],
            sub_type_names=data.get('sub_type_names', {}),
        )
        records = gen_result['records']

        step_memory_data = {
            'peak_time': gen_result.get('peak_time', 0),
            'peak_value': gen_result.get('peak_value', 0),
            'records': records,
            'callchains': self.record_generator.generate_callchain(data['callchains'], data['data_dict']),
            'dataDict': data.get('data_dict', {}),
            'data_source': 'native_hook_statistic',  # 标记数据源
            'data_quality_warning': '使用统计数据，时间精度、线程信息和地址信息缺失',
        }

        step_time = time.time() - step_start
        mode_info = 'refined mode' if self.use_refined_lib_symbol else 'original mode'
        logging.info(
            'Native Memory analysis (from statistic) for %s completed, %d records, %.2f seconds [%s]',
            scene_dir,
            len(records),
            step_time,
            mode_info,
        )

        return step_memory_data
