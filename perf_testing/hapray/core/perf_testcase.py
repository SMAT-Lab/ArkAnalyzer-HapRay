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
import re
import threading
import time
from abc import ABC, abstractmethod

from devicetest.core.test_case import TestCase
from hypium.uidriver.ohos.app_manager import get_bundle_info
from hypium.uidriver.uitree import UiTree
from xdevice import platform_logger

from hapray.core.config.config import Config
from hapray.core.ui_event_wrapper import UIEventWrapper
from hapray.core.xvm import XVM

Log = platform_logger('PerfTestCase')

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

# Native Memory 配置模板 - 应用级采集（固定参数，只有 expand_pids 动态替换）
_NATIVE_MEMORY_CONFIG = """hiprofiler_cmd \\
  -c - \\
  -o {output_path}.htrace \\
  -t {duration} \\
  -s \\
  -k \\
<<CONFIG
request_id: 1
session_config {{
  buffers {{
    pages: 16384
  }}
}}
plugin_configs {{
  plugin_name: "nativehook"
  sample_interval: 5000
  config_data {{
    save_file: false
    smb_pages: 16384
    max_stack_depth: 20
    string_compressed: true
    fp_unwind: true
    blocked: true
    callframe_compress: true
    record_accurately: true
    offline_symbolization: true
    startup_mode: false
    malloc_free_matching_interval: 10
{expand_pids}
  }}
}}
CONFIG"""


class ConnectedError(Exception):
    pass


