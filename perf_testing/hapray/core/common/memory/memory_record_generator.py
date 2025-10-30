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
from typing import Any

from .memory_classifier import MemoryClassifier


class MemoryRecordGenerator:
    """内存记录生成器

    负责将原始事件数据转换为前端可用的记录格式
    """

    def __init__(self, classifier: MemoryClassifier):
        """初始化记录生成器

        Args:
            classifier: 内存分类器实例
        """
        self.classifier = classifier

    def generate_records(
        self,
        events: list[dict],
        processes: list[dict],
        threads: list[dict],
        data_dict: dict[int, str],
        trace_start_ts: int,
        step_idx: int = 1,
    ) -> list[dict[str, Any]]:
        """生成平铺的内存记录

        新逻辑：
        1. 为每个事件生成一条记录，不再聚合
        2. 每条记录包含所有 4 个维度的信息（pid, tid, fileId, symbolId）
        3. 如果某个维度没有信息，则设为 null
        4. 记录包含 heapSize（单次分配/释放大小）和 relativeTs（相对时间戳）
        5. 根据文件、符号、线程进行分类，获取大类和小类信息
        6. 前端根据不同维度的 key 进行独立计算

        Args:
            events: 事件列表
            processes: 进程列表
            threads: 线程列表
            data_dict: 数据字典（符号和文件名）
            trace_start_ts: Trace 起始时间戳
            step_idx: 步骤索引

        Returns:
            内存记录列表
        """
        # 构建映射
        process_map = {p['id']: p for p in processes}
        thread_map = {t['id']: t for t in threads}

        records = []

        for event in events:
            # 获取进程信息
            process = process_map.get(event['ipid'])
            if not process:
                continue

            # 获取线程信息
            thread = thread_map.get(event['itid'])

            # 获取文件和符号信息
            file_path = None
            symbol_name = None
            file_id = None
            symbol_id = None

            # 获取文件信息 - 直接从 data_dict 表中查询
            if event.get('last_lib_id') and event['last_lib_id'] > 0:
                file_id = event['last_lib_id']
                file_path = data_dict.get(event['last_lib_id'], 'unknown')

            # 获取符号信息 - 直接从 data_dict 表中查询
            if event.get('last_symbol_id') and event['last_symbol_id'] > 0:
                symbol_id = event['last_symbol_id']
                symbol_name = data_dict.get(event['last_symbol_id'], 'unknown')

            # 分类
            classification = self.classifier.get_final_classification(
                file_path=file_path,
                symbol_name=symbol_name,
                thread_name=thread.get('name') if thread else None,
            )

            # 创建记录
            record = {
                'stepIdx': step_idx,
                # 进程维度信息
                'pid': process['pid'],
                'process': process['name'],
                # 线程维度信息
                'tid': thread['tid'] if thread else None,
                'thread': thread['name'] if thread else None,
                # 文件维度信息
                'fileId': file_id,
                'file': file_path,
                # 符号维度信息
                'symbolId': symbol_id,
                'symbol': symbol_name,
                # 事件信息
                'eventType': event['event_type'],
                'subEventType': '',  # 可以从 sub_type_names 获取
                # 内存大小（单次分配/释放的大小）
                'heapSize': event['heap_size'],
                # 当前时间点的累积内存值
                'allHeapSize': event['all_heap_size'],
                # 相对时间戳（相对于 trace 开始时间）
                'relativeTs': event['start_ts'] - trace_start_ts,
                # 分类信息 - 大类
                'componentName': classification['sub_category_name'],
                'componentCategory': classification['category'],
                # 分类信息 - 小类（从符号、文件、线程等推断）
                'categoryName': classification['category_name'],
                'subCategoryName': classification['sub_category_name'],
            }

            records.append(record)

        logging.info('Generated %d memory records for step %d', len(records), step_idx)
        return records

    @staticmethod
    def calculate_stats(events: list[dict]) -> dict[str, Any]:
        """计算内存统计信息（峰值、平均值、持续时间）

        Args:
            events: 事件列表

        Returns:
            统计信息字典
        """
        if not events:
            return {
                'peak_memory_size': 0,
                'peak_memory_duration': 0,
                'average_memory_size': 0,
            }

        peak_memory_size = 0
        peak_memory_duration = 0
        total_memory = 0
        memory_count = 0

        # 遍历所有事件，计算峰值和平均值
        for event in events:
            current_size = event.get('all_heap_size', 0)
            if current_size > peak_memory_size:
                peak_memory_size = current_size
                peak_memory_duration = event.get('current_size_dur', 0)
            total_memory += current_size
            memory_count += 1

        average_memory_size = total_memory / memory_count if memory_count > 0 else 0

        return {
            'peak_memory_size': peak_memory_size,
            'peak_memory_duration': peak_memory_duration,
            'average_memory_size': average_memory_size,
        }
