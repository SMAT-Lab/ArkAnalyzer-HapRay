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
import shutil
import time
from concurrent.futures import ThreadPoolExecutor
from typing import List, Optional

from xdevice.__main__ import main_process

from hapray import VERSION
from hapray.core.common.common_utils import CommonUtils
from hapray.core.common.folder_utils import scan_folders, delete_folder
from hapray.core.config.config import Config
from hapray.core.dsl.dsl_test_runner import DSLTestRunner
from hapray.core.report import ReportGenerator, create_perf_summary_excel

ENV_ERR_STR = """
The hdc or node command is not in PATH.
Please Download Command Line Tools for HarmonyOS(https://developer.huawei.com/consumer/cn/download/),
then add the following directories to PATH.
    $command_line_tools/tool/node/ (for Windows)
    $command_line_tools/tool/node/bin (for Mac/Linux)
    $command_line_tools/sdk/default/openharmony/toolchains (for ALL)
"""


def check_env() -> bool:
    if shutil.which('hdc') and shutil.which('node'):
        return True
    return False


class PerfAction:
    """Handles performance testing actions including test case execution and report generation."""

    @staticmethod
    def get_matched_cases(run_testcases: List[str], all_testcases: dict) -> List[str]:
        """Matches test case patterns against available test cases."""
        matched_cases = []
        for pattern in run_testcases:
            try:
                regex = re.compile(pattern)
                for case_name in all_testcases.keys():
                    if regex.match(case_name):
                        matched_cases.append(case_name)
            except re.error as e:
                logging.error(f"Invalid regex pattern: {pattern}, error: {e}")
                if pattern in all_testcases:
                    matched_cases.append(pattern)
        return matched_cases

    @staticmethod
    def execute(args) -> Optional[str]:
        """Executes performance testing workflow."""
        if not check_env():
            logging.error(ENV_ERR_STR)
            return

        parser = argparse.ArgumentParser(
            description='Code-oriented Performance Analysis for OpenHarmony Apps',
            prog='ArkAnalyzer-HapRay perf')

        parser.add_argument(
            '-v', '--version',
            action='version',
            version=f'%(prog)s {VERSION}',
            help="Show program's version number and exit"
        )

        parser.add_argument('--so_dir', default=None, help='Directory for symbolicated .so files')
        parser.add_argument('--run_testcases', nargs='+', default=None, help='Test cases to execute')
        parser.add_argument('--circles', action="store_true", help="Enable CPU cycle sampling")
        parser.add_argument('--round', type=int, default=5, help="Specify test round")
        parser.add_argument('--no-trace', action='store_true', help="Disable trace capturing")
        parsed_args = parser.parse_args(args)

        root_path = os.getcwd()
        timestamp = time.strftime('%Y%m%d%H%M%S', time.localtime(time.time()))
        reports_path = os.path.join(root_path, 'reports', timestamp)
        os.makedirs(reports_path, exist_ok=True)
        logging.info(f"Reports will be saved to: {reports_path}")

        if parsed_args.run_testcases is not None:
            Config.set('run_testcases', parsed_args.run_testcases)

        if parsed_args.circles:
            Config.set('hiperf.event', 'raw-cpu-cycles')

        if parsed_args.no_trace:
            Config.set('trace.enable', False)
        else:
            Config.set('trace.enable', True)

        all_testcases = CommonUtils.load_all_testcases()

        if parsed_args.so_dir is not None:
            Config.set('so_dir', parsed_args.so_dir)

        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = []
            report_generator = ReportGenerator()
            run_testcases = Config.get('run_testcases', [])

            if not run_testcases:
                logging.error('No test cases specified for execution')
                return

            matched_cases = PerfAction.get_matched_cases(run_testcases, all_testcases)
            if not matched_cases:
                logging.error('No test cases matched the input patterns')
                return

            logging.info(f"Found {len(matched_cases)} test cases for execution")

            for case_name in matched_cases:
                scene_round_dirs = PerfAction.run_testcase(case_name, reports_path, all_testcases, parsed_args.round)
                merge_folder_path = os.path.join(reports_path, case_name)
                future = executor.submit(
                    report_generator.generate_report,
                    scene_round_dirs,
                    merge_folder_path
                )
                futures.append(future)

            # Wait for all report generation tasks
            for future in futures:
                future.result()

            # Generate summary Excel
            logging.info("Creating summary Excel report...")
            if create_perf_summary_excel(reports_path):
                logging.info("Summary Excel created successfully")
            else:
                logging.error("Failed to create summary Excel")

            return reports_path

    @staticmethod
    def run_testcase(case_name: str, reports_path: str, all_testcases: dict, _round: int) -> List[str]:
        scene_round_dirs = []
        for round_num in range(_round):
            case_dir, file_extension = all_testcases[case_name]
            output = os.path.join(reports_path, f'{case_name}_round{round_num}')

            if file_extension == '.py':
                main_process(f'run -l {case_name} -tcpath {case_dir} -rp {output}')
            else:
                DSLTestRunner.run_testcase(f'{case_dir}/{case_name}{file_extension}', output)

            # Verify and retry if data is incomplete
            for attempt in range(5):
                if scan_folders(output):
                    scene_round_dirs.append(output)
                    break
                else:
                    if delete_folder(output):
                        logging.warning(f'Incomplete perf.data, retrying ({attempt + 1}/5) for {output}')
                        if file_extension == '.py':
                            main_process(f'run -l {case_name} -tcpath {case_dir} -rp {output}')
                        else:
                            DSLTestRunner.run_testcase(f'{case_dir}/{case_name}.{file_extension}', output)
        return scene_round_dirs