class PerfTestCase(TestCase, UIEventWrapper, ABC):
    """Base class for performance test cases with trace collection support"""

    def __init__(self, tag: str, configs):
        TestCase.__init__(self, tag, configs)
        UIEventWrapper.__init__(self, self.device1)
        self.tag = tag
        self._redundant_mode_status = False  # default close redundant mode
        self._steps = []
        self.uitree = UiTree(self.driver)
        self.bundle_info = None
        self.module_name = None
        self.xvm = XVM(self)

    @property
    def steps(self) -> list:
        """List of test steps with name and description"""
        return self._steps

    @property
    @abstractmethod
    def app_name(self) -> str:
        """Human-readable name of the application under test"""

    @property
    def report_path(self) -> str:
        """Path where test reports will be stored"""
        return self.get_case_report_path()

    def setup(self):
        """common setup"""
        Log.info('PerfTestCase setup')
        self.bundle_info = get_bundle_info(self.driver, self.app_package)
        self.module_name = self.bundle_info.get('entryModuleName')

        os.makedirs(os.path.join(self.report_path, 'hiperf'), exist_ok=True)
        os.makedirs(os.path.join(self.report_path, 'htrace'), exist_ok=True)
        os.makedirs(os.path.join(self.report_path, 'memory'), exist_ok=True)
        self.stop_app()
        self.driver.wake_up_display()
        self.driver.swipe_to_home()

    def teardown(self):
        """common teardown"""
        Log.info('PerfTestCase teardown')
        self.stop_app()
        self._generate_reports()

    def execute_performance_step(
        self, step_name: str, duration: int, action: callable, *args, sample_all_processes: bool = None
    ):
        """
        Execute a test step while collecting performance and trace data

        Args:
            step_id: Identifier for the current step
            action: Function to execute for this test step
            duration: Data collection time in seconds
            sample_all_processes: Whether to sample all system processes (None = use config default)
        """
        step_id = len(self._steps) + 1
        self._steps.append({'name': f'step{step_id}', 'description': step_name})
        output_file = self._prepare_output_path(step_id)
        self._clean_previous_output(output_file)

        # dump view tree when start test step
        perf_step_dir = os.path.join(self.report_path, 'hiperf', f'step{step_id}')

        # capture UI data at start of test step
        self.capture_ui(step_id, 'start')

        # Use config default if not explicitly specified
        if sample_all_processes is None:
            sample_all_processes = Config.get('sample_all', False)

        cmd = self._build_collection_command(output_file, duration, sample_all_processes)

        self.xvm.start_trace(duration)
        collection_thread = threading.Thread(target=self._run_perf_command, args=(cmd, duration))
        collection_thread.start()
        try:
            # Execute the test action while data collection runs
            action(*args)
        except Exception as e:
            Log.error(f'execute performance action err {e}')

        collection_thread.join()

        try:
            # capture UI data at end of test step
            self.capture_ui(step_id, 'end')
        finally:
            self._collect_coverage_data(perf_step_dir)
            self._save_performance_data(output_file, step_id)
            self.xvm.stop_trace(perf_step_dir)

    def set_device_redundant_mode(self):
        # 设置hdc参数
        Log.info('设置hdc参数: persist.ark.properties 0x200105c')
        os.system('hdc shell param set persist.ark.properties 0x200105c')
        self._redundant_mode_status = True

    def reboot_device(self):
        regex = re.compile(r'\d+')
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
                # 检测设备桌面是否完成启动
                pid = self.driver.shell('pidof com.ohos.sceneboard', 10)
                if regex.match(pid.strip()):
                    Log.info('手机重启成功，设备已连接')
                    Log.info('等待手机完全启动到大屏幕界面...')
                    self.driver.wake_up_display()
                    self.driver.swipe_to_back()
                    self.driver.swipe_to_home(5)
                    return

                Log.info(f'设备未连接，返回码: {pid}')
            except Exception as e:
                Log.info(f'设备检测失败: {e}')

            Log.info(f'等待设备重启中... ({elapsed_time}/{max_wait_time}秒)')
            time.sleep(wait_interval)
            elapsed_time += wait_interval
            Log.info(f'时间已更新: {elapsed_time}秒')

        # 如果超时仍未检测到设备
        raise ConnectedError('手机重启超时，设备未连接')

    def _generate_reports(self):
        """Generate test reports and metadata files"""
        steps_info = self._collect_step_information()
        self._save_steps_info(steps_info)
        self._save_test_metadata()

    def _prepare_output_path(self, step_id: int) -> str:
        """Generate output file path on device"""
        return f'/data/local/tmp/hiperf_step{step_id}.data'

    def _clean_previous_output(self, output_path: str):
        """Remove previous output files from device"""
        output_dir = os.path.dirname(output_path)
        self.driver.shell(f'mkdir -p {output_dir}')
        self.driver.shell(f'rm -f {output_path}')
        self.driver.shell(f'rm -f {output_path}.htrace')

    def _build_collection_command(self, output_path: str, duration: int, sample_all: bool) -> str:
        """
        Build appropriate command based on collection parameters

        Args:
            output_path: Output file path on device
            duration: Collection duration in seconds
            sample_all: Whether to sample all processes (only for perf/trace, not for memory)

        Returns:
            Formatted collection command string
        """
        trace_enabled = Config.get('trace.enable', True)
        memory_enabled = Config.get('memory.enable', False)

        # Validate memory collection constraints
        if memory_enabled and sample_all:
            Log.warning(
                'Memory collection enabled but sample_all=True. Memory collection will use application-level only.'
            )
            Log.warning('Consider setting sample_all=False for consistent data collection.')

        # Get collection components
        pids_args = self._build_processes_args(sample_all)
        memory_pids = self._get_memory_pids() if memory_enabled else []

        # Build command based on enabled features
        collection_mode = self._determine_collection_mode(trace_enabled, memory_enabled)
        return self._build_command_by_mode(collection_mode, output_path, duration, pids_args, memory_pids)

    def _get_memory_pids(self) -> list[int]:
        """Get process IDs for memory collection (application-level only)"""
        process_ids, _ = self._get_app_pids()
        if not process_ids:
            Log.error('Memory collection enabled but no application PIDs found')
            raise ValueError('No process IDs available for memory collection')
        return process_ids

    def _determine_collection_mode(self, trace_enabled: bool, memory_enabled: bool) -> str:
        """Determine the collection mode based on enabled features"""
        if trace_enabled and memory_enabled:
            return 'trace_perf_memory'
        if memory_enabled:
            return 'memory_only'
        if trace_enabled:
            return 'trace_perf'
        return 'perf_only'

    def _build_command_by_mode(
        self, mode: str, output_path: str, duration: int, pids_args: str, memory_pids: list[int]
    ) -> str:
        """Build command based on collection mode using strategy pattern"""
        strategies = {
            'memory_only': lambda: self._build_native_memory_command(output_path, duration, memory_pids),
            'trace_perf': lambda: self._build_trace_perf_command(
                output_path, duration, self._build_perf_command(pids_args, duration)
            ),
            'trace_perf_memory': lambda: self._build_trace_perf_memory_command(
                output_path, duration, self._build_perf_command(pids_args, duration), memory_pids
            ),
            'perf_only': lambda: self._build_perf_command(pids_args, duration, 'hiperf record', f'-o {output_path}'),
        }

        strategy = strategies.get(mode)
        if not strategy:
            raise ValueError(f'Unknown collection mode: {mode}')

        return strategy()

    def _build_processes_args(self, sample_all: bool) -> str:
        if sample_all:
            return '-a'
        process_ids, _ = self._get_app_pids()
        if not process_ids:
            Log.error('No application processes found for collection')
            return ''

        pid_args = ','.join(map(str, process_ids))
        return f'-p {pid_args}'

    def _build_perf_command(self, pids: str, duration: int, cmd: str = '', output_arg: str = '') -> str:
        """Construct base performance collection command"""
        return _PERF_CMD_TEMPLATE.format(
            cmd=cmd, pids=pids, output_path=output_arg, duration=duration, event=Config.get('hiperf.event')
        )

    def _build_trace_perf_command(self, output_path: str, duration: int, record_args: str) -> str:
        """Construct combined trace and performance command"""
        return _TRACE_PERF_CMD_TEMPLATE.format(output_path=output_path, duration=duration, record_args=record_args)

    def _build_ftrace_plugin_config(self) -> str:
        """构建 ftrace 插件配置字符串"""
        return """# ftrace plugin configuration
plugin_configs {
  plugin_name: "ftrace-plugin"
  sample_interval: 1000
  config_data {
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
  }
}"""

    def _build_hiperf_plugin_config(self, output_path: str, record_args: str) -> str:
        """构建 hiperf 插件配置字符串"""
        return f"""# hiperf plugin configuration
plugin_configs {{
  plugin_name: "hiperf-plugin"
  config_data {{
    is_root: false
    outfile_name: "{output_path}"
    record_args: "{record_args}"
  }}
}}"""

    def _build_nativehook_plugin_config(self, expand_pids_lines: str) -> str:
        """
        构建 nativehook 插件配置字符串

        Args:
            expand_pids_lines: expand_pids 配置行（已格式化）

        Returns:
            nativehook 插件配置字符串
        """
        return f"""# nativehook plugin configuration
 plugin_configs {{
  plugin_name: "nativehook"
  sample_interval: 5000
  config_data {{
    save_file: false
    smb_pages: 16384
    max_stack_depth: 20
    string_compressed: true
    fp_unwind: true
    blocked: true
    callframe_compress: true
    record_accurately: true
    offline_symbolization: true
    startup_mode: false
    malloc_free_matching_interval: 10
{expand_pids_lines}
  }}
 }}"""

    def _build_native_memory_command(self, output_path: str, duration: int, pids: list[int]) -> str:
        """
        Construct Native Memory collection command (application-level only)
        严格按照用户提供的命令，只有 expand_pids 需要动态替换

        Args:
            output_path: Output file path on device (without .htrace extension)
            duration: Collection duration in seconds
            pids: List of process IDs to monitor

        Returns:
            Command string with config via stdin
        """
        if not pids:
            Log.error('No PIDs provided for memory collection')
            raise ValueError('Memory collection requires process IDs')

        # 构建 expand_pids 配置行
        expand_pids_lines = '\n'.join([f'    expand_pids: {pid}' for pid in pids])
        Log.info(f'Memory collection: {len(pids)} process(es) - PIDs: {pids}')

        return _NATIVE_MEMORY_CONFIG.format(output_path=output_path, duration=duration, expand_pids=expand_pids_lines)

    def _build_trace_perf_memory_command(
        self, output_path: str, duration: int, record_args: str, pids: list[int]
    ) -> str:
        """
        Construct combined trace, perf, and memory collection command (application-level only)
        严格按照用户提供的命令，只有 expand_pids 需要动态替换

        Args:
            output_path: Output file path on device (without .htrace extension)
            duration: Collection duration in seconds
            record_args: Performance recording arguments
            pids: List of process IDs for memory monitoring

        Returns:
            Command string with config via stdin
        """
        if not pids:
            Log.error('No PIDs provided for memory collection')
            raise ValueError('Memory collection requires process IDs')

        # 构建各插件配置
        expand_pids_lines = '\n'.join([f'    expand_pids: {pid}' for pid in pids])
        ftrace_config = self._build_ftrace_plugin_config()
        hiperf_config = self._build_hiperf_plugin_config(output_path, record_args)
        nativehook_config = self._build_nativehook_plugin_config(expand_pids_lines)

        # 构建完整命令
        return f"""hiprofiler_cmd \\
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

{ftrace_config}

{hiperf_config}
{nativehook_config}
CONFIG"""

    def _run_perf_command(self, command: str, duration: int):
        """
        Execute performance collection command on device

        Args:
            command: Command to execute
            duration: Expected duration in seconds
        """
        Log.info(f'Starting performance collection for {duration}s')
        Log.info(f'Command: {command}')
        result = self.driver.shell(command, timeout=duration + 30)
        Log.info('Performance collection completed %s', result)

    def _save_performance_data(self, device_file: str, step_id: int):
        """Save performance, trace, and memory data to report directory"""
        perf_step_dir = os.path.join(self.report_path, 'hiperf', f'step{step_id}')
        trace_step_dir = os.path.join(self.report_path, 'htrace', f'step{step_id}')
        memory_step_dir = os.path.join(self.report_path, 'memory', f'step{step_id}')

        local_perf_path = os.path.join(perf_step_dir, Config.get('hiperf.data_filename', 'perf.data'))
        local_trace_path = os.path.join(trace_step_dir, 'trace.htrace')

        self._ensure_directories_exist(perf_step_dir, trace_step_dir, memory_step_dir)
        self._save_process_info(perf_step_dir)

        self._transfer_perf_data(device_file, local_perf_path)
        self._transfer_trace_data(device_file, local_trace_path)
        self._transfer_redundant_data(trace_step_dir)

    def _collect_step_information(self) -> list:
        """Collect metadata about test steps"""
        step_info = []
        for idx, step in enumerate(self.steps, start=1):
            step_info.append({'name': step['name'], 'description': step['description'], 'stepIdx': idx})
        return step_info

    def _save_steps_info(self, steps_info: list):
        """Save step metadata to JSON file"""
        steps_path = os.path.join(self.report_path, 'hiperf', 'steps.json')
        with open(steps_path, 'w', encoding='utf-8') as file:
            json.dump(steps_info, file, ensure_ascii=False, indent=4)

    def _save_test_metadata(self):
        """Save test metadata to JSON file"""
        metadata = {
            'app_id': self.app_package,
            'app_name': self.app_name,
            'app_version': self._get_app_version(),
            'scene': self.tag,
            'device': self.devices[0].device_description,
            'timestamp': int(time.time() * 1000),  # Millisecond precision
        }

        metadata_path = os.path.join(self.report_path, 'testInfo.json')
        with open(metadata_path, 'w', encoding='utf-8') as file:
            json.dump(metadata, file, indent=4, ensure_ascii=False)

    def _get_app_version(self) -> str:
        """Retrieve application version from device"""
        cmd = f'bm dump -n {self.app_package}'
        result = self.driver.shell(cmd)

        try:
            # Extract JSON portion from command output
            json_str = result.split(':', 1)[1].strip()
            data = json.loads(json_str)
            return data.get('applicationInfo', {}).get('versionName', 'Unknown')
        except (json.JSONDecodeError, IndexError, KeyError):
            return 'Unknown'

    def get_app_process_id(self) -> int:
        result = self.driver.shell(f'pidof {self.app_package}')
        return int(result.strip())

    def _get_app_pids(self) -> tuple[list[int], list[str]]:
        """Get all PIDs and process names associated with the application"""
        cmd = f'ps -ef | grep {self.app_package}'
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
        maps = []
        for pid in process_ids:
            result = self.driver.shell(f'cat /proc/{pid}/maps')
            maps.append(result.split('\n'))

        with open(info_path, 'w', encoding='utf-8') as file:
            json.dump(
                {'pids': process_ids, 'process_names': process_names, 'maps': maps}, file, indent=4, ensure_ascii=False
            )

    def _ensure_directories_exist(self, *paths):
        """Ensure required directories exist"""
        for path in paths:
            os.makedirs(path, exist_ok=True)

    def _transfer_perf_data(self, remote_path: str, local_path: str):
        """Transfer performance data from device to host"""
        if not self.driver.has_file(remote_path):
            Log.error('Not found %s', remote_path)
            return
        self.driver.shell(
            f'hiperf report -i {remote_path} --json -o {remote_path}.json --symbol-dir /data/local/tmp/so_dir'
        )
        self.driver.pull_file(remote_path, local_path)
        self.driver.pull_file(f'{remote_path}.json', os.path.join(os.path.dirname(local_path), 'perf.json'))
        if os.path.exists(local_path):
            Log.info(f'Performance data saved: {local_path}')
        else:
            Log.error(f'Failed to transfer performance data: {local_path}')

    def _transfer_trace_data(self, remote_path: str, local_path: str):
        """Transfer trace data from device to host"""
        if not Config.get('trace.enable'):
            return

        if not self.driver.has_file(f'{remote_path}.htrace'):
            return

        self.driver.pull_file(f'{remote_path}.htrace', local_path)
        if os.path.exists(local_path):
            Log.info(f'Trace data saved: {local_path}')
        else:
            Log.error(f'Failed to transfer trace data: {local_path}')

    def _transfer_redundant_data(self, trace_step_dir: str):
        if not self._redundant_mode_status:
            return
        remote_path = f'data/app/el2/100/base/{self.app_package}/files/{self.app_package}_redundant_file.txt'
        if not self.driver.has_file(remote_path):
            return
        local_path = os.path.join(trace_step_dir, 'redundant_file.txt')
        self.driver.pull_file(remote_path, local_path)
        if os.path.exists(local_path):
            Log.info(f'Redundant data saved: {local_path}')
        else:
            Log.error(f'Failed to transfer redundant data: {local_path}')

    def _collect_coverage_data(self, perf_step_dir: str):
        self.driver.shell('aa dump -c -l')
        self.driver.wait(1)
        file = f'data/app/el2/100/base/{self.app_package}/haps/{self.module_name}/cache/bjc*'
        result = self.driver.shell(f'ls {file}')
        # not found bjc_cov file
        if result.find(file) != -1:
            return

        files = result.splitlines()
        files.sort(key=lambda x: x, reverse=True)
        self.driver.pull_file(files[0], os.path.join(perf_step_dir, 'bjc_cov.json'))

    def capture_ui(self, step_id: int, label_name: str = None):
        """
        抓取UI相关数据，包括截屏和dump element树

        Args:
            step_id: 测试步骤ID
            label_name: 标记UI
        """
        Log.info(f'开始抓取UI数据 - Step {step_id}')

        # 创建UI数据保存目录
        ui_step_dir = os.path.join(self.report_path, 'ui', f'step{step_id}')
        os.makedirs(ui_step_dir, exist_ok=True)

        self.uitree.dump_to_file(os.path.join(ui_step_dir, f'inspector_{label_name}.json'))

        # 1. 截屏
        self._capture_screenshot(ui_step_dir, f'{label_name}_1')

        # 2. dump element树
        self._dump_element_tree(ui_step_dir, f'{label_name}_1')

        # 3. 第2次截屏
        self._capture_screenshot(ui_step_dir, f'{label_name}_2')

        # 4. 第2次dump element树
        self._dump_element_tree(ui_step_dir, f'{label_name}_2')

        Log.info(f'UI数据抓取完成 - Step {step_id}')

    def _capture_screenshot(self, ui_step_dir: str, label_name: str = None):
        """
        执行截屏并保存到本地

        Args:
            ui_step_dir: UI数据保存目录
            label_name: 测试步骤名称
        """
        try:
            Log.info('开始执行截屏...')

            # 执行hdc shell uitest screenCap命令
            result = self.driver.shell('uitest screenCap')
            Log.info(f'截屏命令输出: {result}')

            # 解析截屏文件路径
            if 'ScreenCap saved to' in result:
                # 提取文件路径
                match = re.search(r'ScreenCap saved to (.+\.png)', result)
                if match:
                    remote_screenshot_path = match.group(1)
                    Log.info(f'截屏文件路径: {remote_screenshot_path}')

                    # 生成本地保存路径
                    local_filename = f'screenshot_{label_name}.png' if label_name else 'screenshot.png'
                    local_screenshot_path = os.path.join(ui_step_dir, local_filename)

                    # 使用hdc file recv保存到本地
                    recv_cmd = f'hdc file recv {remote_screenshot_path} {local_screenshot_path}'
                    Log.info(f'执行文件传输命令: {recv_cmd}')
                    os.system(recv_cmd)

                    # 验证文件是否成功保存
                    if os.path.exists(local_screenshot_path):
                        Log.info(f'截屏保存成功: {local_screenshot_path}')
                    else:
                        Log.error(f'截屏保存失败: {local_screenshot_path}')
                else:
                    Log.error('无法从截屏命令输出中解析文件路径')
            else:
                Log.error('截屏命令执行失败或输出格式不正确')

        except Exception as e:
            Log.error(f'截屏过程中发生错误: {e}')

    def _dump_element_tree(self, ui_step_dir: str, label_name: str = None):
        """
        执行dump element树操作

        Args:
            ui_step_dir: UI数据保存目录
            label_name: 测试步骤名称
        """
        try:
            Log.info('开始dump element树...')

            # 1. 获取Focus window id
            focus_window_id = self._get_focus_window_id()
            if not focus_window_id:
                Log.error('无法获取Focus window id')
                return

            Log.info(f'获取到Focus window id: {focus_window_id}')

            # 2. 执行hidumper命令获取element树
            self._execute_hidumper_dump(ui_step_dir, label_name, focus_window_id)

        except Exception as e:
            Log.error(f'dump element树过程中发生错误: {e}')

    def _get_focus_window_id(self) -> str:
        """
        从hidumper命令输出中解析Focus window id

        Returns:
            Focus window id字符串，如果解析失败返回None
        """
        try:
            # 执行hidumper命令获取Focus window信息
            result = self.driver.shell("hidumper -s WindowManagerService -a '-a'")
            Log.info(f'hidumper命令输出: {result}')

            # 解析Focus window id
            # 查找 "Focus window: " 后面的数字
            match = re.search(r'Focus window:\s*(\d+)', result)
            if match:
                focus_window_id = match.group(1)
                Log.info(f'解析到Focus window id: {focus_window_id}')
                return focus_window_id
            Log.error('无法从hidumper输出中解析Focus window id')
            return None

        except Exception as e:
            Log.error(f'获取Focus window id时发生错误: {e}')
            return None

    def _execute_hidumper_dump(self, ui_step_dir: str, label_name: str, window_id: str):
        """
        执行hidumper dump命令并保存输出到文件

        Args:
            ui_step_dir: UI数据保存目录
            label_name: 测试步骤名称
            window_id: Focus window id
        """
        try:
            # 生成输出文件名
            dump_filename = f'element_tree_{label_name}.txt' if label_name else 'element_tree.txt'
            local_dump_path = os.path.join(ui_step_dir, dump_filename)

            # 执行hidumper dump命令
            dump_cmd = f"hidumper -s WindowManagerService -a '-w {window_id} -default'"
            Log.info(f'执行hidumper dump命令: {dump_cmd}')

            # 执行命令并保存输出到文件
            result = self.driver.shell(dump_cmd)

            # 将输出保存到本地文件
            with open(local_dump_path, 'w', encoding='utf-8') as f:
                f.write(result)

            Log.info(f'Element树dump保存成功: {local_dump_path}')

        except Exception as e:
            Log.error(f'执行hidumper dump时发生错误: {e}')
