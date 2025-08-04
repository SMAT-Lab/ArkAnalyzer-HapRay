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
import queue
import re
import shutil
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Optional, Dict

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
    """Verify required commands are in PATH"""
    return bool(shutil.which('hdc') and shutil.which('node'))


class DeviceManager:
    """Manages a pool of HarmonyOS devices for parallel execution"""

    def __init__(self, device_list: List[str]):
        self.available_devices = queue.Queue()
        self._init_devices(device_list)

    def _init_devices(self, device_list: List[str]):
        """Initialize device pool"""
        if not device_list:
            raise ValueError("Device list cannot be empty")
        for device in device_list:
            self.available_devices.put(device)

    def acquire_device(self) -> str:
        """Get an available device from the pool"""
        return self.available_devices.get()

    def release_device(self, device: str):
        """Return device to the pool"""
        self.available_devices.put(device)

    def get_device_count(self) -> int:
        """Get total number of available devices"""
        return self.available_devices.qsize()


class DeviceBoundTestRunner:
    """Executes test cases on bound devices"""

    def __init__(self, device_manager: DeviceManager, reports_path: str, test_round: int):
        self.device_manager = device_manager
        self.reports_path = reports_path
        self.round = test_round

    def execute_testcase(self, case_name: str, all_testcases: Dict) -> List[str]:
        """Execute a test case on a bound device for multiple rounds"""
        device_sn = self.device_manager.acquire_device()
        logging.info("Device bound: %s -> %s", case_name, device_sn)
        scene_round_dirs = []

        for round_num in range(self.round):
            output_dir = self._run_single_round(case_name, all_testcases, device_sn, round_num)
            scene_round_dirs.append(output_dir)

        self.device_manager.release_device(device_sn)
        logging.info("Device released: %s", device_sn)

        return scene_round_dirs

    def _run_single_round(self, case_name: str, all_testcases: Dict,
                          device_sn: str, round_num: int) -> str:
        """Execute a single test round on bound device"""
        case_dir, file_extension = all_testcases[case_name]
        output_dir = os.path.join(self.reports_path, f"{case_name}_round{round_num}")
        device_arg = f"-sn {device_sn}" if device_sn else ""
        command = f'run -l {case_name} {device_arg} -tcpath {case_dir} -rp {output_dir}'

        if file_extension == '.py':
            main_process(command)
        else:
            DSLTestRunner.run_testcase(
                f'{case_dir}/{case_name}{file_extension}',
                output_dir,
                device_id=device_sn
            )

        for attempt in range(5):
            self._wait_for_completion()
            if scan_folders(output_dir):
                break

            if delete_folder(output_dir):
                logging.warning('Incomplete perf.data, retrying (%d/5) for %s', attempt + 1, output_dir)
                if file_extension == '.py':
                    main_process(command)
                else:
                    DSLTestRunner.run_testcase(f'{case_dir}/{case_name}{file_extension}',
                                               output_dir, device_id=device_sn)
        return output_dir

    def _wait_for_completion(self):
        for _ in range(5):
            if os.path.exists(os.path.join(self.reports_path, 'testInfo.json')):
                break
            else:
                time.sleep(5)


class ParallelReportGenerator:
    """Manages parallel report generation using thread pool"""

    def __init__(self, reports_path: str):
        self.reports_path = reports_path
        self.executor = ThreadPoolExecutor(max_workers=os.cpu_count() or 4)
        self.futures = {}
        self.results = {}
        self.lock = threading.Lock()

    def submit_report_task(self, report_generator: ReportGenerator,
                           scene_round_dirs: List[str], case_name: str):
        """Submit a report generation task to the executor"""
        merge_folder_path = os.path.join(self.reports_path, case_name)
        future = self.executor.submit(
            self._generate_report_safely,
            report_generator,
            scene_round_dirs,
            merge_folder_path,
            case_name
        )
        with self.lock:
            self.futures[future] = case_name

    def _generate_report_safely(self, report_generator: ReportGenerator,
                                scene_round_dirs: List[str],
                                merge_folder_path: str,
                                case_name: str) -> bool:
        """Generate report with error handling"""
        try:
            report_generator.generate_report(scene_round_dirs, merge_folder_path)
            return True
        except Exception as e:
            logging.error("Report generation failed: %s | Error: %s", case_name, str(e))
            return False

    def wait_completion(self):
        """Wait for all report tasks to complete and collect results"""
        for future in as_completed(self.futures):
            case_name = self.futures[future]
            try:
                success = future.result()
                with self.lock:
                    self.results[case_name] = success
                status = "completed" if success else "failed"
                logging.info("Report %s: %s", status, case_name)
            except Exception as e:
                with self.lock:
                    self.results[case_name] = False
                logging.error("Report task exception: %s | Error: %s", case_name, str(e))

    def shutdown(self):
        """Shutdown the report generator executor"""
        self.executor.shutdown(wait=True)

    def get_results(self) -> Dict[str, bool]:
        """Get report generation results"""
        return self.results


