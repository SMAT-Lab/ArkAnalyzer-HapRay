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
import traceback
from typing import Any, Optional

import pandas as pd

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
        memory_db_paths: list[str],
        time_ranges: Optional[list[dict]] = None,
    ) -> dict[str, Any]:
        """分析内存数据

        Args:
            scene_dir: 场景目录
            memory_db_paths: memory.db 文件路径列表（每个 step 一个）
            time_ranges: 时间范围列表（可选）

        Returns:
            分析结果字典，包含每个 step 的记录和统计信息
        """
        start_time = time.time()

        try:
            # 存储每个 step 的数据
            step_memory_data = {}

            # 分析每个 step
            for step_idx, db_path in enumerate(memory_db_paths, start=1):
                if not os.path.exists(db_path):
                    logging.warning('Memory database not found: %s', db_path)
                    continue

                logging.info('Analyzing memory for step%d: %s', step_idx, db_path)
                step_start = time.time()

                # 加载数据
                data = self.data_loader.load_all_data(db_path)

                # 生成记录
                records = self.record_generator.generate_records(
                    events=data['events'],
                    processes=data['processes'],
                    threads=data['threads'],
                    data_dict=data['data_dict'],
                    trace_start_ts=data['trace_start_ts'],
                    step_idx=step_idx,
                )

                # 计算统计信息
                stats = self.record_generator.calculate_stats(data['events'])

                step_memory_data[f'step{step_idx}'] = {
                    'stats': stats,
                    'records': records,
                }

                # 导出 records 到 Excel（放在 memory.db 同目录）
                self._export_records_to_excel(db_path, records, step_idx)

                step_time = time.time() - step_start
                logging.info(
                    'Native Memory analysis for step%d completed, %d records, %.2f seconds',
                    step_idx,
                    len(records),
                    step_time,
                )

            # 保存结果到 JSON 文件
            if step_memory_data:
                self._save_to_json(scene_dir, step_memory_data)

            total_time = time.time() - start_time
            logging.info('Memory analysis completed in %.2f seconds', total_time)

            return {
                'status': 'success',
                'step_count': len(step_memory_data),
                'total_time': total_time,
            }

        except Exception as e:
            logging.error('Memory analysis failed: %s', str(e))
            return {
                'status': 'error',
                'error': str(e),
            }

    def _save_to_json(self, scene_dir: str, step_memory_data: dict[str, Any]):
        """保存内存数据到 JSON 文件

        Args:
            scene_dir: 场景目录
            step_memory_data: 步骤内存数据
        """
        report_dir = os.path.join(scene_dir, 'report')
        os.makedirs(report_dir, exist_ok=True)

        native_memory_json_path = os.path.join(report_dir, 'native_memory.json')

        try:
            # 使用流式写入避免内存溢出
            with open(native_memory_json_path, 'w', encoding='utf-8') as f:
                f.write('{\n')

                is_first = True
                for step_key, memory_data in step_memory_data.items():
                    if not is_first:
                        f.write(',\n')
                    is_first = False

                    # 写入步骤键
                    f.write(f'  "{step_key}": ')

                    # 分块写入数据
                    stats = memory_data['stats']
                    records = memory_data['records']

                    f.write('{\n')
                    f.write(f'    "stats": {json.dumps(stats)},\n')
                    f.write('    "records": [\n')

                    # 分批写入记录，避免一次性序列化所有记录
                    batch_size = 1000
                    for i in range(0, len(records), batch_size):
                        batch = records[i : i + batch_size]
                        for idx, record in enumerate(batch):
                            is_last = i + idx == len(records) - 1
                            f.write(f'      {json.dumps(record)}')
                            if not is_last:
                                f.write(',')
                            f.write('\n')

                    f.write('    ]\n')
                    f.write('  }')

                f.write('\n}\n')

            logging.info('Saved Native Memory data to: %s', native_memory_json_path)

        except Exception as e:
            logging.error('Failed to save Native Memory JSON: %s', str(e))
            raise

    def _export_records_to_excel(self, db_path: str, records: list[dict[str, Any]], step_idx: int):
        """导出 records 到 Excel 文件（优化版本）

        Args:
            db_path: memory.db 文件路径
            records: 记录列表
            step_idx: 步骤索引
        """
        try:
            start_time = time.time()

            # 获取 memory.db 所在目录
            db_dir = os.path.dirname(db_path)
            excel_path = os.path.join(db_dir, f'memory_records_step{step_idx}.xlsx')

            logging.info('开始导出 %d 条记录到 Excel...', len(records))

            # 优化1: 使用 xlsxwriter 引擎（比 openpyxl 快 3-5 倍）
            # 优化2: 禁用常量内存优化以提升速度
            # 优化3: 使用字典列表直接构造 DataFrame（避免额外的数据复制）
            df = pd.DataFrame(records)

            df_time = time.time()
            logging.info('  DataFrame 构造完成，耗时 %.2f 秒', df_time - start_time)

            # 使用 xlsxwriter 引擎导出（速度更快）
            with pd.ExcelWriter(
                excel_path, engine='xlsxwriter', engine_kwargs={'options': {'strings_to_numbers': False}}
            ) as writer:
                df.to_excel(writer, sheet_name=f'Step{step_idx}', index=False)

                # 优化4: 禁用自动列宽计算（节省大量时间）
                worksheet = writer.sheets[f'Step{step_idx}']
                # 设置固定列宽（避免自动计算）
                worksheet.set_column(0, len(df.columns) - 1, 15)

            write_time = time.time()
            total_time = write_time - start_time

            # 获取文件大小
            file_size_mb = os.path.getsize(excel_path) / (1024 * 1024)

            logging.info('Excel 导出完成: %s', excel_path)
            logging.info('  记录数: %d, 文件大小: %.2f MB', len(records), file_size_mb)
            logging.info(
                '  总耗时: %.2f 秒 (DataFrame: %.2f 秒, 写入: %.2f 秒)',
                total_time,
                df_time - start_time,
                write_time - df_time,
            )
            logging.info('  导出速度: %.0f 条/秒', len(records) / total_time if total_time > 0 else 0)

        except Exception as e:
            logging.error('Failed to export records to Excel: %s', str(e))
            logging.error('Traceback: %s', traceback.format_exc())
