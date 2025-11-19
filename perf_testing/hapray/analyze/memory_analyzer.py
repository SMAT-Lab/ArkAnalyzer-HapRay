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
from hapray.core.common.memory.memory_comparison_exporter import MemoryComparisonExporter


class MemoryResultModel(BaseModel):
    """Memory analysis summary result model"""

    table_name = 'memory_results'
    fields = {'peak_time': 'REAL', 'records_count': 'INTEGER'}


class MemoryRecordStorageModel(BaseModel):
    """Memory analysis detailed record storage model

    数据以紧凑结构存储，仅保留字典 ID，避免重复字符串占用空间。
    """

    table_name = 'memory_records'
    fields = {
        'pid': 'INTEGER',
        'processId': 'INTEGER',
        'tid': 'INTEGER',
        'threadId': 'INTEGER',
        'fileId': 'INTEGER',
        'symbolId': 'INTEGER',
        'eventTypeId': 'INTEGER',
        'subEventTypeId': 'INTEGER',
        'addr': 'INTEGER',
        'callchainId': 'INTEGER',
        'heapSize': 'INTEGER',
        'relativeTs': 'INTEGER',
        'componentNameId': 'INTEGER',
        'componentCategory': 'INTEGER',
        'categoryNameId': 'INTEGER',
        'subCategoryNameId': 'INTEGER',
    }


class MemoryRecordModel(BaseModel):
    """Memory analysis detailed record model (view)

    通过视图 `memory_records` 联表 `memory_data_dicts`，提供与原表一致的查询列。
    componentCategory 直接存储为 INTEGER 类型，不通过字典表。
    """

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
        'addr': 'INTEGER',
        'callchainId': 'INTEGER',
        'heapSize': 'INTEGER',
        'relativeTs': 'INTEGER',
        'componentName': 'TEXT',
        'componentCategory': 'INTEGER',
        'categoryName': 'TEXT',
        'subCategoryName': 'TEXT',
    }


class MemoryCallchainStorageModel(BaseModel):
    """Memory analysis callchain frame storage model"""

    table_name = 'memory_callchains_raw'
    fields = {
        'callchainId': 'INTEGER',
        'depth': 'INTEGER',
        'ip': 'TEXT',
        'symbolId': 'INTEGER',
        'fileId': 'INTEGER',
        'offset': 'INTEGER',
        'symbolOffset': 'INTEGER',
        'vaddr': 'TEXT',
    }


class MemoryCallchainModel(BaseModel):
    """Memory analysis callchain frame view model"""

    table_name = 'memory_callchains'
    fields = {
        'callchainId': 'INTEGER',
        'depth': 'INTEGER',
        'ip': 'TEXT',
        'symbolId': 'INTEGER',
        'symbol': 'TEXT',
        'fileId': 'INTEGER',
        'file': 'TEXT',
        'offset': 'INTEGER',
        'symbolOffset': 'INTEGER',
        'vaddr': 'TEXT',
    }


class MemoryDataDictModel(BaseModel):
    """Memory analysis data_dict model"""

    table_name = 'memory_data_dicts'
    fields = {
        'dictId': 'INTEGER',
        'value': 'TEXT',
    }


