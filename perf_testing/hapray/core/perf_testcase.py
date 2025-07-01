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

import json
import os
import threading
import time
from abc import ABC, abstractmethod

from devicetest.core.test_case import TestCase
from hypium import UiDriver
from xdevice import platform_logger

from hapray.core.config.config import Config

Log = platform_logger("PerfTestCase")

# Template for basic performance collection command
_PERF_CMD_TEMPLATE = (
    '{cmd} {pids} --call-stack dwarf --kernel-callchain -f 1000 '
    '--cpu-limit 100 -e {event} --enable-debuginfo-symbolic '
    '--clockid boottime -m 1024 -d {duration} {output_path}'
)

# Template for combined trace and performance collection command
_TRACE_PERF_CMD_TEMPLATE = """hiprofiler_cmd \\
  -c - \\
  -o {output_path}.htrace \\
  -t {duration} \\
  -s \\
  -k \\
<<CONFIG
# Session configuration
 request_id: 1
 session_config {{
  buffers {{
   pages: 16384
  }}
 }}

# ftrace plugin configuration
 plugin_configs {{
  plugin_name: "ftrace-plugin"
  sample_interval: 1000
  config_data {{
   # ftrace events
   ftrace_events: "sched/sched_switch"
   ftrace_events: "power/suspend_resume"
   ftrace_events: "sched/sched_wakeup"
   ftrace_events: "sched/sched_wakeup_new"
   ftrace_events: "sched/sched_waking"
   ftrace_events: "sched/sched_process_exit"
   ftrace_events: "sched/sched_process_free"
   ftrace_events: "task/task_newtask"
   ftrace_events: "task/task_rename"
   ftrace_events: "power/cpu_frequency"
   ftrace_events: "power/cpu_idle"

   # hitrace categories
   hitrace_categories: "ability"
   hitrace_categories: "ace"
   hitrace_categories: "app"
   hitrace_categories: "ark"
   hitrace_categories: "binder"
   hitrace_categories: "disk"
   hitrace_categories: "freq"
   hitrace_categories: "graphic"
   hitrace_categories: "idle"
   hitrace_categories: "irq"
   hitrace_categories: "memreclaim"
   hitrace_categories: "mmc"
   hitrace_categories: "multimodalinput"
   hitrace_categories: "notification"
   hitrace_categories: "ohos"
   hitrace_categories: "pagecache"
   hitrace_categories: "rpc"
   hitrace_categories: "sched"
   hitrace_categories: "sync"
   hitrace_categories: "window"
   hitrace_categories: "workq"
   hitrace_categories: "zaudio"
   hitrace_categories: "zcamera"
   hitrace_categories: "zimage"
   hitrace_categories: "zmedia"

   # Buffer configuration
   buffer_size_kb: 204800
   flush_interval_ms: 1000
   flush_threshold_kb: 4096
   parse_ksyms: true
   clock: "boot"
   trace_period_ms: 200
   debug_on: false
  }}
 }}

# hiperf plugin configuration
 plugin_configs {{
  plugin_name: "hiperf-plugin"
  config_data {{
   is_root: false
   outfile_name: "{output_path}"
   record_args: "{record_args}"
  }}
 }}
CONFIG"""


class ConnectedException(Exception):
    pass


