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
        self.current_step_id = None  # 当前步骤ID
        self.current_page_idx = 0  # 当前页面索引，从0开始自增
        self.pageMap: dict[int, list] = {}  # pageMap: step_id -> list of pages

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

        # 设置当前步骤ID和重置页面索引
        self.current_step_id = step_id
        self.current_page_idx = 0

        # Use config default if not explicitly specified
        if sample_all_processes is None:
            sample_all_processes = Config.get('sample_all', False)

        # 步骤开始时的数据采集（包括UI数据采集、XVM追踪和性能采集线程启动）
        self.data_collector.collect_step_data_start(step_id, self.report_path, duration, sample_all_processes)
        # 检查UI采集开关
        if Config.get('ui.capture_enable', False):
            self.dump_page(f'step{step_id}_start', animate=True)

        try:
            # Execute the test action while data collection runs
            action(*args)
        except Exception as e:
            Log.error(f'execute performance action err {e}')

        # 步骤结束时的数据采集（包括UI数据采集和XVM追踪，以及性能采集线程等待）
        self.data_collector.collect_step_data_end(step_id, self.report_path, self._redundant_mode_status)
        if Config.get('ui.capture_enable', False):
            self.dump_page(f'step{step_id}_end', animate=True)

    def dump_page(self, page_description: str, animate: bool = False, ext_info: dict = None):
        """
        导出页面组件树（异步执行，不阻塞用例执行）

        Args:
            page_description: 页面描述信息
            animate: 是否进行动画采集（采集两次截图和组件树）
            ext_info: 额外的扩展信息字典，会写入page_info
        """
        if ext_info is None:
            ext_info = {}
        if self.current_step_id is None:
            Log.warning('dump_page调用时current_step_id为None，跳过组件树导出')
            return

        # 页面索引自增
        self.current_page_idx += 1
        page_idx = self.current_page_idx
        step_id = self.current_step_id

        try:
            Log.info(f'开始异步导出页面组件树 - Step {step_id}, Page {page_idx}, Description: {page_description}')
            files = self.data_collector.capture_ui_handler.capture_page(step_id, self.report_path, page_idx, animate)
            page_info = {
                **files,
                'page_idx': page_idx,
                'description': page_description,
                **ext_info,
            }

            # 同时添加到pageMap中
            if step_id not in self.pageMap:
                self.pageMap[step_id] = []
            self.pageMap[step_id].append(page_info)

            Log.info(f'页面信息已添加到Step {step_id}的pages列表和pageMap - Page {page_idx}')

            Log.info(f'页面组件树导出完成 - Step {step_id}, Page {page_idx}')
        except Exception as e:
            Log.error(f'导出页面组件树失败 - Step {step_id}, Page {page_idx}: {e}')

    def update_current_page_ext_info(self, ext_info: dict):
        """
        更新当前页面的扩展信息

        Args:
            ext_info: 要更新的扩展信息字典，会合并到现有page_info中
        """
        if self.current_step_id is None:
            Log.warning('update_current_page_ext_info调用时current_step_id为None，跳过更新')
            return

        if self.current_page_idx == 0:
            Log.warning('update_current_page_ext_info调用时current_page_idx为0，没有可更新的页面')
            return

        step_id = self.current_step_id
        page_idx = self.current_page_idx

        # 在pageMap中查找对应的页面
        if step_id not in self.pageMap:
            Log.warning(f'Step {step_id} 在pageMap中不存在，无法更新页面信息')
            return

        # 查找匹配的页面（通过page_idx）
        pages = self.pageMap[step_id]
        page_found = False
        for page_info in pages:
            if page_info.get('page_idx') == page_idx:
                # 合并扩展信息
                page_info.update(ext_info)
                page_found = True
                Log.info(f'已更新Step {step_id} Page {page_idx}的扩展信息: {ext_info}')
                break

        if not page_found:
            Log.warning(f'未找到Step {step_id} Page {page_idx}的页面信息，无法更新')

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
        self._save_page_info()
        self._save_test_metadata()

    def _collect_step_information(self) -> list:
        """Collect metadata about test steps"""
        step_info = []
        for idx, step in enumerate(self.steps, start=1):
            step_info.append({**step, 'stepIdx': idx})
        return step_info

    def _save_steps_info(self, steps_info: list):
        """Save step metadata to JSON file"""
        # 统一规则：所有步骤信息只在 report 目录下使用 steps.json
        report_dir = os.path.join(self.report_path, 'report')
        os.makedirs(report_dir, exist_ok=True)
        steps_path = os.path.join(report_dir, 'steps.json')
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

    def _save_page_info(self):
        """保存page信息到ui/step_id目录下"""
        if not self.pageMap:
            return

        for step_id, pages in self.pageMap.items():
            # 创建ui/step_id目录
            ui_step_dir = os.path.join(self.report_path, 'ui', f'step{step_id}')
            os.makedirs(ui_step_dir, exist_ok=True)

            # 保存page信息为JSON文件
            pages_info_path = os.path.join(ui_step_dir, 'pages.json')
            try:
                with open(pages_info_path, 'w', encoding='utf-8') as f:
                    json.dump(pages, f, ensure_ascii=False, indent=4)
                Log.info(f'Page信息已保存到: {pages_info_path} (Step {step_id}, 共{len(pages)}个页面)')
            except Exception as e:
                Log.error(f'保存Page信息失败 - Step {step_id}: {e}')

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
