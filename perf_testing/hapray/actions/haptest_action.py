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
import shutil
import time
import traceback
from typing import Optional

from xdevice.__main__ import main_process

from hapray import VERSION
from hapray.core.config.config import Config
from hapray.core.report import ReportGenerator

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


class HapTestAction:
    """Strategy-driven UI automation with performance capture"""

    @staticmethod
    def execute(args) -> Optional[str]:
        """Execute HapTest automation

        Args:
            args: Command line arguments

        Returns:
            Report path if successful, None otherwise
        """
        if '--multiprocessing-fork' in args:
            return None

        if not check_env():
            logging.error(ENV_ERR_STR)
            return None

        parser = argparse.ArgumentParser(
            description='Strategy-driven UI automation with perf/trace capture', prog='ArkAnalyzer-HapRay haptest'
        )

        parser.add_argument(
            '-v',
            '--version',
            action='version',
            version=f'%(prog)s {VERSION}',
            help="Show program's version number and exit",
        )

        parser.add_argument(
            '--app-package', type=str, required=True, help='Target application package name (e.g., com.example.app)'
        )

        parser.add_argument('--app-name', type=str, required=True, help='Readable application name (e.g., "示例应用")')

        parser.add_argument(
            '--ability-name', type=str, default=None, help='Main ability name (optional, auto-detect if not specified)'
        )

        parser.add_argument(
            '--strategy',
            type=str,
            default='depth_first',
            choices=['depth_first', 'breadth_first', 'random'],
            help='Exploration strategy: depth_first (default), breadth_first, random',
        )

        parser.add_argument('--max-steps', type=int, default=30, help='Maximum exploration steps (default: 30)')

        parser.add_argument('--round', type=int, default=1, help='Number of test rounds (default: 1)')

        parser.add_argument(
            '--devices', nargs='+', default=None, help='Device serial numbers (e.g., HX1234567890 HX0987654321)'
        )

        parser.add_argument(
            '--trace', dest='trace', action='store_true', default=True, help='Enable trace capture (default: True)'
        )

        parser.add_argument('--no-trace', dest='trace', action='store_false', help='Disable trace capture')

        parser.add_argument('--memory', action='store_true', help='Enable memory profiling')

        parser.add_argument('--no-perf', action='store_true', help='Disable perf capture (memory-only mode)')

        parsed = parser.parse_args(args)

        Config.set('trace.enable', parsed.trace)
        Config.set('memory.enable', parsed.memory)
        if parsed.no_perf:
            Config.set('hiperf.disabled', True)

        root_path = os.getcwd()
        timestamp = time.strftime('%Y%m%d%H%M%S', time.localtime(time.time()))
        reports_path = os.path.join(root_path, 'reports', f'haptest_{parsed.app_package}_{timestamp}')
        os.makedirs(reports_path, exist_ok=True)

        logging.info('=' * 60)
        logging.info('Starting HapTest Automation')
        logging.info('=' * 60)
        logging.info('Application: %s (%s)', parsed.app_name, parsed.app_package)
        logging.info('Strategy: %s', parsed.strategy)
        logging.info('Max Steps: %d', parsed.max_steps)
        logging.info('Rounds: %d', parsed.round)
        logging.info('Trace: %s', 'Enabled' if parsed.trace else 'Disabled')
        logging.info('Memory: %s', 'Enabled' if parsed.memory else 'Disabled')
        logging.info('Perf: %s', 'Disabled' if parsed.no_perf else 'Enabled')
        logging.info('Reports Path: %s', reports_path)
        logging.info('=' * 60)

        runner = HapTestRunner(
            reports_path=reports_path,
            app_package=parsed.app_package,
            app_name=parsed.app_name,
            ability_name=parsed.ability_name,
            strategy_type=parsed.strategy,
            max_steps=parsed.max_steps,
            test_round=parsed.round,
            devices=parsed.devices,
        )

        success = runner.run()

        if success:
            logging.info('=' * 60)
            logging.info('HapTest Automation Completed Successfully')
            logging.info('Reports: %s', reports_path)
            logging.info('=' * 60)
            return reports_path
        logging.error('HapTest Automation Failed')
        return None


