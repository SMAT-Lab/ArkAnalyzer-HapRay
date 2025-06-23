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
import re
import logging
import argparse
from concurrent.futures import ThreadPoolExecutor

from hapray import VERSION
from hapray.core.config.config import Config
from hapray.core.report import ReportGenerator, create_perf_summary_excel


class UpdateAction:
    """Handles report update actions for existing performance reports."""

    @staticmethod
    def execute(args):
        """Executes report update workflow."""
        parser = argparse.ArgumentParser(
            description='Update existing performance reports',
            prog='ArkAnalyzer-HapRay update')
        parser.add_argument('--report_dir', '-r', required=True,
                            help='Directory containing reports to update')
        parser.add_argument('--so_dir', default=None,
                            help='Directory for symbolicated .so files')
        parser.add_argument(
            '-v', '--version',
            action='version',
            version=f'%(prog)s {VERSION}',
            help="Show program's version number and exit"
        )
        parsed_args = parser.parse_args(args)

        report_dir = os.path.abspath(parsed_args.report_dir)
        so_dir = os.path.abspath(parsed_args.so_dir) if parsed_args.so_dir else None

        if not os.path.exists(report_dir):
            logging.error(f"Report directory not found: {report_dir}")
            return

        logging.info(f"Updating reports in: {report_dir}")
        if so_dir:
            logging.info(f"Using symbolicated .so files from: {so_dir}")
            Config.set('so_dir', so_dir)

        testcase_dirs = UpdateAction.find_testcase_dirs(report_dir)
        if not testcase_dirs:
            logging.error("No valid test case reports found")
            return

        logging.info(f"Found {len(testcase_dirs)} test case reports for updating")
        UpdateAction.process_reports(testcase_dirs, report_dir)

    @staticmethod
    def find_testcase_dirs(report_dir):
        """Identifies valid test case directories in the report directory."""
        testcase_dirs = []
        round_dir_pattern = re.compile(r'.*_round\d$')

        for entry in os.listdir(report_dir):
            if round_dir_pattern.match(entry):
                continue

            full_path = os.path.join(report_dir, entry)
            if os.path.isdir(full_path):
                if all(os.path.exists(os.path.join(full_path, subdir))
                       for subdir in ['hiperf', 'htrace']):
                    testcase_dirs.append(full_path)

        if not testcase_dirs:
            if all(os.path.exists(os.path.join(report_dir, subdir))
                   for subdir in ['hiperf', 'htrace']):
                testcase_dirs.append(report_dir)

        return testcase_dirs

    @staticmethod
    def process_reports(testcase_dirs, report_dir):
        """Processes reports using parallel execution."""
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = []
            report_generator = ReportGenerator()

            for case_dir in testcase_dirs:
                scene_name = os.path.basename(case_dir)
                logging.info(f"Updating report: {scene_name}")
                future = executor.submit(
                    report_generator.update_report,
                    case_dir
                )
                futures.append(future)

            # Monitor completion status
            for future in futures:
                try:
                    if future.result():
                        logging.info("Report updated successfully")
                    else:
                        logging.error("Report update failed")
                except Exception as e:
                    logging.error(f"Error updating report: {str(e)}")

        # Generate summary report
        logging.info("Generating summary Excel report")
        if create_perf_summary_excel(report_dir):
            logging.info("Summary Excel created successfully")
        else:
            logging.error("Failed to create summary Excel")
