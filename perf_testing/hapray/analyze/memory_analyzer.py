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

from hapray.analyze.base_analyzer import BaseAnalyzer, BaseModel
from hapray.core.common.memory import MemoryAnalyzerCore
from hapray.core.common.memory.memory_aggregator import MemoryAggregator


class MemoryResultModel(BaseModel):
    """内存分析汇总结果模型"""

    table_name = 'memory_results'
    fields = {'peak_time': 'REAL', 'records_count': 'INTEGER', 'created_at': 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP'}


class MemoryRecordModel(BaseModel):
    """内存分析详细记录模型"""

    table_name = 'memory_records'
    fields = {
        'pid': 'INTEGER',
        'process': 'TEXT',
        'tid': 'INTEGER',
        'thread': 'TEXT',
        'fileId': 'INTEGER',
        'file': 'TEXT',
        'symbolId': 'INTEGER',
        'symbol': 'TEXT',
        'eventType': 'TEXT',
        'subEventType': 'TEXT',
        'addr': 'TEXT',
        'callchainId': 'INTEGER',
        'heapSize': 'INTEGER',
        'relativeTs': 'INTEGER',
        'componentName': 'TEXT',
        'componentCategory': 'TEXT',
        'categoryName': 'TEXT',
        'subCategoryName': 'TEXT',
        'created_at': 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP',
    }


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

        # 保存到SQLite数据库
        self._save_results_to_db()

    def _save_results_to_db(self):
        """将 self.results 保存到 SQLite 数据库文件

        数据库文件保存在 scene_dir/report/hapray_report.db（与其他分析器共享）
        使用 Model 类创建两个表：
        1. memory_results: 存储每个 step 的汇总信息
        2. memory_records: 存储每条记录的详细信息
        """
        if not self.results:
            return

        try:
            # 创建表（基于模型类）
            self.create_model_table(MemoryResultModel)
            self.create_model_table(MemoryRecordModel)

            # 为 memory_results 表添加唯一约束（每个 step_id 只有一行）
            # 注意：create_model_table 已经创建了普通 step_id 索引
            # 我们需要删除普通索引，然后创建唯一索引
            # 或者直接使用唯一索引覆盖（如果支持的话）
            try:
                # 尝试删除可能存在的普通索引
                self.exec_sql('DROP INDEX IF EXISTS idx_memory_results_step_id')
                # 创建唯一索引（实现唯一约束效果）
                self.create_index('idx_memory_results_step_id', 'memory_results', 'step_id', unique=True)
            except Exception:
                # 如果操作失败，尝试创建唯一索引（IF NOT EXISTS 会处理已存在的情况）
                self.create_index('idx_memory_results_step_id_unique', 'memory_results', 'step_id', unique=True)

            # 创建额外的索引以提高查询性能
            # step_id 索引已由 create_model_table 自动创建
            self.create_index('idx_memory_records_callchainId', 'memory_records', 'callchainId')
            self.create_index('idx_memory_records_relativeTs', 'memory_records', 'relativeTs')
            self.create_index('idx_memory_records_componentName', 'memory_records', 'componentName')

            # 保存数据
            for step_name, step_data in self.results.items():
                if not isinstance(step_data, dict):
                    continue

                # 转换 step_name 为 step_id (INTEGER)
                step_id = self.step_dir_to_step_id(step_name)

                # 准备汇总数据
                records = step_data.get('records') or []
                peak_time = (step_data.get('peak_time') or 0) if records else 0
                records_count = len(records) if records else 0

                # 保存汇总信息（使用 replace=True 实现 INSERT OR REPLACE）
                result_model = MemoryResultModel(
                    peak_time=peak_time,
                    records_count=records_count,
                )
                self.save_model(step_id, result_model, replace=True)

                # 删除该 step 的旧记录（如果存在）
                self.exec_sql('DELETE FROM memory_records WHERE step_id = ?', (step_id,))

                # 批量保存详细记录
                if records:
                    record_models = []
                    for record in records:
                        if not isinstance(record, dict):
                            continue

                        record_model = MemoryRecordModel(
                            pid=record.get('pid'),
                            process=record.get('process'),
                            tid=record.get('tid'),
                            thread=record.get('thread'),
                            fileId=record.get('fileId'),
                            file=record.get('file'),
                            symbolId=record.get('symbolId'),
                            symbol=record.get('symbol'),
                            eventType=record.get('eventType'),
                            subEventType=record.get('subEventType'),
                            addr=record.get('addr'),
                            callchainId=record.get('callchainId'),
                            heapSize=record.get('heapSize'),
                            relativeTs=record.get('relativeTs'),
                            componentName=record.get('componentName'),
                            componentCategory=record.get('componentCategory'),
                            categoryName=record.get('categoryName'),
                            subCategoryName=record.get('subCategoryName'),
                        )
                        record_models.append(record_model)

                    if record_models:
                        self.batch_save_models(step_id, record_models, replace=False)

            self.logger.info('Memory analysis results saved to database: %s', self.get_db_path())
        except Exception as e:
            self.logger.exception('Failed to save memory analysis results to database: %s', str(e))
