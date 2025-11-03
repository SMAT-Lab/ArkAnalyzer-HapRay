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
        6. 为每条记录计算所有维度的统计信息：
           - 4个基础维度（进程、线程、文件、符号）
           - 3个聚合维度（大分类、小分类、事件类型）

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

        # 按相对时间排序事件
        sorted_events = sorted(events, key=lambda e: e['start_ts'])

        # 计算每个维度的统计信息
        dimension_stats = self._calculate_dimension_stats(sorted_events, process_map, thread_map, data_dict)

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
            last_lib_id = event.get('last_lib_id')
            if last_lib_id is not None and last_lib_id > 0:
                file_id = last_lib_id
                file_path = data_dict.get(last_lib_id, 'unknown')

            # 获取符号信息 - 直接从 data_dict 表中查询
            last_symbol_id = event.get('last_symbol_id')
            if last_symbol_id is not None and last_symbol_id > 0:
                symbol_id = last_symbol_id
                symbol_name = data_dict.get(last_symbol_id, 'unknown')

            # 分类
            classification = self.classifier.get_final_classification(
                file_path=file_path,
                symbol_name=symbol_name,
                thread_name=thread.get('name') if thread else None,
            )

            # 构建各维度的 key
            pid = process.get('pid')
            if pid is None:
                continue

            tid = thread.get('tid') if thread else None
            process_key = pid
            thread_key = (pid, tid) if tid is not None else None
            file_key = (pid, tid, file_id) if tid is not None and file_id is not None else None
            symbol_key = (
                (pid, tid, file_id, symbol_id)
                if tid is not None and file_id is not None and symbol_id is not None
                else None
            )

            # 获取各维度的统计信息
            default_stats = {'peakMem': 0, 'avgMem': 0, 'totalAllocMem': 0, 'totalFreeMem': 0, 'eventNum': 0}

            process_stats = dimension_stats['process'].get(process_key, default_stats)
            thread_stats = dimension_stats['thread'].get(thread_key, default_stats) if thread_key else default_stats
            file_stats = dimension_stats['file'].get(file_key, default_stats) if file_key else default_stats
            symbol_stats = dimension_stats['symbol'].get(symbol_key, default_stats) if symbol_key else default_stats

            # 获取聚合维度的统计信息
            category_key = classification['category_name']
            component_key = (classification['category_name'], classification['sub_category_name'])

            # 事件类型 key（合并 AllocEvent/FreeEvent，处理 MmapEvent/MunmapEvent）
            event_type = event['event_type']
            sub_event_type = ''  # 可以从 sub_type_names 获取
            if event_type in ('AllocEvent', 'FreeEvent'):
                event_type_key = 'AllocEvent'
            elif event_type in ('MmapEvent', 'MunmapEvent'):
                event_type_key = sub_event_type if sub_event_type else 'Other MmapEvent'
            else:
                event_type_key = event_type

            category_stats = dimension_stats['category'].get(category_key, default_stats)
            component_stats = dimension_stats['component'].get(component_key, default_stats)
            event_type_stats = dimension_stats['eventType'].get(event_type_key, default_stats)

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
                # 进程维度统计
                'processPeakMem': process_stats['peakMem'],
                'processAvgMem': process_stats['avgMem'],
                'processTotalAllocMem': process_stats['totalAllocMem'],
                'processTotalFreeMem': process_stats['totalFreeMem'],
                'processEventNum': process_stats['eventNum'],
                # 线程维度统计
                'threadPeakMem': thread_stats['peakMem'],
                'threadAvgMem': thread_stats['avgMem'],
                'threadTotalAllocMem': thread_stats['totalAllocMem'],
                'threadTotalFreeMem': thread_stats['totalFreeMem'],
                'threadEventNum': thread_stats['eventNum'],
                # 文件维度统计
                'filePeakMem': file_stats['peakMem'],
                'fileAvgMem': file_stats['avgMem'],
                'fileTotalAllocMem': file_stats['totalAllocMem'],
                'fileTotalFreeMem': file_stats['totalFreeMem'],
                'fileEventNum': file_stats['eventNum'],
                # 符号维度统计
                'symbolPeakMem': symbol_stats['peakMem'],
                'symbolAvgMem': symbol_stats['avgMem'],
                'symbolTotalAllocMem': symbol_stats['totalAllocMem'],
                'symbolTotalFreeMem': symbol_stats['totalFreeMem'],
                'symbolEventNum': symbol_stats['eventNum'],
                # 大分类维度统计（key: categoryName）
                'categoryPeakMem': category_stats['peakMem'],
                'categoryAvgMem': category_stats['avgMem'],
                'categoryTotalAllocMem': category_stats['totalAllocMem'],
                'categoryTotalFreeMem': category_stats['totalFreeMem'],
                'categoryEventNum': category_stats['eventNum'],
                # 小分类维度统计（key: categoryName|subCategoryName）
                'componentPeakMem': component_stats['peakMem'],
                'componentAvgMem': component_stats['avgMem'],
                'componentTotalAllocMem': component_stats['totalAllocMem'],
                'componentTotalFreeMem': component_stats['totalFreeMem'],
                'componentEventNum': component_stats['eventNum'],
                # 事件类型维度统计（key: eventTypeName）
                'eventTypePeakMem': event_type_stats['peakMem'],
                'eventTypeAvgMem': event_type_stats['avgMem'],
                'eventTypeTotalAllocMem': event_type_stats['totalAllocMem'],
                'eventTypeTotalFreeMem': event_type_stats['totalFreeMem'],
                'eventTypeEventNum': event_type_stats['eventNum'],
            }

            records.append(record)

        logging.info('Generated %d memory records for step %d', len(records), step_idx)
        return records

    def _calculate_dimension_stats(
        self,
        sorted_events: list[dict],
        process_map: dict,
        thread_map: dict,
        data_dict: dict[int, str],
    ) -> dict[str, dict]:
        """计算每个维度的统计信息

        为所有维度独立计算统计信息：
        - 4个基础维度：进程、线程、文件、符号
        - 3个聚合维度：大分类、小分类、事件类型

        Args:
            sorted_events: 按时间排序的事件列表
            process_map: 进程映射
            thread_map: 线程映射
            data_dict: 数据字典（符号和文件名）

        Returns:
            维度统计信息字典，格式为：
            {
                'process': {key: {peakMem, avgMem, totalAllocMem, totalFreeMem, eventNum}},
                'thread': {key: {peakMem, avgMem, totalAllocMem, totalFreeMem, eventNum}},
                'file': {key: {peakMem, avgMem, totalAllocMem, totalFreeMem, eventNum}},
                'symbol': {key: {peakMem, avgMem, totalAllocMem, totalFreeMem, eventNum}},
                'category': {key: {peakMem, avgMem, totalAllocMem, totalFreeMem, eventNum}},
                'component': {key: {peakMem, avgMem, totalAllocMem, totalFreeMem, eventNum}},
                'eventType': {key: {peakMem, avgMem, totalAllocMem, totalFreeMem, eventNum}}
            }
        """
        # 初始化统计数据结构
        stats = {
            'process': {},  # key: pid
            'thread': {},  # key: (pid, tid)
            'file': {},  # key: (pid, tid, fileId)
            'symbol': {},  # key: (pid, tid, fileId, symbolId)
            'category': {},  # key: categoryName
            'component': {},  # key: (categoryName, subCategoryName)
            'eventType': {},  # key: eventTypeName
        }

        # 用于跟踪每个维度的累积内存
        cumulative_mem = {
            'process': {},
            'thread': {},
            'file': {},
            'symbol': {},
            'category': {},
            'component': {},
            'eventType': {},
        }

        # 用于计算平均值
        mem_sum = {
            'process': {},
            'thread': {},
            'file': {},
            'symbol': {},
            'category': {},
            'component': {},
            'eventType': {},
        }
        mem_count = {
            'process': {},
            'thread': {},
            'file': {},
            'symbol': {},
            'category': {},
            'component': {},
            'eventType': {},
        }

        # 遍历排序后的事件
        for event in sorted_events:
            process = process_map.get(event['ipid'])
            if not process:
                continue

            thread = thread_map.get(event['itid'])
            pid = process.get('pid')
            if pid is None:
                continue

            tid = thread.get('tid') if thread else None

            # 安全获取 file_id 和 symbol_id
            last_lib_id = event.get('last_lib_id')
            file_id = last_lib_id if (last_lib_id is not None and last_lib_id > 0) else None

            last_symbol_id = event.get('last_symbol_id')
            symbol_id = last_symbol_id if (last_symbol_id is not None and last_symbol_id > 0) else None

            heap_size = event.get('heap_size')
            event_type = event.get('event_type')
            sub_event_type = event.get('sub_event_type', '')

            # 跳过无效数据
            if heap_size is None or event_type is None:
                continue

            # 获取文件和符号名称（用于分类）
            file_path = data_dict.get(file_id, 'unknown') if file_id else 'unknown'
            symbol_name = data_dict.get(symbol_id, 'unknown') if symbol_id else 'unknown'

            # 分类
            classification = self.classifier.get_final_classification(
                file_path=file_path,
                symbol_name=symbol_name,
                thread_name=thread.get('name') if thread else None,
            )

            # 构建各维度的 key
            process_key = pid
            thread_key = (pid, tid) if tid is not None else None
            file_key = (pid, tid, file_id) if tid is not None and file_id is not None else None
            symbol_key = (
                (pid, tid, file_id, symbol_id)
                if tid is not None and file_id is not None and symbol_id is not None
                else None
            )

            # 构建聚合维度的 key
            category_key = classification['category_name']
            component_key = (classification['category_name'], classification['sub_category_name'])

            # 事件类型 key（合并 AllocEvent/FreeEvent，处理 MmapEvent/MunmapEvent）
            if event_type in ('AllocEvent', 'FreeEvent'):
                event_type_key = 'AllocEvent'
            elif event_type in ('MmapEvent', 'MunmapEvent'):
                event_type_key = sub_event_type if sub_event_type else 'Other MmapEvent'
            else:
                event_type_key = event_type

            # 更新进程维度
            self._update_dimension_stat(
                stats['process'],
                cumulative_mem['process'],
                mem_sum['process'],
                mem_count['process'],
                process_key,
                heap_size,
                event_type,
            )

            # 更新线程维度
            if thread_key:
                self._update_dimension_stat(
                    stats['thread'],
                    cumulative_mem['thread'],
                    mem_sum['thread'],
                    mem_count['thread'],
                    thread_key,
                    heap_size,
                    event_type,
                )

            # 更新文件维度
            if file_key:
                self._update_dimension_stat(
                    stats['file'],
                    cumulative_mem['file'],
                    mem_sum['file'],
                    mem_count['file'],
                    file_key,
                    heap_size,
                    event_type,
                )

            # 更新符号维度
            if symbol_key:
                self._update_dimension_stat(
                    stats['symbol'],
                    cumulative_mem['symbol'],
                    mem_sum['symbol'],
                    mem_count['symbol'],
                    symbol_key,
                    heap_size,
                    event_type,
                )

            # 更新大分类维度
            self._update_dimension_stat(
                stats['category'],
                cumulative_mem['category'],
                mem_sum['category'],
                mem_count['category'],
                category_key,
                heap_size,
                event_type,
            )

            # 更新小分类维度
            self._update_dimension_stat(
                stats['component'],
                cumulative_mem['component'],
                mem_sum['component'],
                mem_count['component'],
                component_key,
                heap_size,
                event_type,
            )

            # 更新事件类型维度
            self._update_dimension_stat(
                stats['eventType'],
                cumulative_mem['eventType'],
                mem_sum['eventType'],
                mem_count['eventType'],
                event_type_key,
                heap_size,
                event_type,
            )

        # 计算平均值
        for dimension in ['process', 'thread', 'file', 'symbol', 'category', 'component', 'eventType']:
            for key in stats[dimension]:
                if mem_count[dimension].get(key, 0) > 0:
                    stats[dimension][key]['avgMem'] = mem_sum[dimension][key] / mem_count[dimension][key]
                else:
                    stats[dimension][key]['avgMem'] = 0

        return stats

    @staticmethod
    def _update_dimension_stat(
        stats_dict: dict,
        cumulative_dict: dict,
        sum_dict: dict,
        count_dict: dict,
        key: Any,
        heap_size: int,
        event_type: str,
    ) -> None:
        """更新单个维度的统计信息

        Args:
            stats_dict: 统计信息字典
            cumulative_dict: 累积内存字典
            sum_dict: 内存总和字典（用于计算平均值）
            count_dict: 计数字典（用于计算平均值）
            key: 维度的 key
            heap_size: 堆大小变化
            event_type: 事件类型
        """
        if key not in stats_dict:
            stats_dict[key] = {
                'peakMem': 0,
                'avgMem': 0,
                'totalAllocMem': 0,
                'totalFreeMem': 0,
                'eventNum': 0,
            }
            cumulative_dict[key] = 0
            sum_dict[key] = 0
            count_dict[key] = 0

        # 更新累积内存
        if event_type in ['AllocEvent', 'MmapEvent']:
            cumulative_dict[key] += heap_size
            stats_dict[key]['totalAllocMem'] += heap_size
        elif event_type in ['FreeEvent', 'MunmapEvent']:
            cumulative_dict[key] -= heap_size
            stats_dict[key]['totalFreeMem'] += heap_size

        # 更新峰值
        stats_dict[key]['peakMem'] = max(stats_dict[key]['peakMem'], cumulative_dict[key])

        # 累加用于计算平均值
        sum_dict[key] += cumulative_dict[key]
        count_dict[key] += 1

        # 更新事件计数
        stats_dict[key]['eventNum'] += 1

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
