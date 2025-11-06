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
    ) -> dict[str, Any]:
        """生成平铺的内存记录

        新逻辑：
        1. 为每个事件生成一条记录，不再聚合
        2. 每条记录包含所有 4 个维度的信息（pid, tid, fileId, symbolId）
        3. 如果某个维度没有信息，则设为 null
        4. 记录包含 heapSize（单次分配/释放大小）和 relativeTs（相对时间戳）
        5. 根据文件、符号、线程进行分类，获取大类和小类信息
        6. 为每条记录计算所有维度的统计信息：
           - 4个基础维度（进程、线程、文件、符号）
           - 3个聚合维度（大分类、小分类、事件类型）
        7. 释放事件继承对应分配事件的分类信息（通过地址匹配）

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
        from collections import defaultdict

        # 构建映射
        process_map = {p['id']: p for p in processes}
        thread_map = {t['id']: t for t in threads}

        # 地址 -> 分配事件的分类信息（用于释放事件继承分类）
        # 使用栈结构支持同一地址的多次分配/释放（LIFO）
        addr_to_alloc_classification: dict[int, list[dict]] = defaultdict(list)

        records = []
        # 计算累计内存与峰值（events 已按 start_ts 升序载入）
        current_total = 0
        peak_value = 0
        peak_time = 0

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
            last_lib_id = event.get('last_lib_id')
            if last_lib_id is not None and last_lib_id > 0:
                file_id = last_lib_id
                file_path = data_dict.get(last_lib_id, 'unknown')

            # 获取符号信息 - 直接从 data_dict 表中查询
            last_symbol_id = event.get('last_symbol_id')
            if last_symbol_id is not None and last_symbol_id > 0:
                symbol_id = last_symbol_id
                symbol_name = data_dict.get(last_symbol_id, 'unknown')

            evt_type = event.get('event_type')
            addr = event.get('addr')

            # 判断是分配还是释放
            is_alloc = evt_type in ('AllocEvent', 'MmapEvent', 0)
            is_free = evt_type in ('FreeEvent', 'MunmapEvent', 1)

            # 分类逻辑
            classification = None

            if is_alloc:
                # 分配事件：正常分类
                classification = self.classifier.get_final_classification(
                    file_path=file_path,
                    symbol_name=symbol_name,
                    thread_name=thread.get('name') if thread else None,
                )
                # 保存分类信息，供后续释放事件使用
                if addr is not None:
                    addr_to_alloc_classification[addr].append(classification)
            elif is_free:
                # 释放事件：尝试继承对应分配事件的分类信息
                if addr is not None and addr in addr_to_alloc_classification:
                    stack = addr_to_alloc_classification[addr]
                    if stack:
                        # 使用 LIFO：取最后一次分配的分类信息
                        classification = stack.pop()
                        # 如果栈为空，清理该地址
                        if not stack:
                            del addr_to_alloc_classification[addr]

                # 如果没有找到对应的分配事件，使用当前信息分类（可能是 UNKNOWN）
                if classification is None:
                    classification = self.classifier.get_final_classification(
                        file_path=file_path,
                        symbol_name=symbol_name,
                        thread_name=thread.get('name') if thread else None,
                    )
            else:
                # 其他事件类型：正常分类
                classification = self.classifier.get_final_classification(
                    file_path=file_path,
                    symbol_name=symbol_name,
                    thread_name=thread.get('name') if thread else None,
                )

            # 构建各维度的 key
            pid = process.get('pid')
            if pid is None:
                continue

            # 创建记录
            record = {
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
                'addr': event['addr'],
                'callchainId': event['callchain_id'],
                # 内存大小（单次分配/释放的大小）
                'heapSize': event['heap_size'],
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

            # 计算累计内存变化
            size = event.get('heap_size') or 0
            # 兼容字符串/数值类型的事件类型
            if is_alloc:
                current_total += size
            elif is_free:
                current_total -= size

            if current_total > peak_value:
                peak_value = current_total
                peak_time = event.get('start_ts', 0) - trace_start_ts

        logging.info('Generated %d memory records', len(records))
        return {
            'records': records,
            'peak_value': peak_value,
            'peak_time': peak_time,
        }

    def generate_callchain(self, callchain: list[dict], data_dict: dict[int, str]) -> dict:
        """callchain symbol_id, file_id从data_dict 中读取对应的字符串"""
        if not callchain:
            return {}

        grouped: dict[int, list[dict]] = {}

        for frame in callchain:
            callchain_id = frame.get('callchain_id')
            if callchain_id is None:
                # 跳过异常数据
                continue

            symbol_id = frame.get('symbol_id')
            file_id = frame.get('file_id')

            resolved_frame = {
                'depth': frame.get('depth'),
                'ip': frame.get('ip'),
                'symbolId': symbol_id,
                'symbol': data_dict.get(symbol_id, 'unknown') if symbol_id else None,
                'fileId': file_id,
                'file': data_dict.get(file_id, 'unknown') if file_id else None,
                'offset': frame.get('offset'),
                'symbolOffset': frame.get('symbol_offset'),
                'vaddr': frame.get('vaddr'),
            }

            grouped.setdefault(callchain_id, []).append(resolved_frame)
        return grouped