class MemoryAnalyzer(BaseAnalyzer):
    """Memory analyzer

    Uses core analyzer for analysis, following FrameLoadAnalyzer architecture.
    All calculation logic is completed in Python, no longer depends on SA.

    Notes:
    1. Memory analysis is global analysis, not per-step analysis
       - First call (step1): Collect all trace.db files containing native_hook data and perform analysis
       - Subsequent calls (step2, step3...): Return existing results directly
    2. Memory data is obtained from htrace/stepX/trace.htrace, no longer uses separate memory directory
    3. Only processes trace.db files that contain native_hook table with data
    """

    def __init__(self, scene_dir: str, time_ranges: list[dict] = None, use_refined_lib_symbol: bool = False, export_comparison: bool = False):
        super().__init__(scene_dir, 'more/memory_analysis')
        self.time_ranges = time_ranges
        self.use_refined_lib_symbol = use_refined_lib_symbol
        self.export_comparison = export_comparison
        self.core_analyzer = MemoryAnalyzerCore(use_refined_lib_symbol, collect_comparison_data=export_comparison)

        # 收集所有步骤的对比数据
        self.all_comparison_data = {
            'original_records': [],
            'refined_records': [],
            'data_dict': {},
            'callchain_cache': {},
        }

    def _analyze_impl(
        self, step_dir: str, trace_db_path: str, perf_db_path: str, app_pids: list
    ) -> Optional[dict[str, Any]]:
        """Execute memory analysis

        Args:
            step_dir: Step directory (unused, kept for interface compatibility)
            trace_db_path: trace.db path (unused, kept for interface compatibility)
            perf_db_path: perf.db path (unused, kept for interface compatibility)
            app_pids: Application process ID list (unused, kept for interface compatibility)

        Returns:
            Analysis results dictionary
        """
        # Use core analyzer for analysis
        result = self.core_analyzer.analyze_memory(
            scene_dir=self.scene_dir,
            memory_db_path=trace_db_path,
            app_pids=app_pids,
        )

        # 如果启用了对比导出，收集对比数据并添加步骤标记
        if self.export_comparison and result and 'original_records' in result:
            # 为原始记录添加步骤标记
            original_records = result.get('original_records', [])
            for record in original_records:
                record['step'] = step_dir
            self.all_comparison_data['original_records'].extend(original_records)

            # 为refined记录添加步骤标记
            refined_records = result.get('records', [])
            for record in refined_records:
                record['step'] = step_dir
            self.all_comparison_data['refined_records'].extend(refined_records)

            # 合并 data_dict
            data_dict = result.get('dataDict', {})
            self.all_comparison_data['data_dict'].update(data_dict)
            # 合并 callchain_cache
            callchain_cache = result.get('callchain_cache', {})
            self.all_comparison_data['callchain_cache'].update(callchain_cache)

        return result

    def write_report(self, result: dict):
        """Write memory Excel report and preserve parent class JSON report logic

        For each step:
          - Get peak point (peak_time) and end point (max relativeTs from records)
          - Call get_unreleased_by_callchain to aggregate unreleased memory for each point
          - Write to scene_dir/report/memory_report.xlsx with multiple sheets
        """

        if not self.results:
            return

        aggregator = MemoryAggregator()
        # Target Excel file path
        report_dir = os.path.join(self.scene_dir, 'report')
        os.makedirs(report_dir, exist_ok=True)
        excel_path = os.path.join(report_dir, 'memory_report.xlsx')

        # Aggregate all steps and two time points into a single sheet
        with pd.ExcelWriter(
            excel_path, engine='xlsxwriter', engine_kwargs={'options': {'strings_to_numbers': False}}
        ) as writer:
            all_rows = []
            for step_name, step_data in self.results.items():
                if not isinstance(step_data, dict):
                    continue
                records = step_data.get('records') or []
                # Peak point
                peak_time = (step_data.get('peak_time') or 0) if records else 0
                unreleased_peak = aggregator.get_unreleased_by_callchain(records, time=peak_time) if records else {}
                all_rows.extend(self._extract_unreleased_rows(unreleased_peak, step_name, 'peak'))

                # End point: get max relativeTs from records
                end_time = max((r.get('relativeTs', 0) for r in records), default=peak_time) if records else 0
                unreleased_end = aggregator.get_unreleased_by_callchain(records, time=end_time) if records else {}
                all_rows.extend(self._extract_unreleased_rows(unreleased_end, step_name, 'end'))

            self._write_excel_sheets(writer, all_rows)

        # Excel writing complete; parent class has already written structure to JSON

        # 导出对比报告（如果启用了对比导出）
        if self.export_comparison:
            self._export_comparison_report()

        # Save to SQLite database
        self._save_results_to_db()

    def _export_comparison_report(self):
        """导出对比报告（包含所有步骤的数据）"""
        try:
            # 检查是否有对比数据
            if not self.all_comparison_data['original_records'] and not self.all_comparison_data['refined_records']:
                self.logger.info('No comparison data to export')
                return

            report_dir = os.path.join(self.scene_dir, 'report')
            os.makedirs(report_dir, exist_ok=True)
            comparison_path = os.path.join(report_dir, 'memory_comparison.xlsx')

            # 使用 MemoryComparisonExporter 导出
            exporter = MemoryComparisonExporter()
            exporter.export_comparison(
                output_path=comparison_path,
                original_records=self.all_comparison_data['original_records'],
                refined_records=self.all_comparison_data['refined_records'],
                data_dict=self.all_comparison_data['data_dict'],
                callchain_cache=self.all_comparison_data['callchain_cache'],
            )

            self.logger.info(
                'Comparison report exported to %s (%d original records, %d refined records)',
                comparison_path,
                len(self.all_comparison_data['original_records']),
                len(self.all_comparison_data['refined_records']),
            )
        except Exception as e:
            self.logger.warning('Failed to export comparison report: %s', str(e))


    def _extract_unreleased_rows(self, unreleased_data: dict, step_name: str, point: str) -> list[dict]:
        """Extract unreleased memory rows from aggregator result

        Args:
            unreleased_data: Unreleased data dictionary from aggregator
            step_name: Step name
            point: Time point identifier ('peak' or 'end')

        Returns:
            List of row dictionaries
        """
        rows = []
        for callchain_id, group in (unreleased_data or {}).items():
            for alloc in group.get('allocs', []) or []:
                rows.append(
                    {
                        'point': point,
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
        return rows

    def _write_excel_sheets(self, writer: pd.ExcelWriter, all_rows: list[dict]):
        """Write all Excel sheets with memory data

        Args:
            writer: Excel writer object
            all_rows: List of all data rows
        """
        df_all = pd.DataFrame(all_rows)
        sheet_name = 'MemoryUnreleased'
        df_all.to_excel(writer, sheet_name=sheet_name, index=False)

        # Set fixed column width
        ws = writer.sheets[sheet_name]
        if not df_all.empty:
            ws.set_column(0, len(df_all.columns) - 1, 18)
        else:
            ws.set_column(0, 5, 18)

        # Category summary (step, point, categoryName)
        by_cat_sheet = 'Summary_ByCategory'
        df_cat = self._create_category_summary(df_all, ['step', 'point', 'categoryName'])
        df_cat.to_excel(writer, sheet_name=by_cat_sheet, index=False)
        ws_cat = writer.sheets[by_cat_sheet]
        if not df_cat.empty:
            ws_cat.set_column(0, len(df_cat.columns) - 1, 20)
        else:
            ws_cat.set_column(0, 3, 18)

        # Category + subcategory summary (step, point, categoryName, subCategoryName)
        by_sub_sheet = 'Summary_ByCategorySub'
        df_cat_sub = self._create_category_summary(df_all, ['step', 'point', 'categoryName', 'subCategoryName'])
        df_cat_sub.to_excel(writer, sheet_name=by_sub_sheet, index=False)
        ws_sub = writer.sheets[by_sub_sheet]
        if not df_cat_sub.empty:
            ws_sub.set_column(0, len(df_cat_sub.columns) - 1, 20)
        else:
            ws_sub.set_column(0, 4, 18)

    def _create_category_summary(self, df: pd.DataFrame, groupby_cols: list[str]) -> pd.DataFrame:
        """Create category summary DataFrame

        Args:
            df: Source DataFrame
            groupby_cols: Columns to group by

        Returns:
            Summary DataFrame
        """
        if df.empty:
            return pd.DataFrame([])

        required_cols = set(groupby_cols + ['size'])
        if not required_cols.issubset(set(df.columns)):
            return pd.DataFrame([])

        return df.groupby(groupby_cols, as_index=False)['size'].sum().rename(columns={'size': 'totalSize'})

    def _save_results_to_db(self):
        """Save self.results to SQLite database file

        Database file is saved at scene_dir/report/hapray_report.db (shared with other analyzers).
        Uses Model classes to create two tables:
        1. memory_results: Stores summary information for each step
        2. memory_records: Stores detailed information for each record
        """
        if not self.results:
            return

        try:
            # Create tables (based on model classes)
            self.create_model_table(MemoryResultModel)
            self.create_model_table(MemoryRecordStorageModel)
            self.create_model_table(MemoryCallchainStorageModel)
            self.create_model_table(MemoryDataDictModel)

            # 先构建紧凑存储表，再创建兼容视图
            self._create_memory_callchains_view()

            # Add unique constraint to memory_results table (only one row per step_id)
            # Note: create_model_table has already created a regular step_id index
            # We need to delete the regular index, then create a unique index
            self._create_unique_index_for_results()

            # Create additional indexes to improve query performance
            # step_id index is automatically created by create_model_table
            self._create_memory_records_indexes()
            self._create_memory_callchains_indexes()
            self._create_memory_data_dict_indexes()

            # Save data
            for step_name, step_data in self.results.items():
                if not isinstance(step_data, dict):
                    continue

                step_id = self.step_dir_to_step_id(step_name)
                self._save_step_data_to_db(step_id, step_data)

            self.logger.info('Memory analysis results saved to database: %s', self.get_db_path())
        except Exception as e:
            self.logger.exception('Failed to save memory analysis results to database: %s', str(e))

    def _create_unique_index_for_results(self):
        """Create unique index for memory_results table"""
        try:
            # Try to drop existing regular index
            self.exec_sql('DROP INDEX IF EXISTS idx_memory_results_step_id')
            # Create unique index (implements unique constraint effect)
            self.create_index('idx_memory_results_step_id', 'memory_results', 'step_id', unique=True)
        except Exception:
            # If operation fails, try to create unique index (IF NOT EXISTS handles existing case)
            self.create_index('idx_memory_results_step_id_unique', 'memory_results', 'step_id', unique=True)

    def _create_memory_records_indexes(self):
        """Create indexes for memory_records table to improve query performance"""
        self.exec_sql('DROP INDEX IF EXISTS idx_memory_records_callchainId')
        self.create_index('idx_memory_records_callchainId', 'memory_records', 'callchainId')
        self.exec_sql('DROP INDEX IF EXISTS idx_memory_records_relativeTs')
        self.create_index('idx_memory_records_relativeTs', 'memory_records', 'relativeTs')
        self.exec_sql('DROP INDEX IF EXISTS idx_memory_records_componentName')
        self.exec_sql('DROP INDEX IF EXISTS idx_memory_records_componentNameId')
        self.create_index('idx_memory_records_componentNameId', 'memory_records', 'componentNameId')
        # 为 componentCategory 创建索引以提高查询效率
        self.exec_sql('DROP INDEX IF EXISTS idx_memory_records_componentCategory')
        self.create_index('idx_memory_records_componentCategory', 'memory_records', 'componentCategory')

    def _create_memory_callchains_view(self):
        """Create or refresh view for memory_callchains"""
        view_sql = """
            CREATE VIEW IF NOT EXISTS memory_callchains AS
            SELECT
                raw.step_id AS step_id,
                raw.callchainId AS callchainId,
                raw.depth AS depth,
                raw.ip AS ip,
                raw.symbolId AS symbolId,
                symbol_dict.value AS symbol,
                raw.fileId AS fileId,
                file_dict.value AS file,
                raw.offset AS offset,
                raw.symbolOffset AS symbolOffset,
                raw.vaddr AS vaddr
            FROM memory_callchains_raw AS raw
            LEFT JOIN memory_data_dicts AS symbol_dict ON raw.symbolId = symbol_dict.dictId
            LEFT JOIN memory_data_dicts AS file_dict ON raw.fileId = file_dict.dictId
        """
        # 删除旧视图及同名遗留表，确保列定义更新
        self.exec_sql('DROP VIEW IF EXISTS memory_callchains')
        self.exec_sql('DROP TABLE IF EXISTS memory_callchains')
        self.exec_sql(view_sql)

    def _create_memory_callchains_indexes(self):
        """Create indexes for memory_callchains table to improve query performance"""
        self.exec_sql('DROP INDEX IF EXISTS idx_memory_callchains_callchainId')
        self.create_index('idx_memory_callchains_callchainId', 'memory_callchains_raw', 'callchainId')
        self.exec_sql('DROP INDEX IF EXISTS idx_memory_callchains_depth')
        self.create_index('idx_memory_callchains_depth', 'memory_callchains_raw', 'depth')

    def _create_memory_data_dict_indexes(self):
        """Create indexes for memory_data_dicts table to improve query performance"""
        self.exec_sql('DROP INDEX IF EXISTS idx_memory_data_dicts_dictId')
        self.create_index('idx_memory_data_dicts_step_dict', 'memory_data_dicts', 'step_id, dictId')
        self.create_index('idx_memory_data_dicts_value', 'memory_data_dicts', 'value')

    def _save_step_data_to_db(self, step_id: int, step_data: dict):
        """Save step data to database

        Args:
            step_id: Step ID (INTEGER)
            step_data: Step data dictionary
        """
        # Prepare summary data
        records = step_data.get('records') or []
        peak_time = (step_data.get('peak_time') or 0) if records else 0
        records_count = len(records) if records else 0

        # Save summary information (use replace=True to implement INSERT OR REPLACE)
        result_model = MemoryResultModel(
            peak_time=peak_time,
            records_count=records_count,
        )
        self.save_model(step_id, result_model, replace=True)

        # Delete old records for this step (if exist)
        self.exec_sql('DELETE FROM memory_records WHERE step_id = ?', (step_id,))
        self.exec_sql('DELETE FROM memory_callchains_raw WHERE step_id = ?', (step_id,))
        self.exec_sql('DELETE FROM memory_data_dicts WHERE step_id = ?', (step_id,))

        # Batch save detailed records
        data_dict = dict(step_data.get('dataDict') or {})
        if records:
            record_models, data_dict = self._create_record_models(records, data_dict)
            if record_models:
                self.batch_save_models(step_id, record_models, replace=False)

        callchains = step_data.get('callchains') or {}
        if callchains:
            callchain_models = self._create_callchain_models(callchains)
            if callchain_models:
                self.batch_save_models(step_id, callchain_models, replace=False)

        if data_dict:
            data_dict_models = self._create_data_dict_models(data_dict)
            if data_dict_models:
                self.batch_save_models(step_id, data_dict_models, replace=False)

    def _create_record_models(
        self, records: list[dict], data_dict: dict[int, str]
    ) -> tuple[list[MemoryRecordStorageModel], dict[int, str]]:
        """Create MemoryRecordStorageModel instances from record dictionaries

        Args:
            records: List of record dictionaries
            data_dict: Dictionary of existing dictId -> value mappings (will be extended)

        Returns:
            Tuple of (list of MemoryRecordStorageModel instances, updated data_dict)
        """
        record_models: list[MemoryRecordStorageModel] = []
        if not isinstance(data_dict, dict):
            data_dict = {}

        inverse_map = {value: dict_id for dict_id, value in data_dict.items() if value is not None}
        next_dict_id = (max(data_dict.keys()) + 1) if data_dict else 1

        def to_dict_id(value: Optional[Any]) -> Optional[int]:
            nonlocal next_dict_id
            if value is None:
                return None
            value_str = str(value) if not isinstance(value, str) else value
            existing = inverse_map.get(value_str)
            if existing is not None:
                return existing
            dict_id = next_dict_id
            next_dict_id += 1
            data_dict[dict_id] = value_str
            inverse_map[value_str] = dict_id
            return dict_id

        for record in records:
            if not isinstance(record, dict):
                continue

            record_model = MemoryRecordStorageModel(
                pid=record.get('pid'),
                processId=to_dict_id(record.get('process')),
                tid=record.get('tid'),
                threadId=to_dict_id(record.get('thread')),
                fileId=record.get('fileId'),
                symbolId=record.get('symbolId'),
                eventTypeId=to_dict_id(record.get('eventType')),
                subEventTypeId=to_dict_id(record.get('subEventType')),
                addr=record.get('addr'),
                callchainId=record.get('callchainId'),
                heapSize=record.get('heapSize'),
                relativeTs=record.get('relativeTs'),
                componentNameId=to_dict_id(record.get('componentName')),
                componentCategory=record.get('componentCategory'),
                categoryNameId=to_dict_id(record.get('categoryName')),
                subCategoryNameId=to_dict_id(record.get('subCategoryName')),
            )
            record_models.append(record_model)

        return record_models, data_dict

    def _create_callchain_models(self, callchains: dict[int, list[dict]]) -> list[MemoryCallchainStorageModel]:
        """Create MemoryCallchainStorageModel instances from callchain dictionaries

        Args:
            callchains: Mapping of callchainId to frame list

        Returns:
            List of MemoryCallchainStorageModel instances
        """
        models: list[MemoryCallchainStorageModel] = []
        for callchain_id, frames in callchains.items():
            if not isinstance(frames, list):
                continue

            for frame in frames:
                if not isinstance(frame, dict):
                    continue

                model = MemoryCallchainStorageModel(
                    callchainId=callchain_id,
                    depth=frame.get('depth'),
                    ip=frame.get('ip'),
                    symbolId=frame.get('symbolId'),
                    fileId=frame.get('fileId'),
                    offset=frame.get('offset'),
                    symbolOffset=frame.get('symbolOffset'),
                    vaddr=frame.get('vaddr'),
                )
                models.append(model)
        return models

    def _create_data_dict_models(self, data_dict: dict[int, str]) -> list[MemoryDataDictModel]:
        """Create MemoryDataDictModel instances from data_dict mapping

        Args:
            data_dict: Mapping from native data_dict id to text

        Returns:
            List of MemoryDataDictModel instances
        """
        models: list[MemoryDataDictModel] = []
        for dict_id, value in data_dict.items():
            model = MemoryDataDictModel(
                dictId=dict_id,
                value=value,
            )
            models.append(model)
        return models