class PerfAction:
    """Handles performance testing execution and reporting"""

    def __init__(self, reports_path: str, test_round: int, devices: Optional[List[str]] = None):
        self.reports_path = reports_path
        self.round = test_round
        self.devices = devices or self._detect_devices()
        os.makedirs(reports_path, exist_ok=True)

        # Initialize device manager
        self.device_manager = DeviceManager(self.devices)
        logging.info("Device pool initialized: %d devices available", len(self.devices))

        # Initialize parallel reporter
        self.report_generator = ReportGenerator()
        self.parallel_reporter = ParallelReportGenerator(reports_path)

    def _detect_devices(self) -> List[str]:
        """Detect connected HarmonyOS devices"""
        try:
            result = os.popen("hdc list targets").read()
            return [
                line.split('\t')[0]
                for line in result.splitlines()
            ]
        except Exception:
            logging.warning("⚠️ Device detection failed, using default device")
            return []

    @staticmethod
    def get_matched_cases(run_testcases: List[str], all_testcases: Dict) -> List[str]:
        """Match test case patterns against available test cases"""
        matched_cases = []
        for pattern in run_testcases:
            try:
                regex = re.compile(pattern)
                matched_cases.extend(
                    case_name for case_name in all_testcases.keys()
                    if regex.match(case_name)
                )
            except re.error as e:
                logging.error("Invalid regex pattern: %s, error: %s", pattern, str(e))
                if pattern in all_testcases:
                    matched_cases.append(pattern)
        return matched_cases

    @staticmethod
    def execute(args) -> Optional[str]:
        """Execute performance testing workflow"""
        if "--multiprocessing-fork" in args:
            return None
        
        if not check_env():
            logging.error(ENV_ERR_STR)
            return None

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
        parser.add_argument('--round', type=int, default=5, help="Number of test rounds")
        parser.add_argument('--no-trace', action='store_true', help="Disable trace capturing")
        parser.add_argument('--devices', nargs='+', default=None, help='Device serial numbers (e.g., HX1234567890)')

        parsed_args = parser.parse_args(args)
        root_path = os.getcwd()
        timestamp = time.strftime('%Y%m%d%H%M%S', time.localtime(time.time()))
        reports_path = os.path.join(root_path, 'reports', timestamp)
        logging.info("Reports will be saved to: %s", reports_path)

        # Update configuration based on arguments
        if parsed_args.run_testcases:
            Config.set('run_testcases', parsed_args.run_testcases)
        if parsed_args.circles:
            Config.set('hiperf.event', 'raw-cpu-cycles')
        if parsed_args.so_dir is not None:
            Config.set('so_dir', parsed_args.so_dir)
        Config.set('trace.enable', not parsed_args.no_trace)

        action = PerfAction(reports_path, parsed_args.round, devices=parsed_args.devices)
        action.run()

        return reports_path

    def run(self):
        """Main execution flow for performance testing"""
        all_testcases = CommonUtils.load_all_testcases()
        run_testcases = Config.get('run_testcases', [])

        # Validate input
        if not run_testcases:
            logging.error('No test cases specified for execution')
            return

        matched_cases = self.get_matched_cases(run_testcases, all_testcases)
        if not matched_cases:
            logging.error('No test cases matched the input patterns')
            return

        logging.info("Found %d test cases for execution", len(matched_cases))
        logging.info("Starting execution | Devices: %d | Cases: %d", len(self.devices), len(matched_cases))

        # Initialize test runner
        test_runner = DeviceBoundTestRunner(
            self.device_manager,
            self.reports_path,
            self.round
        )

        # Execute tests in parallel
        with ThreadPoolExecutor(max_workers=len(self.devices)) as executor:
            futures = {
                executor.submit(
                    self._execute_and_report,
                    test_runner,
                    case_name,
                    all_testcases
                ): case_name
                for case_name in matched_cases
            }

            # Process results
            for future in as_completed(futures):
                case_name = futures[future]
                try:
                    future.result()
                    logging.info("Test completed: %s", case_name)
                except Exception as e:
                    logging.error("Test failed: %s | Error: %s", case_name, str(e))

        # Finalize reporting
        self._finalize_reporting()

    def _execute_and_report(self, test_runner: DeviceBoundTestRunner,
                            case_name: str, all_testcases: Dict):
        """Execute test and submit report generation task"""
        scene_round_dirs = test_runner.execute_testcase(case_name, all_testcases)
        logging.info("Test rounds completed: %s | Rounds: %d", case_name, len(scene_round_dirs))

        # Submit report generation
        self.parallel_reporter.submit_report_task(
            self.report_generator,
            scene_round_dirs,
            case_name
        )

    def _finalize_reporting(self):
        """Finalize report generation and create summary"""
        self.parallel_reporter.wait_completion()
        self.parallel_reporter.shutdown()

        # Generate summary report
        logging.info("Creating summary Excel report...")
        if create_perf_summary_excel(self.reports_path):
            logging.info("Summary Excel created successfully")
        else:
            logging.error("Failed to create summary Excel")

        # Report generation statistics
        report_results = self.parallel_reporter.get_results()
        success_count = sum(1 for success in report_results.values() if success)
        logging.info("Report generation stats: %d/%d succeeded", success_count, len(report_results))
