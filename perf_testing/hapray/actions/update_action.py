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
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor

from hapray import VERSION
from hapray.core.config.config import Config
from hapray.core.report import ReportGenerator, create_perf_summary_excel
from hapray.mode.mode import Mode
from hapray.mode.simple_mode import create_simple_mode_structure


class UpdateAction:
    """Handles report update actions for existing performance reports."""

    @staticmethod
    def execute(args):
        """Executes report update workflow."""
        parser = argparse.ArgumentParser(
            description='Update existing performance reports',
            prog='ArkAnalyzer-HapRay update',
        )
        parser.add_argument(
            '--report_dir',
            '-r',
            required=True,
            help='Directory containing reports to update',
        )
        parser.add_argument('--so_dir', default=None, help='Directory for symbolicated .so files')
        parser.add_argument(
            '-v',
            '--version',
            action='version',
            version=f'%(prog)s {VERSION}',
            help="Show program's version number and exit",
        )
        parser.add_argument(
            '--mode',
            type=int,
            default=Mode.COMMUNITY,
            help=f'select mode {Mode.COMMUNITY} COMMUNITY {Mode.COMPATIBILITY} COMPATIBILITY {Mode.SIMPLE} SIMPLE',
        )
        parser.add_argument(
            '--perfs',
            nargs='+',
            default=[],
            help='SIMPLE mode need perf paths (supports multiple files)',
        )
        parser.add_argument(
            '--traces',
            nargs='+',
            default=[],
            help='SIMPLE mode need trace paths (supports multiple files)',
        )
        parser.add_argument(
            '--package-name',
            default='',
            help='SIMPLE mode need package name',
        )
        parser.add_argument(
            '--pids', nargs='+', type=int, default=[], help='SIMPLE mode可选填pids（提供整数ID列表，如: --pids 1 2 3）'
        )
        parser.add_argument(
            '--steps', default='', help='SIMPLE mode可选填steps.json文件路径，如果提供则使用该文件而不是自动生成'
        )
        parser.add_argument(
            '--time-ranges',
            nargs='*',
            default=[],
            help='可选的时间范围过滤，格式为 "startTime-endTime"（纳秒），支持多个时间范围，如: --time-ranges "1000000000-2000000000" "3000000000-4000000000"',
        )
        parsed_args = parser.parse_args(args)

        report_dir = os.path.abspath(parsed_args.report_dir)
        so_dir = os.path.abspath(parsed_args.so_dir) if parsed_args.so_dir else None

        Config.set('mode', parsed_args.mode)
        if not os.path.exists(report_dir) and Config.get('mode') == Mode.COMMUNITY:
            logging.error('Report directory not found: %s', report_dir)
            return
        if Config.get('mode') == Mode.SIMPLE:
            # 简单模式构造目录
            perf_paths = parsed_args.perfs
            trace_paths = parsed_args.traces
            pids = parsed_args.pids

            if not perf_paths or not trace_paths:
                logging.error('SIMPLE mode requires both --perfs and --traces parameters')
                return

            if not parsed_args.package_name:
                logging.error('SIMPLE mode requires --package_name parameter')
                return

            package_name = parsed_args.package_name
            steps_file_path = parsed_args.steps
            timestamp = time.strftime('%Y%m%d%H%M%S', time.localtime(time.time()))
            report_dir = os.path.join(report_dir, timestamp)
            create_simple_mode_structure(
                report_dir, perf_paths, trace_paths, package_name, pids=pids, steps_file_path=steps_file_path
            )
        logging.info('Updating reports in: %s', report_dir)
        if so_dir:
            logging.info('Using symbolicated .so files from: %s', so_dir)
            Config.set('so_dir', so_dir)

        testcase_dirs = UpdateAction.find_testcase_dirs(report_dir)
        if not testcase_dirs:
            logging.error('No valid test case reports found')
            return

        # Parse time ranges
        time_ranges = UpdateAction.parse_time_ranges(parsed_args.time_ranges)
        if time_ranges:
            logging.info('Using %d time range filters', len(time_ranges))
            for i, tr in enumerate(time_ranges):
                logging.info('Time range %d: %d - %d nanoseconds', i + 1, tr['startTime'], tr['endTime'])

        logging.info('Found %d test case reports for updating', len(testcase_dirs))
        UpdateAction.process_reports(testcase_dirs, report_dir, time_ranges)

    @staticmethod
    def find_testcase_dirs(report_dir):
        """Identifies valid test case directories in the report directory."""
        testcase_dirs = []
        round_dir_pattern = re.compile(r'.*_round\d$')

        for entry in os.listdir(report_dir):
            if round_dir_pattern.match(entry):
                continue

            full_path = os.path.join(report_dir, entry)
            if os.path.isdir(full_path) and all(
                os.path.exists(os.path.join(full_path, subdir)) for subdir in ['hiperf', 'htrace']
            ):
                testcase_dirs.append(full_path)

        if not testcase_dirs and all(
            os.path.exists(os.path.join(report_dir, subdir)) for subdir in ['hiperf', 'htrace']
        ):
            testcase_dirs.append(report_dir)

        return testcase_dirs

    @staticmethod
    def parse_time_ranges(time_range_strings: list[str]) -> list[dict]:
        """Parse time range strings into structured format.

        Args:
            time_range_strings: List of time range strings in format "startTime-endTime"

        Returns:
            List of time range dictionaries with 'startTime' and 'endTime' keys
        """
        time_ranges = []
        for time_range_str in time_range_strings:
            try:
                if '-' not in time_range_str:
                    logging.error('Invalid time range format: %s. Expected format: "startTime-endTime"', time_range_str)
                    continue

                start_str, end_str = time_range_str.split('-', 1)
                start_time = int(start_str.strip())
                end_time = int(end_str.strip())

                if start_time >= end_time:
                    logging.error(
                        'Invalid time range: start time (%d) must be less than end time (%d)', start_time, end_time
                    )
                    continue

                time_ranges.append({'startTime': start_time, 'endTime': end_time})

            except ValueError as e:
                logging.error('Failed to parse time range "%s": %s', time_range_str, str(e))
                continue

        return time_ranges

    @staticmethod
    def process_reports(testcase_dirs, report_dir, time_ranges: list[dict] = None):
        """Processes reports using parallel execution."""
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = []
            report_generator = ReportGenerator()

            for case_dir in testcase_dirs:
                scene_name = os.path.basename(case_dir)
                logging.info('Updating report: %s', scene_name)
                if time_ranges:
                    logging.info('Using time ranges for %s: %s', scene_name, time_ranges)
                future = executor.submit(report_generator.update_report, case_dir, time_ranges)
                futures.append(future)

            # Monitor completion status
            for future in futures:
                try:
                    if future.result():
                        logging.info('Report updated successfully')
                    else:
                        logging.error('Report update failed')
                except Exception as e:
                    logging.error('Error updating report: %s', str(e))

        # Generate summary report
        logging.info('Generating summary Excel report')
        if create_perf_summary_excel(report_dir):
            logging.info('Summary Excel created successfully')
        else:
            logging.error('Failed to create summary Excel')
