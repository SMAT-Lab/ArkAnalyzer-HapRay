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
    """Memory analysis summary result model"""

    table_name = 'memory_results'
    fields = {'peak_time': 'REAL', 'records_count': 'INTEGER', 'created_at': 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP'}


class MemoryRecordModel(BaseModel):
    """Memory analysis detailed record model"""

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

    def __init__(self, scene_dir: str, time_ranges: list[dict] = None):
        super().__init__(scene_dir, 'more/memory_analysis')
        self.time_ranges = time_ranges
        self.core_analyzer = MemoryAnalyzerCore()

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
        return self.core_analyzer.analyze_memory(
            scene_dir=self.scene_dir,
            memory_db_path=trace_db_path,
            app_pids=app_pids,
        )

    def write_report(self, result: dict):
        """Write memory Excel report and preserve parent class JSON report logic

        For each step:
          - Get peak point (peak_time) and end point (max relativeTs from records)
          - Call get_unreleased_by_callchain to aggregate unreleased memory for each point
          - Write to scene_dir/report/memory_report.xlsx with multiple sheets
        """
        # Write parent class JSON report first
        super().write_report(result)

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

        # Save to SQLite database
        self._save_results_to_db()

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
                rows.append({
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
                })
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

        return (
            df.groupby(groupby_cols, as_index=False)['size']
            .sum()
            .rename(columns={'size': 'totalSize'})
        )

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
            self.create_model_table(MemoryRecordModel)

            # Add unique constraint to memory_results table (only one row per step_id)
            # Note: create_model_table has already created a regular step_id index
            # We need to delete the regular index, then create a unique index
            self._create_unique_index_for_results()

            # Create additional indexes to improve query performance
            # step_id index is automatically created by create_model_table
            self._create_memory_records_indexes()

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
        self.create_index('idx_memory_records_callchainId', 'memory_records', 'callchainId')
        self.create_index('idx_memory_records_relativeTs', 'memory_records', 'relativeTs')
        self.create_index('idx_memory_records_componentName', 'memory_records', 'componentName')

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

        # Batch save detailed records
        if records:
            record_models = self._create_record_models(records)
            if record_models:
                self.batch_save_models(step_id, record_models, replace=False)

    def _create_record_models(self, records: list[dict]) -> list[MemoryRecordModel]:
        """Create MemoryRecordModel instances from record dictionaries

        Args:
            records: List of record dictionaries

        Returns:
            List of MemoryRecordModel instances
        """
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

        return record_models
