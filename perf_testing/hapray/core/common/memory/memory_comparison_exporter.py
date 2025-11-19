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

import pandas as pd


class MemoryComparisonExporter:
    """内存分析对比导出器

    用于导出默认值vs refined值的对比Excel，展示两种方式的差异
    """

    def __init__(self):
        """初始化对比导出器"""
        pass

    def export_comparison(
        self,
        output_path: str,
        original_records: list[dict],
        refined_records: list[dict],
        data_dict: dict[int, str],
        callchain_cache: dict[int, list[dict]],
    ):
        """导出对比Excel

        Args:
            output_path: 输出文件路径
            original_records: 使用原始值的记录列表
            refined_records: 使用refined值的记录列表
            data_dict: 数据字典
            callchain_cache: 已缓存的调用链数据
        """
        try:
            os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)

            with pd.ExcelWriter(output_path, engine='xlsxwriter') as writer:
                # 创建对比数据
                comparison_data = self._create_comparison_data(
                    original_records, refined_records, data_dict
                )

                # 写入对比数据
                if comparison_data:
                    df = pd.DataFrame(comparison_data)
                    df.to_excel(writer, sheet_name='Comparison', index=False)

                    # 设置列宽
                    ws = writer.sheets['Comparison']
                    ws.set_column(0, len(df.columns) - 1, 20)

                    # 创建修改过的调用链数据
                    callchain_data = self._create_modified_callchain_data(
                        comparison_data, data_dict, callchain_cache
                    )

                    # 写入调用链数据
                    if callchain_data:
                        df_callchain = pd.DataFrame(callchain_data)
                        df_callchain.to_excel(writer, sheet_name='ModifiedCallchains', index=False)

                        # 设置列宽
                        ws_callchain = writer.sheets['ModifiedCallchains']
                        ws_callchain.set_column(0, len(df_callchain.columns) - 1, 15)

                        logging.info('Modified callchain data exported (%d frames)', len(callchain_data))
                    else:
                        logging.info('No modified callchain data to export')

                    logging.info('Comparison data exported to %s', output_path)
                else:
                    # 没有对比数据时，创建一个提示信息表
                    logging.warning('No comparison data to export (original_records=%d, refined_records=%d)',
                                    len(original_records), len(refined_records))

                    # 创建一个提示信息表
                    info_data = [
                        {
                            'Status': 'No Data',
                            'Message': 'No native_hook events found in the trace database',
                            'OriginalRecords': len(original_records),
                            'RefinedRecords': len(refined_records),
                        }
                    ]
                    df_info = pd.DataFrame(info_data)
                    df_info.to_excel(writer, sheet_name='Info', index=False)

                    ws = writer.sheets['Info']
                    ws.set_column(0, len(df_info.columns) - 1, 30)

        except Exception as e:
            logging.error('Failed to export comparison: %s', str(e))

    def _create_comparison_data(
        self,
        original_records: list[dict],
        refined_records: list[dict],
        data_dict: dict[int, str],
    ) -> list[dict]:
        """创建对比数据 - 基于事件级别的对比

        按照 (pid, tid, addr, callchainId) 作为事件的唯一标识，对比同一个事件的
        原始值和精化值的 last_lib_id 和 last_symbol_id

        Args:
            original_records: 原始记录列表
            refined_records: refined记录列表
            data_dict: 数据字典

        Returns:
            对比数据列表
        """
        comparison_rows = []

        # 按事件唯一标识分组：(pid, tid, addr, callchainId)
        def get_event_key(record):
            return (
                record.get('pid'),
                record.get('tid'),
                record.get('addr'),
                record.get('callchainId'),
            )

        original_by_event = {}
        for record in original_records:
            key = get_event_key(record)
            if key not in original_by_event:
                original_by_event[key] = []
            original_by_event[key].append(record)

        refined_by_event = {}
        for record in refined_records:
            key = get_event_key(record)
            if key not in refined_by_event:
                refined_by_event[key] = []
            refined_by_event[key].append(record)

        # 对比每个事件
        all_events = set(original_by_event.keys()) | set(refined_by_event.keys())

        for event_key in sorted(all_events):
            original_list = original_by_event.get(event_key, [])
            refined_list = refined_by_event.get(event_key, [])

            # 对比每个事件的所有记录
            if original_list and refined_list:
                # 按 relativeTs 排序，取第一条作为代表
                orig = sorted(original_list, key=lambda r: r.get('relativeTs', 0))[0]
                ref = sorted(refined_list, key=lambda r: r.get('relativeTs', 0))[0]

                orig_lib_id = orig.get('fileId')
                ref_lib_id = ref.get('fileId')
                orig_symbol_id = orig.get('symbolId')
                ref_symbol_id = ref.get('symbolId')

                is_lib_different = orig_lib_id != ref_lib_id
                is_symbol_different = orig_symbol_id != ref_symbol_id
                is_different = is_lib_different or is_symbol_different

                # 只添加有改变的行
                if is_different:
                    comparison_rows.append(
                        {
                            'step': orig.get('step', 'unknown'),  # 添加步骤标记
                            'eventId': f"{event_key[0]}_{event_key[1]}_{event_key[2]}_{event_key[3]}",
                            'pid': event_key[0],
                            'tid': event_key[1],
                            'addr': event_key[2],
                            'callchainId': event_key[3],
                            'eventCount': len(original_list),
                            'originalLibId': orig_lib_id,
                            'originalLibPath': orig.get('file'),
                            'refinedLibId': ref_lib_id,
                            'refinedLibPath': ref.get('file'),
                            'libIdChanged': is_lib_different,
                            'originalSymbolId': orig_symbol_id,
                            'originalSymbol': orig.get('symbol'),
                            'refinedSymbolId': ref_symbol_id,
                            'refinedSymbol': ref.get('symbol'),
                            'symbolIdChanged': is_symbol_different,
                            'isDifferent': is_different,
                            'process': orig.get('process'),
                            'thread': orig.get('thread'),
                            'eventType': orig.get('eventType'),
                            'totalHeapSize': sum(r.get('heapSize', 0) for r in original_list),
                        }
                    )

        logging.info('Found %d events with differences out of %d total events',
                     len(comparison_rows), len(all_events))
        return comparison_rows

    def _create_modified_callchain_data(
        self,
        comparison_data: list[dict],
        data_dict: dict[int, str],
        callchain_cache: dict[int, list[dict]],
    ) -> list[dict]:
        """创建修改过的调用链数据

        为每个有差异的调用链创建完整的调用链信息，
        显示原始值和精化值的对比。

        Args:
            comparison_data: 对比数据列表
            data_dict: 数据字典
            callchain_cache: 已缓存的调用链数据

        Returns:
            修改过的调用链数据列表
        """
        if not callchain_cache:
            return []

        callchain_rows = []

        # 收集所有有差异的调用链ID
        callchain_ids = set()
        for item in comparison_data:
            callchain_id = item.get('callchainId')
            if callchain_id and callchain_id > 0:
                callchain_ids.add(callchain_id)


        if not callchain_ids:
            logging.warning('No valid callchain IDs found in comparison data')
            return []

        logging.info('Exporting complete callchain info for %d modified callchains from cache', len(callchain_ids))

        # 为每个调用链创建数据
        for callchain_id in sorted(callchain_ids):
            # 从缓存中获取调用链帧
            frames = callchain_cache.get(callchain_id, [])

            if not frames:
                logging.warning('Callchain %d not found in cache', callchain_id)
                continue

            # 为每个帧创建一行数据
            for frame in frames:
                symbol_id = frame.get('symbol_id')
                file_id = frame.get('file_id')

                # 获取符号和文件名
                symbol_name = data_dict.get(symbol_id, 'unknown') if symbol_id else 'unknown'
                file_path = data_dict.get(file_id, 'unknown') if file_id else 'unknown'

                callchain_rows.append({
                    'callchainId': callchain_id,
                    'depth': frame.get('depth', 0),
                    'symbolId': symbol_id,
                    'symbol': symbol_name,
                    'fileId': file_id,
                    'file': file_path,
                    'ip': frame.get('ip'),
                    'offset': frame.get('offset'),
                    'symbolOffset': frame.get('symbol_offset'),
                    'vaddr': frame.get('vaddr'),
                })

        logging.info('Created %d callchain frame records from cache', len(callchain_rows))
        return callchain_rows