class PerfTestCase(TestCase, ABC):
    """Base class for performance test cases with trace collection support"""

    def __init__(self, tag: str, configs):
        super().__init__(tag, configs)
        self.driver = UiDriver(self.device1)
        self.tag = tag
        self._start_app_package = None  # Package name for process identification
        self._redundant_mode_status = False  # default close redundant mode

    @property
    @abstractmethod
    def steps(self) -> list:
        """List of test steps with name and description"""

    @property
    @abstractmethod
    def app_package(self) -> str:
        """Package identifier of the application under test"""

    @property
    @abstractmethod
    def app_name(self) -> str:
        """Human-readable name of the application under test"""

    @property
    def report_path(self) -> str:
        """Path where test reports will be stored"""
        return self.get_case_report_path()

    def execute_performance_step(
            self,
            step_id: int,
            action: callable,
            duration: int,
            sample_all_processes: bool = False
    ):
        """
        Execute a test step while collecting performance and trace data

        Args:
            step_id: Identifier for the current step
            action: Function to execute for this test step
            duration: Data collection time in seconds
            sample_all_processes: Whether to sample all system processes
        """
        output_file = self._prepare_output_path(step_id)
        self._clean_previous_output(output_file)

        cmd = self._build_collection_command(
            output_file,
            duration,
            sample_all_processes
        )

        collection_thread = threading.Thread(
            target=self._run_perf_command,
            args=(cmd, duration)
        )
        collection_thread.start()

        # Execute the test action while data collection runs
        action(self.driver)

        collection_thread.join()
        self._save_performance_data_async(output_file, step_id)

    def generate_reports(self):
        """Generate test reports and metadata files"""
        steps_info = self._collect_step_information()
        self._save_steps_info(steps_info)
        self._save_test_metadata()

    def set_device_redundant_mode(self):
        # 设置hdc参数
        Log.info('设置hdc参数: persist.ark.properties 0x200105c')
        os.system('hdc shell param set persist.ark.properties 0x200105c')
        self._redundant_mode_status = True

    def reboot_device(self):
        # 重启手机
        Log.info('重启手机')
        os.system('hdc shell reboot')

        # 检测手机是否重启成功
        Log.info('检测手机重启状态')
        max_wait_time = 180  # 最大等待时间180秒
        wait_interval = 10  # 每10秒检查一次
        elapsed_time = 0

        while elapsed_time < max_wait_time:
            try:
                # 使用hdc shell命令检测设备是否真正连接
                result = os.system('hdc shell "echo device_ready"')
                if result == 0:
                    Log.info('手机重启成功，设备已连接')
                    Log.info('等待手机完全启动到大屏幕界面...')
                    time.sleep(60)  # 额外等待60秒确保系统完全启动到大屏幕
                    return

                Log.info(f'设备未连接，返回码: {result}')
            except Exception as e:
                Log.info(f'设备检测失败: {e}')

            Log.info(f'等待设备重启中... ({elapsed_time}/{max_wait_time}秒)')
            time.sleep(wait_interval)
            elapsed_time += wait_interval
            Log.info(f'时间已更新: {elapsed_time}秒')

        # 如果超时仍未检测到设备
        raise ConnectedException('手机重启超时，设备未连接')

    def _prepare_output_path(self, step_id: int) -> str:
        """Generate output file path on device"""
        return f"/data/local/tmp/hiperf_step{step_id}.data"

    def _clean_previous_output(self, output_path: str):
        """Remove previous output files from device"""
        output_dir = os.path.dirname(output_path)
        self.driver.shell(f"mkdir -p {output_dir}")
        self.driver.shell(f"rm -f {output_path}")
        self.driver.shell(f"rm -f {output_path}.htrace")

    def _build_collection_command(
            self,
            output_path: str,
            duration: int,
            sample_all: bool
    ) -> str:
        """Build appropriate command based on collection parameters"""
        pids_args = self._build_processes_args(sample_all)

        if Config.get('trace.enable'):
            record_args = self._build_perf_command(pids_args, duration)
            return self._build_trace_perf_command(output_path, duration, record_args)
        return self._build_perf_command(
            pids_args, duration, 'hiperf record', f'-o {output_path}'
        )

    def _build_processes_args(self, sample_all: bool) -> str:
        if sample_all:
            return '-a'
        process_ids, _ = self._get_app_pids()
        if not process_ids:
            Log.error("No application processes found for collection")
            return ""

        pid_args = ','.join(map(str, process_ids))
        return f'-p {pid_args}'

    def _build_perf_command(
            self,
            pids: str,
            duration: int,
            cmd: str = '',
            output_arg: str = ''
    ) -> str:
        """Construct base performance collection command"""
        return _PERF_CMD_TEMPLATE.format(
            cmd=cmd,
            pids=pids,
            output_path=output_arg,
            duration=duration,
            event=Config.get('hiperf.event')
        )

    def _build_trace_perf_command(
            self,
            output_path: str,
            duration: int,
            record_args: str
    ) -> str:
        """Construct combined trace and performance command"""
        return _TRACE_PERF_CMD_TEMPLATE.format(
            output_path=output_path,
            duration=duration,
            record_args=record_args
        )

    def _run_perf_command(self, command: str, duration: int):
        """Execute performance collection command on device"""
        Log.info(f'Starting performance collection for {duration}s')
        self.driver.shell(command, timeout=duration + 30)
        Log.info('Performance collection completed')

    def _save_performance_data_async(self, device_file: str, step_id: int):
        """Asynchronously save collected performance data"""
        threading.Thread(
            target=lambda: self._save_perf_and_trace_data(device_file, step_id)
        ).start()

    def _save_perf_and_trace_data(self, device_file: str, step_id: int):
        """Save performance and trace data to report directory"""
        perf_step_dir = os.path.join(
            self.report_path,
            'hiperf',
            f'step{step_id}'
        )
        trace_step_dir = os.path.join(
            self.report_path,
            'htrace',
            f'step{step_id}'
        )

        local_perf_path = os.path.join(
            perf_step_dir,
            Config.get('hiperf.data_filename', 'perf.data')
        )
        local_trace_path = os.path.join(trace_step_dir, 'trace.htrace')

        self._ensure_directories_exist(perf_step_dir, trace_step_dir)
        self._save_process_info(perf_step_dir)

        if not self._verify_remote_files_exist(device_file):
            return

        if Config.get('trace.enable') and not self._verify_remote_files_exist(f"{device_file}.htrace"):
            return

        self._transfer_perf_data(device_file, local_perf_path)
        if Config.get('trace.enable'):
            self._transfer_trace_data(device_file, local_trace_path)
        self._transfer_redundant_data(trace_step_dir)

    def _collect_step_information(self) -> list:
        """Collect metadata about test steps"""
        step_info = []
        for idx, step in enumerate(self.steps, start=1):
            step_info.append({
                "name": step['name'],
                "description": step['description'],
                "stepIdx": idx
            })
        return step_info

    def _save_steps_info(self, steps_info: list):
        """Save step metadata to JSON file"""
        steps_path = os.path.join(self.report_path, 'hiperf', 'steps.json')
        with open(steps_path, 'w', encoding='utf-8') as file:
            json.dump(steps_info, file, ensure_ascii=False, indent=4)

    def _save_test_metadata(self):
        """Save test metadata to JSON file"""
        metadata = {
            "app_id": self.app_package,
            "app_name": self.app_name,
            "app_version": self._get_app_version(),
            "scene": self.tag,
            "device": self.devices[0].device_description,
            "timestamp": int(time.time() * 1000)  # Millisecond precision
        }

        metadata_path = os.path.join(self.report_path, 'testInfo.json')
        with open(metadata_path, 'w', encoding='utf-8') as file:
            json.dump(metadata, file, indent=4, ensure_ascii=False)

    def _get_app_version(self) -> str:
        """Retrieve application version from device"""
        cmd = f"bm dump -n {self.app_package}"
        result = self.driver.shell(cmd)

        try:
            # Extract JSON portion from command output
            json_str = result.split(':', 1)[1].strip()
            data = json.loads(json_str)
            return data.get('applicationInfo', {}).get('versionName', "Unknown")
        except (json.JSONDecodeError, IndexError, KeyError):
            return "Unknown"

    def _get_app_pids(self) -> tuple[list[int], list[str]]:
        """Get all PIDs and process names associated with the application"""
        target_package = self._start_app_package or self.app_package
        cmd = f"ps -ef | grep {target_package}"
        result = self.driver.shell(cmd)

        process_ids = []
        process_names = []

        for line in result.splitlines():
            if 'grep' in line:  # Skip the grep process itself
                continue

            parts = line.split()
            if len(parts) < 2:  # Skip invalid lines
                continue

            try:
                process_ids.append(int(parts[1]))
                process_names.append(parts[-1])
            except (ValueError, IndexError):
                continue

        return process_ids, process_names

    def _save_process_info(self, directory: str):
        """Save process information to JSON file"""
        process_ids, process_names = self._get_app_pids()
        info_path = os.path.join(directory, 'pids.json')
        with open(info_path, 'w', encoding='utf-8') as file:
            json.dump(
                {'pids': process_ids, 'process_names': process_names},
                file,
                indent=4,
                ensure_ascii=False
            )

    def _ensure_directories_exist(self, *paths):
        """Ensure required directories exist"""
        for path in paths:
            os.makedirs(path, exist_ok=True)

    def _verify_remote_files_exist(self, device_file: str) -> bool:
        """Verify required files exist on device"""
        perf_result = self.driver.shell(f"ls -l {device_file}")
        if "No such file" in perf_result:
            Log.error(f"Performance data missing: {device_file}")
            return False

        return True

    def _transfer_perf_data(self, remote_path: str, local_path: str):
        """Transfer performance data from device to host"""
        self.driver.shell(f"hiperf report -i {remote_path} --json -o {remote_path}.json")
        self.driver.pull_file(remote_path, local_path)
        self.driver.pull_file(f"{remote_path}.json", os.path.join(os.path.dirname(local_path), 'perf.json'))
        if os.path.exists(local_path):
            Log.info(f"Performance data saved: {local_path}")
        else:
            Log.error(f"Failed to transfer performance data: {local_path}")

    def _transfer_trace_data(self, remote_path: str, local_path: str):
        """Transfer trace data from device to host"""
        self.driver.pull_file(f"{remote_path}.htrace", local_path)
        if os.path.exists(local_path):
            Log.info(f"Trace data saved: {local_path}")
        else:
            Log.error(f"Failed to transfer trace data: {local_path}")

    def _transfer_redundant_data(self, trace_step_dir: str):
        if not self._transfer_redundant_data:
            return
        bundle_name = self._start_app_package or self.app_package
        remote_path = f'data/app/el2/100/base/{bundle_name}/files/{bundle_name}_redundant_file.txt'
        if not self._verify_remote_files_exist(remote_path):
            return
        local_path = os.path.join(trace_step_dir, 'redundant_file.txt')
        self.driver.pull_file(remote_path, local_path)
        if os.path.exists(local_path):
            Log.info(f"Redundant data saved: {local_path}")
        else:
            Log.error(f"Failed to transfer redundant data: {local_path}")