class HapTestRunner:
    """Executes HapTest automation with xDevice framework"""

    def __init__(
        self,
        reports_path: str,
        app_package: str,
        app_name: str,
        ability_name: Optional[str],
        strategy_type: str,
        max_steps: int,
        test_round: int,
        devices: Optional[list] = None,
    ):
        self.reports_path = reports_path
        self.app_package = app_package
        self.app_name = app_name
        self.ability_name = ability_name
        self.strategy_type = strategy_type
        self.max_steps = max_steps
        self.test_round = test_round
        self.devices = devices or []

        self._create_test_case()

    def _create_test_case(self):
        """Dynamically create HapTest case file and JSON config"""
        case_dir = os.path.join(os.path.dirname(__file__), '..', 'testcases', '__haptest_generated__')
        os.makedirs(case_dir, exist_ok=True)

        case_name = f'HapTest_{self.app_package.replace(".", "_")}'
        case_file = os.path.join(case_dir, f'{case_name}.py')
        json_file = os.path.join(case_dir, f'{case_name}.json')

        case_content = f'''"""
Auto-generated HapTest case
Application: {self.app_name} ({self.app_package})
Strategy: {self.strategy_type}
Max Steps: {self.max_steps}
"""

from hapray.haptest import HapTest


class {case_name}(HapTest):
    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(
            tag=self.TAG,
            configs=controllers,
            app_package='{self.app_package}',
            app_name='{self.app_name}',
            ability_name={repr(self.ability_name)},
            strategy_type='{self.strategy_type}',
            max_steps={self.max_steps}
        )
'''

        json_content = f'''{{
    "description": "Auto-generated HapTest for {self.app_name} ({self.app_package})",
    "environment": [
        {{
            "type": "device",
            "label": "phone"
        }}
    ],
    "driver": {{
        "type": "DeviceTest",
        "py_file": [
            "{case_name}.py"
        ]
    }},
    "kits": [
    ]
}}
'''

        with open(case_file, 'w', encoding='utf-8') as f:
            f.write(case_content)

        with open(json_file, 'w', encoding='utf-8') as f:
            f.write(json_content)

        init_file = os.path.join(case_dir, '__init__.py')
        if not os.path.exists(init_file):
            with open(init_file, 'w', encoding='utf-8') as f:
                f.write('"""Auto-generated HapTest cases"""')

        self.case_name = case_name
        self.case_dir = case_dir

        logging.info('Created test case: %s', case_file)
        logging.info('Created JSON config: %s', json_file)

    def run(self) -> bool:
        """Execute test rounds and generate reports"""
        try:
            scene_round_dirs = []

            for round_num in range(self.test_round):
                logging.info('\n' + '=' * 60)
                logging.info('Starting Round %d/%d', round_num + 1, self.test_round)
                logging.info('=' * 60)

                if self.test_round > 1:
                    output_dir = os.path.join(self.reports_path, f'{self.case_name}_round{round_num}')
                else:
                    output_dir = os.path.join(self.reports_path, self.case_name)

                device_arg = ''
                if self.devices:
                    device_arg = f'-sn {self.devices[0]}'

                command = f'run -l {self.case_name} {device_arg} -tcpath {self.case_dir} -rp {output_dir}'

                logging.info('Executing: xdevice %s', command)
                main_process(command)

                self._wait_for_completion(output_dir)

                if os.path.exists(output_dir):
                    scene_round_dirs.append(output_dir)
                    logging.info('Round %d completed: %s', round_num + 1, output_dir)
                else:
                    logging.error('Round %d failed: output directory not found', round_num + 1)

            if scene_round_dirs:
                self._generate_reports(scene_round_dirs)
                return True
            logging.error('All test rounds failed')
            return False

        except Exception as e:
            logging.error('HapTest execution failed: %s', str(e))
            return False

    def _wait_for_completion(self, output_dir: str):
        """Wait for test case to complete"""
        max_wait = 30
        for _i in range(max_wait):
            if os.path.exists(os.path.join(output_dir, 'testInfo.json')):
                logging.info('Test case completed')
                return
            time.sleep(2)

        logging.warning('Test case completion timeout after %d seconds', max_wait * 2)

    def _generate_reports(self, scene_round_dirs: list):
        """Generate analysis reports"""
        logging.info('\n' + '=' * 60)
        logging.info('Generating Analysis Reports')
        logging.info('=' * 60)

        try:
            merge_folder_path = os.path.join(self.reports_path, self.case_name)
            report_generator = ReportGenerator()

            logging.info('Generating report for: %s', self.case_name)
            logging.info('Scene directories: %s', scene_round_dirs)
            logging.info('Output path: %s', merge_folder_path)

            success = report_generator.generate_report(scene_round_dirs, merge_folder_path)

            if success:
                logging.info('Reports generated successfully')
                logging.info('Report location: %s/report/hapray_report.html', merge_folder_path)
            else:
                logging.error('Report generation failed')
        except Exception as e:
            logging.error('Report generation failed: %s', str(e))
            logging.error(traceback.format_exc())


if __name__ == '__main__':
    import sys

    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    HapTestAction.execute(sys.argv[1:])
