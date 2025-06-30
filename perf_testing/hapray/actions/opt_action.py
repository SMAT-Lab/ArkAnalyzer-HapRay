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
import logging
from concurrent.futures import ProcessPoolExecutor
from typing import Tuple, List, Optional

import pandas as pd

from hapray import VERSION
from hapray.core.common.excel_utils import ExcelReportSaver
from hapray.optimization_detector.file_info import FileCollector
from hapray.optimization_detector.invoke_symbols import InvokeSymbols
from hapray.optimization_detector.optimization_detector import OptimizationDetector


class OptAction:
    """Handles binary optimization analysis actions."""

    @staticmethod
    def execute(args) -> Optional[List[Tuple[str, pd.DataFrame]]]:
        """Executes binary optimization detection workflow."""
        parser = argparse.ArgumentParser(description="Analyze binary files for optimization flags",
                                         prog='ArkAnalyzer-HapRay opt')
        parser.add_argument('-v', '--version',
                            action='version',
                            version=f'%(prog)s {VERSION}',
                            help="Show program's version number and exit"
                            )
        parser.add_argument("--input", "-i", required=True,
                            help="Directory containing binary files to analyze")
        parser.add_argument("--output", "-o", default="binary_analysis_report.xlsx",
                            help="Output Excel file path (default: binary_analysis_report.xlsx)")
        parser.add_argument("--jobs", "-j", type=int, default=1,
                            help="Number of parallel jobs (default: 1)")
        parser.add_argument('--report_dir', '-r',
                            help='Directory containing reports to update')
        parsed_args = parser.parse_args(args)

        action = OptAction()
        file_collector = FileCollector()
        try:
            logging.info(f"Collecting binary files from: {parsed_args.input}")
            file_infos = file_collector.collect_binary_files(parsed_args.input)

            if not file_infos:
                logging.warning("No valid binary files found")
                return

            logging.info(f"Starting optimization detection on {len(file_infos)} files")

            with ProcessPoolExecutor(max_workers=2) as executor:
                futures = []
                future = executor.submit(action._run_detection, parsed_args.jobs, file_infos)
                futures.append(future)
                if parsed_args.report_dir:
                    future = executor.submit(action._run_invoke_analysis, file_infos, parsed_args.report_dir)
                    futures.append(future)

            data = []
            # Wait for all report generation tasks
            for future in futures:
                data.extend(future.result())
            action._generate_excel_report(data, parsed_args.output)
            logging.info(f"Analysis report saved to: {parsed_args.output}")
            return data
        finally:
            file_collector.cleanup()

    def _run_detection(self, jobs, file_infos):
        """Run optimization detection in a separate process"""
        detector = OptimizationDetector(jobs)
        return detector.detect_optimization(file_infos)

    def _run_invoke_analysis(self, file_infos, report_dir):
        """Run invoke symbols analysis in a separate process"""
        invoke_symbols = InvokeSymbols()
        return invoke_symbols.analyze(file_infos, report_dir)

    def _generate_excel_report(self, data: List[Tuple[str, pd.DataFrame]], output_file: str) -> None:
        """Generate Excel report using pandas"""
        report_saver = ExcelReportSaver(output_file)
        for row in data:
            report_saver.add_sheet(row[1], row[0])
        report_saver.save()
        logging.info("Report saved to %s", output_file)
