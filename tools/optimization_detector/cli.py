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
import os
import sys
from typing import Optional

from optimization_detector import FileCollector, OptimizationDetector, __version__
from optimization_detector.machine_output import (
    build_tool_result,
    default_result_path_for_output_file,
    finalize_contract,
)
from optimization_detector.report_formatters import ReportFormatterFactory

_STDOUT_WRAPPER = None


def _contract_result_path(output_path: str) -> str:
    """契约 JSON 固定与 -o 同目录: dirname(abs(-o))/hapray-tool-result.json"""
    return default_result_path_for_output_file(output_path)


def _build_opt_success_outputs(parsed_args, saved_files: list[str]) -> dict:
    """
    与 save_reports 内 normalize 顺序一致，列出各格式对应的真实报告绝对路径。
    -f 多格式时 reports_by_format 与 report_files 一一对应。
    """
    output_formats = ReportFormatterFactory.normalize_output_formats(parsed_args.format, parsed_args.output)
    abs_paths = [os.path.abspath(p) for p in saved_files]
    reports_by_format = dict(zip(output_formats, abs_paths, strict=False))
    return {
        'input': parsed_args.input,
        'report_files': abs_paths,
        'reports_by_format': reports_by_format,
        'formats': output_formats,
    }


class OptAction:
    """Handles binary optimization analysis actions."""

    @staticmethod
    def _map_output_path_for_macos(path_str: str, subdir: str) -> str:
        """
        macOS 下统一把输出落到用户目录，避免只读目录写入失败。
        Windows/Linux 保持原样。
        """
        if sys.platform != 'darwin':
            return path_str
        root = os.path.join(os.path.expanduser('~'), 'ArkAnalyzer-HapRay', 'optimization_detector', subdir)
        os.makedirs(root, exist_ok=True)
        return os.path.join(root, os.path.basename(path_str))

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
        parser.add_argument(
            '--machine-json',
            action='store_true',
            help='If result file cannot be written or no file path, print one JSON line to stdout; logs go to stderr',
        )

        parsed_args = parser.parse_args()

        # macOS 下无论是否显式传参，都将输出/日志写到用户目录
        parsed_args.output = OptAction._map_output_path_for_macos(parsed_args.output, 'reports')
        if parsed_args.log_file:
            parsed_args.log_file = OptAction._map_output_path_for_macos(parsed_args.log_file, 'logs')

        # 配置日志
        OptAction.setup_logging(parsed_args.verbose, parsed_args.log_file, machine_json=parsed_args.machine_json)

        action = OptAction()
        file_collector = FileCollector()
        try:
            logging.info('Collecting binary files from: %s', parsed_args.input)
            file_infos = file_collector.collect_binary_files(parsed_args.input)

            if not file_infos:
                logging.warning('No valid binary files found')
                payload = build_tool_result(
                    'optimization_detector',
                    success=False,
                    exit_code=1,
                    action='opt',
                    outputs={},
                    error='no_valid_binary_files',
                    tool_version=__version__,
                )
                finalize_contract(
                    payload,
                    result_path=_contract_result_path(parsed_args.output),
                    machine_json=parsed_args.machine_json,
                )
                return 1

            logging.info('Starting optimization detection on %d files', len(file_infos))
            if parsed_args.timeout:
                logging.info('Timeout per file: %d seconds', parsed_args.timeout)
            multiprocessing.freeze_support()
            data = action.run_detection(
                parsed_args.jobs,
                file_infos,
                parsed_args.timeout,
                parsed_args.lto,
                parsed_args.opt,
            )
            # 保存报告到指定格式
            saved_files = ReportFormatterFactory.save_reports(data, parsed_args.format, parsed_args.output)
            payload = build_tool_result(
                'optimization_detector',
                success=True,
                exit_code=0,
                action='opt',
                outputs=_build_opt_success_outputs(parsed_args, saved_files),
                error=None,
                tool_version=__version__,
            )
            finalize_contract(
                payload,
                result_path=_contract_result_path(parsed_args.output),
                machine_json=parsed_args.machine_json,
            )
            return 0
        except Exception as e:
            payload = build_tool_result(
                'optimization_detector',
                success=False,
                exit_code=1,
                action='opt',
                outputs={},
                error=str(e),
                tool_version=__version__,
            )
            finalize_contract(
                payload,
                result_path=_contract_result_path(parsed_args.output),
                machine_json=parsed_args.machine_json,
            )
            if parsed_args.machine_json:
                return 1
            raise
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
    def setup_logging(verbose: bool = False, log_file: Optional[str] = None, machine_json: bool = False):
        """配置日志"""
        level = logging.DEBUG if verbose else logging.INFO
        global _STDOUT_WRAPPER
        if _STDOUT_WRAPPER is None:
            # Use TextIOWrapper to set UTF-8 encoding for stdout
            # Keep reference to prevent the wrapper from being closed
            _STDOUT_WRAPPER = io.TextIOWrapper(
                sys.stdout.buffer, encoding='utf-8', errors='replace', line_buffering=True
            )

        if machine_json:
            _log_stream = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace', line_buffering=True)
        else:
            _log_stream = _STDOUT_WRAPPER

        handlers = [logging.StreamHandler(_log_stream)]

        if log_file:
            handlers.append(logging.FileHandler(log_file, encoding='utf-8'))

        logging.basicConfig(
            level=level, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', handlers=handlers
        )


def main() -> int:
    return OptAction.execute()


if __name__ == '__main__':
    multiprocessing.freeze_support()
    sys.exit(main())
