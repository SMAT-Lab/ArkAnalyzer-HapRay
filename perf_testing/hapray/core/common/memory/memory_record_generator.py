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
import sqlite3
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Optional

from .callchain_refiner import CallchainRefiner
from .memory_classifier import MemoryClassifier
from .memory_data_loader import MemoryDataLoader


class MemoryRecordGenerator:
    """内存记录生成器

    负责将原始事件数据转换为前端可用的记录格式
    """

    def __init__(self, classifier: MemoryClassifier, use_refined_lib_symbol: bool = False):
        """初始化记录生成器

        Args:
            classifier: 内存分类器实例
            use_refined_lib_symbol: 是否使用refined的lib_id和symbol_id，默认使用原始值
        """
        self.classifier = classifier
        self.use_refined_lib_symbol = use_refined_lib_symbol
        self.callchain_refiner = CallchainRefiner()
        self.db_conn: Optional[sqlite3.Connection] = None
        self.callchain_cache: dict[int, list[dict]] = {}
        self.refined_callchain_cache: dict[int, tuple[Optional[int], Optional[int]]] = {}

    def set_db_connection(self, db_conn: sqlite3.Connection):
        """设置数据库连接，用于查询callchain

        Args:
            db_conn: SQLite数据库连接
        """
        self.db_conn = db_conn

    def _preload_and_refine_callchains(
        self, events: list[dict], data_dict: dict[int, str], max_workers: int = 8
    ) -> dict[int, tuple[Optional[int], Optional[int]]]:
        """预加载并批量精化所有callchain

        一次性加载所有callchain数据到内存，然后使用多线程并行精化

        Args:
            events: 事件列表
            data_dict: 数据字典
            max_workers: 线程池大小

        Returns:
            callchain_id -> (refined_lib_id, refined_symbol_id) 的映射
        """
        if not self.use_refined_lib_symbol or not self.db_conn:
            return {}

        # 收集所有唯一的callchain_id
        unique_callchain_ids = set()
        for event in events:
            callchain_id = event.get('callchain_id')
            if callchain_id and callchain_id > 0:
                unique_callchain_ids.add(callchain_id)

        if not unique_callchain_ids:
            logging.info('No callchains to refine')
            return {}

        logging.info('Preloading and refining %d unique callchains with %d workers',
                     len(unique_callchain_ids), max_workers)

        # 一次性加载所有callchain数据到内存
        try:
            all_frames = MemoryDataLoader.query_all_callchain(self.db_conn)
            logging.info('Loaded %d total frames from database', len(all_frames))

            # 按callchain_id分组
            callchain_frames_map: dict[int, list[dict]] = defaultdict(list)
            for frame in all_frames:
                callchain_id = frame['callchain_id']
                if callchain_id in unique_callchain_ids:
                    callchain_frames_map[callchain_id].append(frame)

            logging.info('Grouped frames into %d callchains', len(callchain_frames_map))

            # 同时填充 callchain_cache，供后续导出使用
            self.callchain_cache.update(callchain_frames_map)
            logging.info('Updated callchain_cache with %d callchains', len(callchain_frames_map))
        except Exception as e:
            logging.error('Failed to preload callchains: %s', str(e))
            return {}

        refined_results = {}

        def refine_single_callchain(callchain_id: int) -> tuple[int, tuple[Optional[int], Optional[int]]]:
            """精化单个callchain - 使用预加载的数据"""
            try:
                frames = callchain_frames_map.get(callchain_id, [])
                if not frames:
                    return callchain_id, (None, None)

                refined_lib_id, refined_symbol_id, _, _ = self.callchain_refiner.refine_callchain(frames, data_dict)
                return callchain_id, (refined_lib_id, refined_symbol_id)
            except Exception as e:
                logging.warning('Failed to refine callchain %d: %s', callchain_id, str(e))
                return callchain_id, (None, None)

        # 使用线程池并行精化
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(refine_single_callchain, cid): cid
                for cid in unique_callchain_ids
            }

            completed = 0
            for future in as_completed(futures):
                try:
                    callchain_id, result = future.result()
                    refined_results[callchain_id] = result
                    completed += 1
                    if completed % 1000 == 0:
                        logging.debug('Refined %d/%d callchains', completed, len(unique_callchain_ids))
                except Exception as e:
                    logging.warning('Error processing callchain: %s', str(e))

        logging.info('Completed refining %d callchains', len(refined_results))
        return refined_results

    def _get_refined_lib_symbol(
        self, callchain_id: int, original_lib_id: Optional[int], original_symbol_id: Optional[int], data_dict: dict[int, str]
    ) -> tuple[Optional[int], Optional[int]]:
        """获取refined的lib_id和symbol_id

        Args:
            callchain_id: 调用链ID
            original_lib_id: 原始的lib_id
            original_symbol_id: 原始的symbol_id
            data_dict: 数据字典

        Returns:
            元组 (refined_lib_id, refined_symbol_id)
        """
        if not self.use_refined_lib_symbol or not self.db_conn or callchain_id <= 0:
            return original_lib_id, original_symbol_id

        # 检查缓存
        if callchain_id not in self.callchain_cache:
            try:
                frames = MemoryDataLoader.query_callchain_by_id(self.db_conn, callchain_id)
                self.callchain_cache[callchain_id] = frames
                if frames:
                    logging.debug('Queried callchain %d: %d frames', callchain_id, len(frames))
            except Exception as e:
                logging.warning('Failed to query callchain %d: %s', callchain_id, str(e))
                return original_lib_id, original_symbol_id

        frames = self.callchain_cache.get(callchain_id, [])
        if not frames:
            return original_lib_id, original_symbol_id

        refined_lib_id, refined_symbol_id, _, _ = self.callchain_refiner.refine_callchain(frames, data_dict)

        if refined_lib_id != original_lib_id or refined_symbol_id != original_symbol_id:
            logging.debug(
                'Refined callchain %d: lib %d->%d, symbol %d->%d',
                callchain_id,
                original_lib_id,
                refined_lib_id,
                original_symbol_id,
                refined_symbol_id,
            )

        return refined_lib_id or original_lib_id, refined_symbol_id or original_symbol_id

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
        # 预加载并精化所有callchain（如果启用了refined模式）
        if self.use_refined_lib_symbol and self.db_conn:
            logging.info('Preloading callchains for refinement...')
            self.refined_callchain_cache = self._preload_and_refine_callchains(events, data_dict)
        else:
            self.refined_callchain_cache = {}

        return self._generate_records_internal(events, processes, threads, data_dict, trace_start_ts)

    def _generate_records_internal(
        self,
        events: list[dict],
        processes: list[dict],
        threads: list[dict],
        data_dict: dict[int, str],
        trace_start_ts: int,
    ) -> dict[str, Any]:
        """内部方法：生成平铺的内存记录（不进行预加载）

        Args:
            events: 事件列表
            processes: 进程列表
            threads: 线程列表
            data_dict: 数据字典（符号和文件名）
            trace_start_ts: Trace 起始时间戳

        Returns:
            内存记录列表
        """

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

            # 获取原始的文件信息 - 直接从 data_dict 表中查询
            last_lib_id = event.get('last_lib_id')
            if last_lib_id is not None and last_lib_id > 0:
                file_id = last_lib_id
                file_path = data_dict.get(last_lib_id, 'unknown')

            # 获取原始的符号信息 - 直接从 data_dict 表中查询
            last_symbol_id = event.get('last_symbol_id')
            if last_symbol_id is not None and last_symbol_id > 0:
                symbol_id = last_symbol_id
                symbol_name = data_dict.get(last_symbol_id, 'unknown')

            # 如果启用了refined模式，尝试从预加载的缓存中获取更准确的lib_id和symbol_id
            if self.use_refined_lib_symbol:
                callchain_id = event.get('callchain_id')
                if callchain_id and callchain_id > 0 and callchain_id in self.refined_callchain_cache:
                    # 使用预加载的精化结果
                    refined_lib_id, refined_symbol_id = self.refined_callchain_cache[callchain_id]
                    if refined_lib_id is not None or refined_symbol_id is not None:
                        logging.debug(
                            'Using cached refined result for callchain %d: lib %s->%s, symbol %s->%s',
                            callchain_id, file_id, refined_lib_id, symbol_id, refined_symbol_id
                        )
                else:
                    # 回退到单个查询（用于缓存未命中的情况）
                    refined_lib_id, refined_symbol_id = self._get_refined_lib_symbol(
                        callchain_id, file_id, symbol_id, data_dict
                    )

                if refined_lib_id is not None and refined_lib_id > 0:
                    file_id = refined_lib_id
                    file_path = data_dict.get(refined_lib_id, 'unknown')
                if refined_symbol_id is not None and refined_symbol_id > 0:
                    symbol_id = refined_symbol_id
                    symbol_name = data_dict.get(refined_symbol_id, 'unknown')

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

            # 获取原始内存大小
            heap_size = event.get('heap_size') or 0
            # heapSize 存储规则：申请内存为正数，释放内存为负数
            heap_size = -abs(heap_size) if is_free else abs(heap_size)

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
                # 内存大小（申请为正数，释放为负数）
                'heapSize': heap_size,
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

            # 计算累计内存变化（heapSize 已经是正负数形式）
            current_total += heap_size

            if current_total > peak_value:
                peak_value = current_total
                peak_time = event.get('start_ts', 0) - trace_start_ts

        logging.info('Generated %d memory records', len(records))
        return {
            'records': records,
            'peak_value': peak_value,
            'peak_time': peak_time,
        }

    def generate_records_with_original(
        self,
        events: list[dict],
        processes: list[dict],
        threads: list[dict],
        data_dict: dict[int, str],
        trace_start_ts: int,
    ) -> dict[str, Any]:
        """生成原始值和refined值的内存记录对比

        返回包含原始值和refined值两个版本的记录，用于对比导出

        Args:
            events: 事件列表
            processes: 进程列表
            threads: 线程列表
            data_dict: 数据字典（符号和文件名）
            trace_start_ts: Trace 起始时间戳

        Returns:
            包含 'original_records' 和 'refined_records' 的字典
        """
        logging.info('Generating records with original and refined values for comparison')

        # 预加载所有callchain一次（如果启用了refined模式）
        if self.use_refined_lib_symbol and self.db_conn:
            logging.info('Preloading callchains for refinement (shared for both original and refined)...')
            self.refined_callchain_cache = self._preload_and_refine_callchains(events, data_dict)
        else:
            self.refined_callchain_cache = {}

        # 临时禁用refined模式，生成原始值记录
        original_use_refined = self.use_refined_lib_symbol
        self.use_refined_lib_symbol = False
        logging.info('Generating original records (refined mode disabled)')
        original_result = self._generate_records_internal(events, processes, threads, data_dict, trace_start_ts)
        original_records = original_result['records']

        # 恢复refined模式，生成refined值记录
        self.use_refined_lib_symbol = original_use_refined
        logging.info('Generating refined records (refined mode enabled)')
        refined_result = self._generate_records_internal(events, processes, threads, data_dict, trace_start_ts)
        refined_records = refined_result['records']

        logging.info('Generated %d original records and %d refined records for comparison',
                     len(original_records), len(refined_records))

        return {
            'original_records': original_records,
            'refined_records': refined_records,
            'peak_value': refined_result['peak_value'],
            'peak_time': refined_result['peak_time'],
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
