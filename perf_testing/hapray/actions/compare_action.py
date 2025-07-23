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

import argparse
import json
import logging
import os
from typing import List

import pandas as pd

from hapray.core.common.excel_utils import ExcelReportSaver


def load_summary_info(directory: str):
    """Recursively load all summary_info.json files in a directory."""
    data = []
    for root, _, files in os.walk(directory):
        for file in files:
            if file == "summary_info.json":
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = json.load(f)
                        if isinstance(content, dict):
                            data.append(content)
                        elif isinstance(content, list):
                            data.extend([item for item in content if isinstance(item, dict)])
                except Exception as e:
                    logging.error("Failed to read %s: %s", file_path, str(e))
    return data


def pivot_summary_info(data: List[dict], prefix: str) -> pd.DataFrame:
    """
    以 scene+step_id+step_name 为主键，rom_version+app_version 为列，count 为值，生成透视表。
    prefix: 'base' 或 'compare'，用于区分列名
    """
    if not data:
        return pd.DataFrame()
    df = pd.DataFrame(data)
    df['version'] = df['rom_version'] + '|' + df['app_version']
    df['scene_key'] = df['scene'] + '||' + df['step_id'].astype(str) + '||' + df['step_name']
    pivot = df.pivot_table(
        index=['scene_key', 'scene', 'step_id', 'step_name'],
        columns='version',
        values='count',
        aggfunc='sum',
        fill_value=0
    )
    # 列名加前缀
    pivot.columns = [f'{prefix}_{col}' for col in pivot.columns]
    pivot = pivot.reset_index()
    return pivot


def merge_base_compare(base_df: pd.DataFrame, compare_df: pd.DataFrame) -> pd.DataFrame:
    # 以 scene_key, scene, step_id, step_name 为主键全外连接
    merged = pd.merge(
        base_df, compare_df,
        on=['scene_key', 'scene', 'step_id', 'step_name'],
        how='outer'
    )
    # 百分比列：对每个 compare_xxx 和 base_xxx 配对，计算 (compare-base)/base
    percent_cols = []
    for c in compare_df.columns:
        if c.startswith('compare_'):
            base_col = 'base_' + c[len('compare_'):]
            if base_col in merged.columns:
                percent_col = f'percent_{c[len("compare_"):]}'
                merged[percent_col] = (
                    merged[c] - merged[base_col]
                ) / merged[base_col].replace(0, pd.NA)
                percent_cols.append(percent_col)
    # 调整列顺序：主键+base各版本+compare各版本+percent
    key_cols = ['scene', 'step_id', 'step_name']
    base_cols = [c for c in merged.columns if c.startswith('base_')]
    compare_cols = [c for c in merged.columns if c.startswith('compare_')]
    merged = merged[key_cols + base_cols + compare_cols + percent_cols]
    return merged


class CompareAction:
    """Handles comparison of two report directories and generates a side-by-side Excel report."""

    @staticmethod
    def execute(args):
        parser = argparse.ArgumentParser(
            description="Compare two report directories and generate a side-by-side Excel.",
            prog="ArkAnalyzer-HapRay compare",
        )
        parser.add_argument('--base_dir', required=True, help='Base report directory (baseline)')
        parser.add_argument('--compare_dir', required=True, help='Compare report directory (to compare)')
        parser.add_argument(
            '--output', default=None,
            help='Output Excel file path (default: compare_result.xlsx in current dir)'
        )
        parsed = parser.parse_args(args)

        base_dir = os.path.abspath(parsed.base_dir)
        compare_dir = os.path.abspath(parsed.compare_dir)
        output_path = parsed.output or os.path.join(os.getcwd(), 'compare_result.xlsx')

        if not os.path.isdir(base_dir):
            logging.error("Base directory does not exist: %s", base_dir)
            return
        if not os.path.isdir(compare_dir):
            logging.error("Compare directory does not exist: %s", compare_dir)
            return

        logging.info("Comparing base: %s with compare: %s", base_dir, compare_dir)
        base_data = load_summary_info(base_dir)
        compare_data = load_summary_info(compare_dir)
        if not base_data and not compare_data:
            logging.error("No summary_info.json data found in either directory.")
            return
        base_pivot = pivot_summary_info(base_data, 'base')
        compare_pivot = pivot_summary_info(compare_data, 'compare')
        merged_df = merge_base_compare(base_pivot, compare_pivot)
        if merged_df.empty:
            logging.error("No data to write after merging.")
            return
        saver = ExcelReportSaver(output_path)
        saver.add_sheet(merged_df, 'Compare')
        saver.save()
        logging.info("Comparison Excel saved to %s", output_path)
