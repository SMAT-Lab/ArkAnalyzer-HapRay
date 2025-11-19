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
import multiprocessing
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import Optional

import pandas as pd

from optimization_detector import FileCollector, InvokeSymbols, OptimizationDetector, __version__
from optimization_detector.excel_utils import ExcelReportSaver


class OptAction:
    """Handles binary optimization analysis actions."""

    @staticmethod
    def execute() -> Optional[list[tuple[str, pd.DataFrame]]]:
        """Executes binary optimization detection workflow."""
        parser = argparse.ArgumentParser(description='Analyze binary files for optimization flags', prog='opt-detector')
        parser.add_argument(
            '-v',
            '--version',
            action='version',
            version=f'%(prog)s {__version__}',
            help="Show program's version number and exit",
        )
        parser.add_argument(
            '--input',
            '-i',
            required=True,
            help='Input path: directory containing binary files, or single file (.so, .a, .hap, .hsp, .apk) to analyze',
        )
        parser.add_argument(
            '--output',
            '-o',
            default='binary_analysis_report.xlsx',
            help='Output Excel file path (default: binary_analysis_report.xlsx)',
        )
        parser.add_argument('--jobs', '-j', type=int, default=1, help='Number of parallel jobs (default: 1)')
        parser.add_argument('--report_dir', '-r', help='Directory containing reports to update')
        parser.add_argument(
            '--timeout',
            '-t',
            type=int,
            default=None,
            help='Timeout in seconds for processing a single file (default: no timeout)',
        )
        parser.add_argument(
            '--no-lto',
            dest='lto',
            action='store_false',
            default=True,
            help='Disable LTO (Link-Time Optimization) detection for .so files (default: enabled)',
        )
        parser.add_argument(
            '--no-opt',
            dest='opt',
            action='store_false',
            default=True,
            help='Disable optimization level (Ox) detection, only run LTO detection (default: enabled)',
        )
        parser.add_argument('--verbose', action='store_true', help='Show verbose logs')

        parser.add_argument('--log-file', help='Path to log file')

        parsed_args = parser.parse_args()

        # 配置日志
        OptAction.setup_logging(parsed_args.verbose, parsed_args.log_file)

        action = OptAction()
        file_collector = FileCollector()
        try:
            logging.info('Collecting binary files from: %s', parsed_args.input)
            file_infos = file_collector.collect_binary_files(parsed_args.input)

            if not file_infos:
                logging.warning('No valid binary files found')
                return None

            logging.info('Starting optimization detection on %d files', len(file_infos))
            if parsed_args.timeout:
                logging.info('Timeout per file: %d seconds', parsed_args.timeout)
            multiprocessing.freeze_support()
            with ProcessPoolExecutor(max_workers=2) as executor:
                futures = []
                future = executor.submit(
                    action.run_detection,
                    parsed_args.jobs,
                    file_infos,
                    parsed_args.timeout,
                    parsed_args.lto,
                    parsed_args.opt,
                )
                futures.append(future)
                if parsed_args.report_dir:
                    future = executor.submit(action.run_invoke_analysis, file_infos, parsed_args.report_dir)
                    futures.append(future)

                data = []
                # Wait for all report generation tasks
                for future in as_completed(futures):
                    data.extend(future.result())
                action.generate_excel_report(data, parsed_args.output)
                logging.info('Analysis report saved to: %s', parsed_args.output)
                return data
        finally:
            file_collector.cleanup()

    @staticmethod
    def run_detection(jobs, file_infos, timeout=None, enable_lto=False, enable_opt=True):
        """Run optimization detection in a separate process"""
        try:
            detector = OptimizationDetector(jobs, timeout=timeout, enable_lto=enable_lto, enable_opt=enable_opt)
            return detector.detect_optimization(file_infos)
        except Exception as e:
            logging.error('OptimizationDetector error: %s', str(e))
            return []

    @staticmethod
    def run_invoke_analysis(file_infos, report_dir):
        """Run invoke symbols analysis in a separate process"""
        invoke_symbols = InvokeSymbols()
        return invoke_symbols.analyze(file_infos, report_dir)

    @staticmethod
    def generate_excel_report(data: list[tuple[str, pd.DataFrame]], output_file: str) -> None:
        """Generate Excel report using pandas"""
        report_saver = ExcelReportSaver(output_file)
        for row in data:
            report_saver.add_sheet(row[1], row[0])
        report_saver.save()
        logging.info('Report saved to %s', output_file)

    @staticmethod
    def setup_logging(verbose: bool = False, log_file: str = None):
        """配置日志"""
        level = logging.DEBUG if verbose else logging.INFO
        handlers = [logging.StreamHandler(sys.stdout)]

        if log_file:
            handlers.append(logging.FileHandler(log_file, encoding='utf-8'))

        logging.basicConfig(
            level=level, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', handlers=handlers
        )


if __name__ == '__main__':
    multiprocessing.freeze_support()
    sys.exit(OptAction.execute())
