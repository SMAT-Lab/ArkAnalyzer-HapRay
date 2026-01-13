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
from typing import Any, Optional

from .callchain_refiner import CallchainRefiner
from .memory_classifier import MemoryClassifier
from .memory_data_loader import MemoryDataLoader


class MemoryStatisticRecordGenerator:
    """内存统计记录生成器

    专门用于将 native_hook_statistic 的聚合统计数据转换为 memory_records 格式
    核心逻辑：将统计数据展开为多条明细记录
    """

    def __init__(self, classifier: MemoryClassifier, use_refined_lib_symbol: bool = False):
        """初始化统计记录生成器

        Args:
            classifier: 内存分类器实例
            use_refined_lib_symbol: 是否使用refined的lib_id和symbol_id
        """
        self.classifier = classifier
        self.use_refined_lib_symbol = use_refined_lib_symbol
        self.callchain_refiner = CallchainRefiner()
        self.db_conn: Optional[sqlite3.Connection] = None
        self.refined_callchain_cache: dict[int, tuple[Optional[int], Optional[int]]] = {}

    def set_db_connection(self, db_conn: sqlite3.Connection):
        """设置数据库连接，用于查询callchain

        Args:
            db_conn: SQLite数据库连接
        """
        self.db_conn = db_conn

    def _preload_and_refine_callchains(
        self, statistic_events: list[dict], data_dict: dict[int, str]
    ) -> dict[int, tuple[Optional[int], Optional[int]]]:
        """预加载并批量精化所有callchain（用于统计数据）

        Args:
            statistic_events: 统计事件列表
            data_dict: 数据字典

        Returns:
            callchain_id -> (refined_lib_id, refined_symbol_id) 的映射
        """
        if not self.use_refined_lib_symbol or not self.db_conn:
            return {}

        # 收集所有唯一的callchain_id
        unique_callchain_ids = set()
        for event in statistic_events:
            callchain_id = event.get('callchain_id')
            if callchain_id and callchain_id > 0:
                unique_callchain_ids.add(callchain_id)

        if not unique_callchain_ids:
            logging.info('No callchains to refine in statistic data')
            return {}

        logging.info('Refining %d unique callchains from statistic data', len(unique_callchain_ids))

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
        except Exception as e:
            logging.error('Failed to preload callchains: %s', str(e))
            return {}

        refined_results = {}

        # 精化每个callchain
        for callchain_id in unique_callchain_ids:
            try:
                frames = callchain_frames_map.get(callchain_id, [])
                if not frames:
                    refined_results[callchain_id] = (None, None)
                    continue

                refined_lib_id, refined_symbol_id, _, _ = self.callchain_refiner.refine_callchain(frames, data_dict)
                refined_results[callchain_id] = (refined_lib_id, refined_symbol_id)
            except Exception as e:
                logging.warning('Failed to refine callchain %d: %s', callchain_id, str(e))
                refined_results[callchain_id] = (None, None)

        logging.info('Completed refining %d callchains', len(refined_results))
        return refined_results

    def _get_refined_lib_symbol(
        self,
        callchain_id: int,
        original_lib_id: Optional[int],
        original_symbol_id: Optional[int],
        data_dict: dict[int, str],
    ) -> tuple[Optional[int], Optional[int]]:
        """获取refined的lib_id和symbol_id

        Args:
            callchain_id: 调用链ID
            original_lib_id: 原始lib_id
            original_symbol_id: 原始symbol_id
            data_dict: 数据字典

        Returns:
            (refined_lib_id, refined_symbol_id)
        """
        if not self.use_refined_lib_symbol:
            return original_lib_id, original_symbol_id

        # 从缓存中获取
        if callchain_id in self.refined_callchain_cache:
            return self.refined_callchain_cache[callchain_id]

        # 如果没有数据库连接，返回原始值
        if not self.db_conn:
            logging.warning('No db connection for refined mode, using original values')
            return original_lib_id, original_symbol_id

        # 查询并精化callchain
        try:
            frames = MemoryDataLoader.query_callchain_by_id(self.db_conn, callchain_id)
            if not frames:
                self.refined_callchain_cache[callchain_id] = (None, None)
                return None, None

            refined_lib_id, refined_symbol_id, _, _ = self.callchain_refiner.refine_callchain(frames, data_dict)
            self.refined_callchain_cache[callchain_id] = (refined_lib_id, refined_symbol_id)
            return refined_lib_id, refined_symbol_id
        except Exception as e:
            logging.warning('Failed to refine callchain %d: %s', callchain_id, str(e))
            self.refined_callchain_cache[callchain_id] = (None, None)
            return None, None

    def generate_records_from_statistic(
        self,
        statistic_events: list[dict],
        processes: list[dict],
        threads: list[dict],
        data_dict: dict[int, str],
        trace_start_ts: int,
        sub_type_names: Optional[dict[int, str]] = None,
    ) -> dict[str, Any]:
        """从 native_hook_statistic 统计数据生成 memory_records

        native_hook_statistic 表记录的是统计快照，每条记录包含：
        - apply_size: 总申请大小
        - release_size: 总释放大小

        直接使用这些统计值生成记录，不需要展开：
        - 如果 apply_size > 0，生成1条 AllocEvent 记录
        - 如果 release_size > 0，生成1条 FreeEvent 记录

        Args:
            statistic_events: 统计事件列表
            processes: 进程列表
            threads: 线程列表（统计数据中无法使用，保留参数以保持接口一致）
            data_dict: 数据字典
            trace_start_ts: Trace 起始时间戳
            sub_type_names: sub_type_id 到名称的映射字典

        Returns:
            包含 records、peak_value、peak_time 的字典
        """
        process_map = {p['ipid']: p for p in processes}

        if sub_type_names is None:
            sub_type_names = {}

        # 如果启用了refined模式，预加载并精化所有callchain
        if self.use_refined_lib_symbol and self.db_conn:
            logging.info('Preloading and refining callchains for statistic data (refined mode)')
            self.refined_callchain_cache = self._preload_and_refine_callchains(statistic_events, data_dict)

        records = []
        current_total = 0
        peak_value = 0
        peak_time = 0

        logging.info('开始从 %d 条统计记录生成内存记录...', len(statistic_events))

        for stat_event in statistic_events:
            # 获取进程信息
            process = process_map.get(stat_event['ipid'])
            if not process:
                continue

            # 获取进程名，如果为空则使用 pid（真实进程ID）
            process_name = process.get('name')
            if not process_name:
                # 优先使用真实的 pid，如果 pid 也为空则使用 ipid
                pid = process.get('pid')
                process_name = str(pid) if pid else f'ipid_{stat_event["ipid"]}'

            # 获取原始文件和符号信息
            original_lib_id = stat_event.get('last_lib_id')
            original_symbol_id = stat_event.get('last_symbol_id')
            callchain_id = stat_event.get('callchain_id', 0)

            # 根据模式选择使用原始值还是refined值
            if self.use_refined_lib_symbol and callchain_id > 0:
                file_id, symbol_id = self._get_refined_lib_symbol(
                    callchain_id, original_lib_id, original_symbol_id, data_dict
                )
            else:
                file_id = original_lib_id
                symbol_id = original_symbol_id

            file_path = data_dict.get(file_id, 'unknown') if file_id and file_id > 0 else None
            symbol_name = data_dict.get(symbol_id, 'unknown') if symbol_id and symbol_id > 0 else None

            # 分类
            classification = self.classifier.get_final_classification(
                file_path=file_path,
                symbol_name=symbol_name,
                thread_name=None,
            )

            # 获取 sub_event_type
            sub_type_id = stat_event.get('sub_type_id')
            sub_event_type = sub_type_names.get(sub_type_id, '') if sub_type_id else ''

            # 相对时间戳
            relative_ts = stat_event['ts'] - trace_start_ts

            # 生成分配记录（如果有申请）
            apply_size = stat_event.get('apply_size', 0)
            if apply_size > 0:
                record = {
                    'pid': process['pid'],
                    'process': process_name,
                    'tid': 0,
                    'thread': 'unknown',
                    'fileId': file_id if file_id and file_id > 0 else None,
                    'file': file_path,
                    'symbolId': symbol_id if symbol_id and symbol_id > 0 else None,
                    'symbol': symbol_name,
                    'eventType': 'AllocEvent',
                    'subEventType': sub_event_type,
                    'addr': 0,
                    'callchainId': callchain_id,
                    'heapSize': apply_size,  # 直接使用总申请大小
                    'relativeTs': relative_ts,
                    'componentName': classification['sub_category_name'],
                    'componentCategory': classification['category'],
                    'categoryName': classification['category_name'],
                    'subCategoryName': classification['sub_category_name'],
                }
                records.append(record)
                current_total += apply_size

                if current_total > peak_value:
                    peak_value = current_total
                    peak_time = relative_ts

            # 生成释放记录（如果有释放）
            release_size = stat_event.get('release_size', 0)
            if release_size > 0:
                record = {
                    'pid': process['pid'],
                    'process': process_name,
                    'tid': 0,
                    'thread': 'unknown',
                    'fileId': file_id if file_id and file_id > 0 else None,
                    'file': file_path,
                    'symbolId': symbol_id if symbol_id and symbol_id > 0 else None,
                    'symbol': symbol_name,
                    'eventType': 'FreeEvent',
                    'subEventType': sub_event_type,
                    'addr': 0,
                    'callchainId': callchain_id,
                    'heapSize': -release_size,  # 直接使用总释放大小（负数）
                    'relativeTs': relative_ts,
                    'componentName': classification['sub_category_name'],
                    'componentCategory': classification['category'],
                    'categoryName': classification['category_name'],
                    'subCategoryName': classification['sub_category_name'],
                }
                records.append(record)
                current_total -= release_size

                if current_total > peak_value:
                    peak_value = current_total
                    peak_time = relative_ts

        mode_info = 'refined mode' if self.use_refined_lib_symbol else 'original mode'
        logging.info(
            '✓ 从 %d 条统计记录生成 %d 条内存记录（峰值: %d bytes @ %d ns）[%s]',
            len(statistic_events),
            len(records),
            peak_value,
            peak_time,
            mode_info,
        )

        return {
            'records': records,
            'peak_value': peak_value,
            'peak_time': peak_time,
        }
