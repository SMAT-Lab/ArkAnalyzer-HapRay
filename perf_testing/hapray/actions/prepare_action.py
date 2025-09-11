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
import tempfile
from typing import Optional

from xdevice.__main__ import main_process

from hapray import VERSION
from hapray.core.common.common_utils import CommonUtils
from hapray.core.config.config import Config
from hapray.core.dsl.dsl_test_runner import DSLTestRunner

ENV_ERR_STR = """
The hdc or node command is not in PATH.
Please Download Command Line Tools for HarmonyOS(https://developer.huawei.com/consumer/cn/download/),
then add the following directories to PATH.
    $command_line_tools/tool/node/ (for Windows)
    $command_line_tools/tool/node/bin (for Mac/Linux)
    $command_line_tools/sdk/default/openharmony/toolchains (for ALL)
"""


def check_env() -> bool:
    """Verify required commands are in PATH"""
    return bool(shutil.which('hdc') and shutil.which('node'))


class PrepareAction:
    """Simplified test execution for preparation purposes"""

    def __init__(self, device_sn: Optional[str] = None):
        self.device_sn = device_sn or self._detect_device()
        logging.info('Using device: %s', self.device_sn or 'default')

    def _detect_device(self) -> Optional[str]:
        """Detect connected HarmonyOS device"""
        try:
            result = os.popen('hdc list targets').read()
            devices = [line.split('\t')[0] for line in result.splitlines() if line.strip()]
            if devices:
                return devices[0]  # Use first available device
        except Exception:
            logging.warning('⚠️ Device detection failed, using default device')
        return None

    @staticmethod
    def get_matched_cases(run_testcases: list[str], all_testcases: dict) -> list[str]:
        """Match test case patterns against available test cases"""
        matched_cases = []
        for pattern in run_testcases:
            try:
                regex = re.compile(pattern)
                matched_cases.extend(case_name for case_name in all_testcases if regex.match(case_name))
            except re.error as e:
                logging.error('Invalid regex pattern: %s, error: %s', pattern, str(e))
                if pattern in all_testcases:
                    matched_cases.append(pattern)
        return matched_cases

    @staticmethod
    def find_0000_cases(all_testcases: dict) -> list[str]:
        """Find all test cases ending with _0000"""
        return [case_name for case_name in all_testcases if case_name.endswith('_0000')]

    def execute_testcase(self, case_name: str, all_testcases: dict) -> bool:
        """Execute a single test case without complex folder structure"""
        try:
            case_dir, file_extension = all_testcases[case_name]

            # Create a temporary output directory for this execution
            with tempfile.TemporaryDirectory(prefix=f'prepare_{case_name}_') as temp_output:
                logging.info('Executing test case: %s', case_name)
                logging.info('Temporary output: %s', temp_output)

                device_arg = f'-sn {self.device_sn}' if self.device_sn else ''
                command = f'run -l {case_name} {device_arg} -tcpath {case_dir} -rp {temp_output}'

                if file_extension == '.py':
                    # Execute Python test case
                    main_process(command)
                else:
                    # Execute DSL test case (YAML)
                    DSLTestRunner.run_testcase(
                        f'{case_dir}/{case_name}{file_extension}', temp_output, device_id=self.device_sn
                    )

                logging.info('✅ Test case completed: %s', case_name)
                return True

        except Exception as e:
            logging.error('❌ Test case failed: %s | Error: %s', case_name, str(e))
            return False

    def run(self, run_testcases: Optional[list[str]] = None, run_all_0000: bool = False):
        """Main execution flow for preparation testing"""
        all_testcases = CommonUtils.load_all_testcases()

        if run_all_0000:
            # Execute all _0000 test cases
            matched_cases = self.find_0000_cases(all_testcases)
            logging.info('Found %d test cases ending with _0000', len(matched_cases))
        elif run_testcases:
            # Execute specified test cases
            matched_cases = self.get_matched_cases(run_testcases, all_testcases)
        else:
            logging.error('No test cases specified for execution')
            return

        if not matched_cases:
            logging.error('No test cases matched the input patterns')
            return

        logging.info('Starting execution | Device: %s | Cases: %d', self.device_sn or 'default', len(matched_cases))

        # Execute test cases sequentially
        success_count = 0
        for case_name in matched_cases:
            if self.execute_testcase(case_name, all_testcases):
                success_count += 1

        # Summary
        logging.info('Execution completed: %d/%d test cases succeeded', success_count, len(matched_cases))

    @staticmethod
    def execute(args) -> bool:
        """Execute preparation testing workflow"""
        if '--multiprocessing-fork' in args:
            return False

        if not check_env():
            logging.error(ENV_ERR_STR)
            return False

        parser = argparse.ArgumentParser(
            description='Simplified Test Execution for Preparation', prog='ArkAnalyzer-HapRay prepare'
        )

        parser.add_argument(
            '-v',
            '--version',
            action='version',
            version=f'%(prog)s {VERSION}',
            help="Show program's version number and exit",
        )

        parser.add_argument(
            '--run_testcases', nargs='+', default=None, help='Test cases to execute (regex patterns supported)'
        )

        parser.add_argument('--all_0000', action='store_true', help='Execute all test cases ending with _0000')

        parser.add_argument('--device', type=str, default=None, help='Device serial number (e.g., HX1234567890)')

        parsed_args = parser.parse_args(args)

        # Validate arguments
        if not parsed_args.run_testcases and not parsed_args.all_0000:
            logging.error('Must specify either --run_testcases or --all_0000')
            return False

        # Update configuration based on arguments
        if parsed_args.run_testcases:
            Config.set('run_testcases', parsed_args.run_testcases)

        action = PrepareAction(device_sn=parsed_args.device)
        action.run(run_testcases=parsed_args.run_testcases, run_all_0000=parsed_args.all_0000)

        return True


if __name__ == '__main__':
    import sys

    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    PrepareAction.execute(sys.argv[1:])
