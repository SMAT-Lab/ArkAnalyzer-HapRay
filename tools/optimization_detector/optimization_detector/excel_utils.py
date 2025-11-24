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


class ExcelReportSaver:
    """Helper class to save multiple DataFrames to an Excel file with multiple sheets"""

    def __init__(self, output_path: str):
        """
        Initialize Excel report saver

        :param output_path: Path to save the Excel file
        """
        # Ensure the output path has .xlsx extension
        output_path = os.path.abspath(output_path)
        if not output_path.lower().endswith('.xlsx'):
            # Remove any existing extension and add .xlsx
            base_path = os.path.splitext(output_path)[0]
            output_path = base_path + '.xlsx'
        self.output_path = output_path
        self.sheets = {}

    def add_sheet(self, df: pd.DataFrame, sheet_name: str):
        """
        Add a DataFrame to be saved as a sheet

        :param df: DataFrame to save
        :param sheet_name: Name for the sheet (max 31 characters)
        """
        # Truncate sheet names longer than 31 characters
        sheet_name = sheet_name[:31]
        self.sheets[sheet_name] = df

    def save(self):
        """Save all added DataFrames to Excel file"""
        if not self.sheets:
            logging.warning('Warning: No sheets to save')
            return

        # Create directory if it doesn't exist
        output_dir = os.path.dirname(self.output_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)

        # Save to Excel using ExcelWriter
        # Explicitly set engine as string to avoid property object issues
        engine_name = 'xlsxwriter'
        with pd.ExcelWriter(self.output_path, engine=engine_name) as writer:
            for sheet_name, df in self.sheets.items():
                df.to_excel(writer, sheet_name=sheet_name)
                ExcelReportSaver._auto_adjust_columns(writer, sheet_name, df)

        logging.info('Excel report saved to: %s', self.output_path)

    @staticmethod
    def _auto_adjust_columns(writer, sheet_name, df):
        """Auto adjust excel columns"""
        worksheet = writer.sheets[sheet_name]

        for idx, col in enumerate(df.columns):
            max_len = max(
                len(str(col)),  # column name len
                df[col].astype(str).map(len).max(),  # max data len
            )
            # xlsxwriter uses set_column method (0-indexed columns)
            worksheet.set_column(idx, idx, max_len + 2)
