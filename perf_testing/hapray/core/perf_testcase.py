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
import time
from abc import ABC, abstractmethod

from devicetest.core.test_case import TestCase
from hypium.uidriver.ohos.app_manager import get_bundle_info
from xdevice import platform_logger

from hapray.core.collection.data_collector import DataCollector
from hapray.core.config.config import Config
from hapray.core.ui_event_wrapper import UIEventWrapper

Log = platform_logger('PerfTestCase')


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
        self.bundle_info = None
        self.module_name = None
        self._data_collector = None  # 延迟初始化，在setup中创建

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

    @property
    def data_collector(self) -> DataCollector:
        """获取 DataCollector 实例（延迟初始化）"""
        if self._data_collector is None:
            self._data_collector = DataCollector(self.driver, self.app_package, self.module_name)
        return self._data_collector

    def setup(self):
        """common setup

        注意：不再创建 memory 目录，memory 数据从 trace.htrace 中获取
        """
        Log.info('PerfTestCase setup')
        self.bundle_info = get_bundle_info(self.driver, self.app_package)
        self.module_name = self.bundle_info.get('entryModuleName')
        # 初始化 DataCollector（延迟到setup中，此时app_package已确定）
        if self._data_collector is None:
            self._data_collector = DataCollector(self.driver, self.app_package, self.module_name)

        os.makedirs(os.path.join(self.report_path, 'hiperf'), exist_ok=True)
        os.makedirs(os.path.join(self.report_path, 'htrace'), exist_ok=True)
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

        # Use config default if not explicitly specified
        if sample_all_processes is None:
            sample_all_processes = Config.get('sample_all', False)

        # 步骤开始时的数据采集（包括UI数据采集、XVM追踪和性能采集线程启动）
        self.data_collector.collect_step_data_start(step_id, self.report_path, duration, sample_all_processes)

        try:
            # Execute the test action while data collection runs
            action(*args)
        except Exception as e:
            Log.error(f'execute performance action err {e}')

        # 步骤结束时的数据采集（包括UI数据采集和XVM追踪，以及性能采集线程等待）
        self.data_collector.collect_step_data_end(step_id, self.report_path, self._redundant_mode_status)

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

    def _collect_step_information(self) -> list:
        """Collect metadata about test steps"""
        step_info = []
        for idx, step in enumerate(self.steps, start=1):
            step_info.append({**step, 'stepIdx': idx})
        return step_info

    def _save_steps_info(self, steps_info: list):
        """Save step metadata to JSON file"""
        steps_path = os.path.join(self.report_path, 'steps.json')
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
