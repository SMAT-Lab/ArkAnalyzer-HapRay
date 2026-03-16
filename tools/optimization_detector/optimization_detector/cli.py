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
import io
import logging
import multiprocessing
import sys
from typing import Optional

from optimization_detector import __version__, detect_optimization
from optimization_detector.errors import OptDetectorInputError, OptDetectorNoFilesError

_STDOUT_WRAPPER = None


class OptAction:
    """Handles binary optimization analysis actions."""

    @staticmethod
    def execute() -> int:
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
            help='Input path: directory containing binary files, or single file (.so, .a, .hap, .hsp, .apk, .har) to analyze',
        )
        parser.add_argument(
            '--output',
            '-o',
            default='binary_analysis_report.xlsx',
            help='Output file path (default: binary_analysis_report.xlsx). Format is auto-detected from extension, or use --format to specify.',
        )
        parser.add_argument(
            '--format',
            '-f',
            choices=['excel', 'json', 'csv', 'xml'],
            nargs='+',
            default=None,
            help='Output format(s): excel, json, csv, or xml. Can specify multiple formats (e.g., -f excel json). If not specified, format is inferred from output file extension.',
        )
        parser.add_argument('--jobs', '-j', type=int, default=1, help='Number of parallel jobs (default: 1)')
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

        OptAction.setup_logging(parsed_args.verbose, parsed_args.log_file)

        try:
            result = detect_optimization(
                parsed_args.input,
                output=parsed_args.output,
                output_format=parsed_args.format,
                jobs=parsed_args.jobs,
                timeout=parsed_args.timeout,
                enable_lto=parsed_args.lto,
                enable_opt=parsed_args.opt,
                return_dict=False,
                save_reports=True,
            )
            if result.get('success'):
                logging.info('Analysis complete. Summary: %s', result.get('summary', {}))
                return 0
            logging.error('Analysis failed: %s', result.get('error', 'Unknown error'))
            return 1
        except OptDetectorInputError as e:
            logging.error('Input error: %s', e.message)
            return 1
        except OptDetectorNoFilesError as e:
            logging.warning('No valid binary files found: %s', e.message)
            return 1

    @staticmethod
    def setup_logging(verbose: bool = False, log_file: Optional[str] = None):
        """配置日志"""
        level = logging.DEBUG if verbose else logging.INFO
        global _STDOUT_WRAPPER
        if _STDOUT_WRAPPER is None:
            _STDOUT_WRAPPER = io.TextIOWrapper(
                sys.stdout.buffer, encoding='utf-8', errors='replace', line_buffering=True
            )

        handlers = [logging.StreamHandler(_STDOUT_WRAPPER)]

        if log_file:
            handlers.append(logging.FileHandler(log_file, encoding='utf-8'))

        logging.basicConfig(
            level=level, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', handlers=handlers
        )


def main() -> int:
    """Entry point for opt-detector CLI."""
    multiprocessing.freeze_support()
    return OptAction.execute()


if __name__ == '__main__':
    sys.exit(main())
