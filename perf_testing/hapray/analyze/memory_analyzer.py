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

import os
from typing import Any, Optional

import pandas as pd

from hapray.analyze import BaseAnalyzer
from hapray.core.common.memory import MemoryAnalyzerCore
from hapray.core.common.memory.memory_aggregator import MemoryAggregator


class MemoryAnalyzer(BaseAnalyzer):
    """内存分析器

    参考 FrameLoadAnalyzer 的架构，使用核心分析器进行分析
    所有计算逻辑都在 Python 中完成，不再依赖 SA

    注意：
    1. 内存分析是全局分析，不是按步骤分析
       - 第一次调用时（step1）：收集所有包含 native_hook 数据的 trace.db 文件并执行分析
       - 后续调用时（step2, step3...）：直接返回已有结果
    2. 内存数据从 htrace/stepX/trace.htrace 中获取，不再使用单独的 memory 目录
    3. 只处理包含 native_hook 表且有数据的 trace.db
    """

    def __init__(self, scene_dir: str, time_ranges: list[dict] = None):
        super().__init__(scene_dir, 'more/memory_analysis')
        self.time_ranges = time_ranges
        self.core_analyzer = MemoryAnalyzerCore()

    def _analyze_impl(
        self, step_dir: str, trace_db_path: str, perf_db_path: str, app_pids: list
    ) -> Optional[dict[str, Any]]:
        """执行内存分析

        Args:
            step_dir: 步骤目录（未使用，保留用于接口兼容）
            trace_db_path: trace.db 路径（未使用，保留用于接口兼容）
            perf_db_path: perf.db 路径（未使用，保留用于接口兼容）
            app_pids: 应用进程 ID 列表（未使用，保留用于接口兼容）
        """

        # 使用核心分析器进行分析
        return self.core_analyzer.analyze_memory(
            scene_dir=self.scene_dir,
            memory_db_path=trace_db_path,
            app_pids=app_pids,
        )

    def write_report(self, result: dict):
        """写入内存Excel报告，并保留父类JSON报告逻辑

        - 对每个 step：
          - 取峰值点（peak_time）与结束点（records 最大 relativeTs）
          - 分别调用 get_unreleased_by_callchain 汇总未释放
          - 写入 scene_dir/report/memory_report.xlsx，多sheet（StepX_Peak, StepX_End）
        """
        # 先写父类JSON报告
        super().write_report(result)

        if not self.results:
            return

        aggregator = MemoryAggregator()
        # 目标excel路径
        report_dir = os.path.join(self.scene_dir, 'report')
        os.makedirs(report_dir, exist_ok=True)
        excel_path = os.path.join(report_dir, 'memory_report.xlsx')

        # 汇总所有 step 与两个时间点到单个 Sheet
        with pd.ExcelWriter(
            excel_path, engine='xlsxwriter', engine_kwargs={'options': {'strings_to_numbers': False}}
        ) as writer:
            all_rows = []
            for step_name, step_data in self.results.items():
                if not isinstance(step_data, dict):
                    continue
                records = step_data.get('records') or []
                # 峰值点
                peak_time = (step_data.get('peak_time') or 0) if records else 0
                unreleased_peak = aggregator.get_unreleased_by_callchain(records, time=peak_time) if records else {}
                for callchain_id, group in (unreleased_peak or {}).items():
                    for alloc in group.get('allocs', []) or []:
                        all_rows.append(
                            {
                                'point': 'peak',
                                'step': step_name,
                                'callchainId': callchain_id,
                                'size': alloc.get('size'),
                                'count': alloc.get('count'),
                                'pid': alloc.get('pid'),
                                'process': alloc.get('process'),
                                'tid': alloc.get('tid'),
                                'thread': alloc.get('thread'),
                                'fileId': alloc.get('fileId'),
                                'file': alloc.get('file'),
                                'symbolId': alloc.get('symbolId'),
                                'symbol': alloc.get('symbol'),
                                'relativeTs': alloc.get('relativeTs'),
                                'componentCategory': alloc.get('componentCategory'),
                                'categoryName': alloc.get('categoryName'),
                                'subCategoryName': alloc.get('subCategoryName'),
                            }
                        )

                # 结束点：取记录最大 relativeTs
                end_time = max((r.get('relativeTs', 0) for r in records), default=peak_time) if records else 0
                unreleased_end = aggregator.get_unreleased_by_callchain(records, time=end_time) if records else {}
                for callchain_id, group in (unreleased_end or {}).items():
                    for alloc in group.get('allocs', []) or []:
                        all_rows.append(
                            {
                                'point': 'end',
                                'step': step_name,
                                'callchainId': callchain_id,
                                'size': alloc.get('size'),
                                'count': alloc.get('count'),
                                'pid': alloc.get('pid'),
                                'process': alloc.get('process'),
                                'tid': alloc.get('tid'),
                                'thread': alloc.get('thread'),
                                'fileId': alloc.get('fileId'),
                                'file': alloc.get('file'),
                                'symbolId': alloc.get('symbolId'),
                                'symbol': alloc.get('symbol'),
                                'relativeTs': alloc.get('relativeTs'),
                                'componentCategory': alloc.get('componentCategory'),
                                'categoryName': alloc.get('categoryName'),
                                'subCategoryName': alloc.get('subCategoryName'),
                            }
                        )

            df_all = pd.DataFrame(all_rows)
            sheet_name = 'MemoryUnreleased'
            df_all.to_excel(writer, sheet_name=sheet_name, index=False)

            # 固定列宽
            ws = writer.sheets[sheet_name]
            if not df_all.empty:
                ws.set_column(0, len(df_all.columns) - 1, 18)
            else:
                ws.set_column(0, 5, 18)

            # 新增：分类汇总（step, point, categoryName）
            by_cat_sheet = 'Summary_ByCategory'
            if not df_all.empty:
                cols_present = set(df_all.columns)
                need_cols = {'step', 'point', 'categoryName', 'size'}
                if need_cols.issubset(cols_present):
                    df_cat = (
                        df_all.groupby(['step', 'point', 'categoryName'], as_index=False)['size']
                        .sum()
                        .rename(columns={'size': 'totalSize'})
                    )
                else:
                    df_cat = pd.DataFrame([])
            else:
                df_cat = pd.DataFrame([])
            df_cat.to_excel(writer, sheet_name=by_cat_sheet, index=False)
            ws_cat = writer.sheets[by_cat_sheet]
            if not df_cat.empty:
                ws_cat.set_column(0, len(df_cat.columns) - 1, 20)
            else:
                ws_cat.set_column(0, 3, 18)

            # 新增：分类+子类汇总（step, point, categoryName, subCategoryName）
            by_sub_sheet = 'Summary_ByCategorySub'
            if not df_all.empty:
                cols_present = set(df_all.columns)
                need_cols_sub = {'step', 'point', 'categoryName', 'subCategoryName', 'size'}
                if need_cols_sub.issubset(cols_present):
                    df_cat_sub = (
                        df_all.groupby(['step', 'point', 'categoryName', 'subCategoryName'], as_index=False)['size']
                        .sum()
                        .rename(columns={'size': 'totalSize'})
                    )
                else:
                    df_cat_sub = pd.DataFrame([])
            else:
                df_cat_sub = pd.DataFrame([])
            df_cat_sub.to_excel(writer, sheet_name=by_sub_sheet, index=False)
            ws_sub = writer.sheets[by_sub_sheet]
            if not df_cat_sub.empty:
                ws_sub.set_column(0, len(df_cat_sub.columns) - 1, 20)
            else:
                ws_sub.set_column(0, 4, 18)

        # 写完Excel无需返回；父类已将结构写入JSON
