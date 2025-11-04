"""
内存数据聚合器

负责对内存记录进行多维度聚合，生成前端需要的统计数据
"""

from collections import defaultdict
from typing import Any


class MemoryAggregator:
    """内存数据聚合器

    对内存记录进行多维度聚合：
    - 按进程聚合
    - 按线程聚合
    - 按文件聚合
    - 按符号聚合
    - 按组件分类聚合
    - 按事件类型聚合
    """

    def __init__(self):
        pass

    def aggregate_all(self, records: list[dict[str, Any]], time: int | None = None) -> dict[str, Any]:
        """对记录进行所有维度的聚合

        Args:
            records: 内存记录列表
            time: 仅聚合 relativeTs <= time 的记录（毫秒/微秒，取决于记录单位）

        Returns:
            包含所有聚合结果的字典
        """
        # 可选的时间过滤
        if time is not None:
            records = [r for r in records if r.get('relativeTs', 0) <= time]

        if not records:
            return {
                'by_process': [],
                'by_thread': [],
                'by_file': [],
                'by_symbol': [],
                'by_component': [],
                'by_file_category': [],
                'by_symbol_category': [],
                'by_event_type': [],
            }

        return {
            'by_process': self._aggregate_by_process(records),
            'by_thread': self._aggregate_by_thread(records),
            'by_file': self._aggregate_by_file(records),
            'by_symbol': self._aggregate_by_symbol(records),
            'by_component': self._aggregate_by_component(records),
            'by_file_category': self._aggregate_by_file_category(records),
            'by_symbol_category': self._aggregate_by_symbol_category(records),
            'by_event_type': self._aggregate_by_event_type(records),
        }

    def get_unreleased_by_callchain(self, records: list[dict[str, Any]], time: int) -> dict[int, dict[str, Any]]:
        """在给定时间点返回未释放地址信息，并按 callchain_id 聚合

        Args:
            records: 平铺后的内存记录（由 MemoryRecordGenerator 生成）
            time: 仅统计 relativeTs <= time 的记录

        Returns:
            { callchainId: { 'totalBytes': int, 'allocs': [ ...未释放分配详情... ] } }
        """
        if not records:
            return {}

        # 仅处理截止到 time 的事件，并按时间升序
        filtered = [r for r in records if r.get('relativeTs', 0) <= time]
        if not filtered:
            return {}

        filtered.sort(key=lambda r: r.get('relativeTs', 0))

        # 地址 -> 活跃分配栈（LIFO），用于处理可能的重复地址/部分释放
        addr_to_active_allocs: dict[int, list[dict[str, Any]]] = defaultdict(list)

        def is_alloc(evt_type: Any) -> bool:
            return evt_type in ('AllocEvent', 'MmapEvent', 0)

        def is_free(evt_type: Any) -> bool:
            return evt_type in ('FreeEvent', 'MunmapEvent', 1)

        for rec in filtered:
            addr = rec.get('addr')
            if addr is None:
                continue

            evt_type = rec.get('eventType')
            size = rec.get('heapSize') or 0

            # 忽略异常数据
            if not size:
                continue

            if is_alloc(evt_type):
                # 记录一次分配作为活跃块，后续 free 按 LIFO 消耗
                active = {
                    'addr': addr,
                    'size': size,  # 剩余未释放大小（初始化为分配大小）
                    'pid': rec.get('pid'),
                    'process': rec.get('process'),
                    'tid': rec.get('tid'),
                    'thread': rec.get('thread'),
                    'fileId': rec.get('fileId'),
                    'file': rec.get('file'),
                    'symbolId': rec.get('symbolId'),
                    'symbol': rec.get('symbol'),
                    'callchainId': rec.get('callchainId'),
                    'relativeTs': rec.get('relativeTs'),
                    'componentCategory': rec.get('componentCategory'),
                    'categoryName': rec.get('categoryName'),
                    'subCategoryName': rec.get('subCategoryName'),
                }
                addr_to_active_allocs[addr].append(active)
            elif is_free(evt_type):
                # 释放：按 LIFO 从该地址的活跃分配中扣减
                remaining = size
                stack = addr_to_active_allocs.get(addr)
                if not stack:
                    continue

                while remaining > 0 and stack:
                    top = stack[-1]
                    if top['size'] > remaining:
                        top['size'] -= remaining
                        remaining = 0
                    else:
                        remaining -= top['size']
                        stack.pop()
                # 如果该地址已完全释放，清理空列表
                if not stack:
                    addr_to_active_allocs.pop(addr, None)

        # 聚合：按分配时的 callchainId 汇总
        result: dict[int, dict[str, Any]] = {}

        for allocs in addr_to_active_allocs.values():
            for alloc in allocs:
                if alloc['size'] <= 0:
                    continue
                callchain_id = alloc.get('callchainId')
                if callchain_id is None:
                    continue
                group = result.setdefault(callchain_id, {'totalBytes': 0, 'allocs': []})
                group['totalBytes'] += alloc['size']
                group['allocs'].append(alloc)

        # 在同一 callchainId 下按 (pid, tid) 聚合：
        # - 去除 addr 字段
        # - 新增 count 统计次数
        # - size 汇总
        # - relativeTs 取最小（最早出现）
        for callchain_id, group in result.items():
            merged: dict[tuple[int, int], dict[str, Any]] = {}
            for alloc in group['allocs']:
                pid = alloc.get('pid')
                tid = alloc.get('tid')
                key = (pid, tid)
                existing = merged.get(key)
                if existing is None:
                    merged[key] = {
                        # 基础标识
                        'pid': pid,
                        'process': alloc.get('process'),
                        'tid': tid,
                        'thread': alloc.get('thread'),
                        'fileId': alloc.get('fileId'),
                        'file': alloc.get('file'),
                        'symbolId': alloc.get('symbolId'),
                        'symbol': alloc.get('symbol'),
                        'callchainId': callchain_id,
                        'relativeTs': alloc.get('relativeTs'),
                        'componentCategory': alloc.get('componentCategory'),
                        'categoryName': alloc.get('categoryName'),
                        'subCategoryName': alloc.get('subCategoryName'),
                        # 聚合指标
                        'size': alloc.get('size', 0),
                        'count': 1,
                    }
                else:
                    existing['size'] = (existing.get('size') or 0) + (alloc.get('size') or 0)
                    existing['count'] = (existing.get('count') or 0) + 1
                    # relativeTs 取最早
                    rts = alloc.get('relativeTs')
                    if rts is not None and (existing.get('relativeTs') is None or rts < existing.get('relativeTs')):
                        existing['relativeTs'] = rts

            # 回写合并后的列表，并按 size 降序
            merged_list = list(merged.values())
            merged_list.sort(key=lambda a: a.get('size', 0), reverse=True)
            group['allocs'] = merged_list
            # totalBytes 按合并后 size 汇总，避免与原列表不一致
            group['totalBytes'] = sum(a.get('size', 0) for a in merged_list)

        return result

    def _aggregate_by_process(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """按进程聚合"""
        process_map = defaultdict(list)

        for record in records:
            pid = record.get('pid', 0)
            process_name = record.get('process', f'Process {pid}')
            # 使用元组作为key，避免字符串拼接导致的解析问题
            key = (pid, process_name)
            process_map[key].append(record)

        result = []
        for (pid, process_name), group_records in process_map.items():
            stats = self._calculate_stats(group_records)
            result.append(
                {
                    'pid': pid,
                    'process': process_name,
                    **stats,
                }
            )

        # 按峰值内存排序
        result.sort(key=lambda x: x['peakMem'], reverse=True)
        return result

    def _aggregate_by_thread(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """按线程聚合"""
        thread_map = defaultdict(list)

        for record in records:
            tid = record.get('tid', 0)
            thread_name = record.get('thread', f'Thread {tid}')
            pid = record.get('pid', 0)
            # 使用元组作为key
            key = (pid, tid, thread_name)
            thread_map[key].append(record)

        result = []
        for (pid, tid, thread_name), group_records in thread_map.items():
            stats = self._calculate_stats(group_records)
            result.append(
                {
                    'pid': pid,
                    'tid': tid,
                    'thread': thread_name,
                    **stats,
                }
            )

        # 按峰值内存排序
        result.sort(key=lambda x: x['peakMem'], reverse=True)
        return result

    def _aggregate_by_file(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """按文件聚合"""
        file_map = defaultdict(list)

        for record in records:
            file_id = record.get('fileId', 0)
            file_path = record.get('file', 'unknown')
            # 使用元组作为key
            key = (file_id, file_path)
            file_map[key].append(record)

        result = []
        for (file_id, file_path), group_records in file_map.items():
            stats = self._calculate_stats(group_records)
            result.append(
                {
                    'fileId': file_id,
                    'file': file_path,
                    **stats,
                }
            )

        # 按峰值内存排序
        result.sort(key=lambda x: x['peakMem'], reverse=True)
        return result

    def _aggregate_by_symbol(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """按符号聚合"""
        symbol_map = defaultdict(list)

        for record in records:
            symbol_id = record.get('symbolId', 0)
            symbol_name = record.get('symbol', 'unknown')
            # 使用元组作为key
            key = (symbol_id, symbol_name)
            symbol_map[key].append(record)

        result = []
        for (symbol_id, symbol_name), group_records in symbol_map.items():
            stats = self._calculate_stats(group_records)
            result.append(
                {
                    'symbolId': symbol_id,
                    'symbol': symbol_name,
                    **stats,
                }
            )

        # 按峰值内存排序
        result.sort(key=lambda x: x['peakMem'], reverse=True)
        return result

    def _aggregate_by_component(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """按组件分类聚合"""
        component_map = defaultdict(list)

        for record in records:
            category = record.get('componentCategory', -1)
            category_name = record.get('categoryName', 'UNKNOWN')
            sub_category = record.get('subCategoryName', 'Unknown')
            # 使用元组作为key
            key = (category, category_name, sub_category)
            component_map[key].append(record)

        result = []
        for (category, category_name, sub_category), group_records in component_map.items():
            stats = self._calculate_stats(group_records)
            result.append(
                {
                    'componentCategory': category,
                    'categoryName': category_name,
                    'subCategoryName': sub_category,
                    **stats,
                }
            )

        # 按峰值内存排序
        result.sort(key=lambda x: x['peakMem'], reverse=True)
        return result

    def _aggregate_by_file_category(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """按文件+分类聚合"""
        file_category_map = defaultdict(list)

        for record in records:
            file_id = record.get('fileId', 0)
            file_path = record.get('file', 'unknown')
            category = record.get('componentCategory', -1)
            category_name = record.get('categoryName', 'UNKNOWN')
            sub_category = record.get('subCategoryName', 'Unknown')
            # 使用元组作为key
            key = (file_id, file_path, category, category_name, sub_category)
            file_category_map[key].append(record)

        result = []
        for (file_id, file_path, category, category_name, sub_category), group_records in file_category_map.items():
            stats = self._calculate_stats(group_records)
            result.append(
                {
                    'fileId': file_id,
                    'file': file_path,
                    'componentCategory': category,
                    'categoryName': category_name,
                    'subCategoryName': sub_category,
                    **stats,
                }
            )

        # 按峰值内存排序
        result.sort(key=lambda x: x['peakMem'], reverse=True)
        return result

    def _aggregate_by_symbol_category(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """按符号+分类聚合"""
        symbol_category_map = defaultdict(list)

        for record in records:
            symbol_id = record.get('symbolId', 0)
            symbol_name = record.get('symbol', 'unknown')
            category = record.get('componentCategory', -1)
            category_name = record.get('categoryName', 'UNKNOWN')
            sub_category = record.get('subCategoryName', 'Unknown')
            # 使用元组作为key
            key = (symbol_id, symbol_name, category, category_name, sub_category)
            symbol_category_map[key].append(record)

        result = []
        for (
            symbol_id,
            symbol_name,
            category,
            category_name,
            sub_category,
        ), group_records in symbol_category_map.items():
            stats = self._calculate_stats(group_records)
            result.append(
                {
                    'symbolId': symbol_id,
                    'symbol': symbol_name,
                    'componentCategory': category,
                    'categoryName': category_name,
                    'subCategoryName': sub_category,
                    **stats,
                }
            )

        # 按峰值内存排序
        result.sort(key=lambda x: x['peakMem'], reverse=True)
        return result

    def _aggregate_by_event_type(self, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """按事件类型聚合"""
        event_type_map = defaultdict(list)

        for record in records:
            event_type = record.get('eventType', 'Unknown')
            sub_event_type = record.get('subEventType', '')

            # 合并 AllocEvent 和 FreeEvent
            if event_type in ('AllocEvent', 'FreeEvent'):
                key = 'AllocEvent'
            elif event_type in ('MmapEvent', 'MunmapEvent'):
                # 如果有 subEventType，使用它；否则使用 'Other MmapEvent'
                key = sub_event_type if sub_event_type else 'Other MmapEvent'
            else:
                key = event_type

            event_type_map[key].append(record)

        result = []
        for event_type, group_records in event_type_map.items():
            stats = self._calculate_stats(group_records)

            result.append(
                {
                    'eventType': event_type,
                    **stats,
                }
            )

        # 按峰值内存排序
        result.sort(key=lambda x: x['peakMem'], reverse=True)
        return result

    def _calculate_stats(self, records: list[dict[str, Any]]) -> dict[str, Any]:
        """计算统计信息

        Args:
            records: 记录列表

        Returns:
            统计信息字典
        """
        if not records:
            return {
                'peakMem': 0,
                'avgMem': 0,
                'totalAllocMem': 0,
                'totalFreeMem': 0,
                'eventNum': 0,
                'start_ts': 0,
            }

        # 按时间排序
        sorted_records = sorted(records, key=lambda r: r.get('relativeTs', 0))

        # 计算当前内存和统计信息
        current_mem = 0
        peak_mem = 0
        total_alloc = 0
        total_free = 0
        mem_sum = 0

        for record in sorted_records:
            heap_size = record.get('heapSize', 0)

            # 更新当前内存
            current_mem += heap_size

            # 更新峰值
            peak_mem = max(peak_mem, current_mem)

            # 统计分配和释放
            if heap_size > 0:
                total_alloc += heap_size
            else:
                total_free += abs(heap_size)

            # 累加用于计算平均值
            mem_sum += current_mem

        # 计算平均内存
        avg_mem = mem_sum / len(sorted_records) if sorted_records else 0

        return {
            'peakMem': peak_mem,
            'avgMem': int(avg_mem),
            'totalAllocMem': total_alloc,
            'totalFreeMem': total_free,
            'eventNum': len(sorted_records),
            'start_ts': sorted_records[0].get('relativeTs', 0) if sorted_records else 0,
        }
