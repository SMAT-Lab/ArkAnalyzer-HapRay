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
from typing import Any

from xdevice import platform_logger

from hapray.core.collection.command_templates import (
    COVERAGE_FILE_PATH_TEMPLATE,
    FILENAME_BJC_COV,
    FILENAME_PERF_JSON,
    FILENAME_REDUNDANT_FILE,
    REDUNDANT_FILE_PATH_TEMPLATE,
)
from hapray.core.config.config import Config

Log = platform_logger('DataTransfer')


class DataTransfer:
    """数据传输类，负责从设备传输数据到主机"""

    def __init__(self, driver: Any, app_package: str, module_name: str = None):
        """
        初始化DataTransfer

        Args:
            driver: 设备驱动对象（需要有pull_file、has_file、shell、wait方法）
            app_package: 应用包名
            module_name: 模块名称（用于覆盖率数据采集）
        """
        self.driver = driver
        self.app_package = app_package
        self.module_name = module_name

    def transfer_perf_data(self, remote_path: str, local_path: str):
        """
        从设备传输性能数据到主机

        Args:
            remote_path: 设备上的文件路径
            local_path: 本地保存路径
        """
        if not self.driver.has_file(remote_path):
            Log.error('Not found %s', remote_path)
            return

        self._generate_perf_json(remote_path)
        self._pull_perf_files(remote_path, local_path)

    def _generate_perf_json(self, remote_path: str):
        """生成perf JSON报告"""
        self.driver.shell(
            f'hiperf report -i {remote_path} --json -o {remote_path}.json --symbol-dir /data/local/tmp/so_dir'
        )

    def _pull_perf_files(self, remote_path: str, local_path: str):
        """拉取性能数据文件"""
        self.driver.pull_file(remote_path, local_path)
        json_local_path = os.path.join(os.path.dirname(local_path), FILENAME_PERF_JSON)
        self.driver.pull_file(f'{remote_path}.json', json_local_path)

        if os.path.exists(local_path):
            Log.info(f'Performance data saved: {local_path}')
        else:
            Log.error(f'Failed to transfer performance data: {local_path}')

    def transfer_trace_data(self, remote_path: str, local_path: str):
        """
        从设备传输trace数据到主机

        Args:
            remote_path: 设备上的文件路径（不含.htrace扩展名）
            local_path: 本地保存路径
        """
        # trace 或 memory 启用时都会生成 .htrace 文件
        if not Config.get('trace.enable') and not Config.get('memory.enable'):
            return

        trace_remote_path = f'{remote_path}.htrace'
        if not self.driver.has_file(trace_remote_path):
            return

        self.driver.pull_file(trace_remote_path, local_path)
        if os.path.exists(local_path):
            Log.info(f'Trace data saved: {local_path}')
        else:
            Log.error(f'Failed to transfer trace data: {local_path}')

    def transfer_redundant_data(self, trace_step_dir: str, redundant_mode_status: bool):
        """
        从设备传输冗余数据到主机

        Args:
            trace_step_dir: trace步骤目录
            redundant_mode_status: 是否启用冗余模式
        """
        if not redundant_mode_status:
            return

        remote_path = REDUNDANT_FILE_PATH_TEMPLATE.format(app_package=self.app_package)
        if not self.driver.has_file(remote_path):
            return

        local_path = os.path.join(trace_step_dir, FILENAME_REDUNDANT_FILE)
        self.driver.pull_file(remote_path, local_path)

        if os.path.exists(local_path):
            Log.info(f'Redundant data saved: {local_path}')
        else:
            Log.error(f'Failed to transfer redundant data: {local_path}')

    def collect_coverage_data(self, perf_step_dir: str):
        """
        收集覆盖率数据

        Args:
            perf_step_dir: 性能步骤目录
        """
        if not self.module_name:
            Log.warning('Module name not set, skipping coverage data collection')
            return

        self._dump_coverage()
        coverage_file = self._find_coverage_file()
        if not coverage_file:
            return

        local_path = os.path.join(perf_step_dir, FILENAME_BJC_COV)
        self.driver.pull_file(coverage_file, local_path)

    def _dump_coverage(self):
        """执行覆盖率dump命令"""
        self.driver.shell('aa dump -c -l')
        self.driver.wait(1)

    def _find_coverage_file(self) -> str:
        """查找覆盖率文件"""
        file_pattern = COVERAGE_FILE_PATH_TEMPLATE.format(app_package=self.app_package, module_name=self.module_name)
        result = self.driver.shell(f'ls {file_pattern}')

        # not found bjc_cov file
        if result.find(file_pattern) != -1:
            return ''

        files = result.splitlines()
        files.sort(key=lambda x: x, reverse=True)
        return files[0] if files else ''
