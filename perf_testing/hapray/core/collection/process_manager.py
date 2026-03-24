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
from typing import Any

from xdevice import platform_logger

from hapray.core.collection.command_templates import FILENAME_PIDS_JSON, PROC_MAPS_PATH_TEMPLATE

Log = platform_logger('ProcessManager')


class ProcessManager:
    """进程管理类，负责获取和管理进程信息"""

    def __init__(self, driver: Any, app_package: str):
        """
        初始化ProcessManager

        Args:
            driver: 设备驱动对象（需要有shell方法）
            app_package: 应用包名
        """
        self.driver = driver
        self.app_package = app_package

    def get_app_pids(self) -> tuple[list[int], list[str]]:
        """
        获取应用的所有进程ID和进程名

        Returns:
            (进程ID列表, 进程名列表)的元组
        """
        cmd = f'ps -ef | grep {self.app_package}'
        result = self.driver.shell(cmd)

        process_ids = []
        process_names = []

        for line in result.splitlines():
            if 'grep' in line:
                continue

            parts = line.split()
            if len(parts) < 2:
                continue

            try:
                process_ids.append(int(parts[1]))
                process_names.append(parts[-1])
            except (ValueError, IndexError):
                continue

        return process_ids, process_names

    def get_memory_pids(self) -> list[int]:
        """
        获取内存采集的进程ID（应用级）

        Returns:
            进程ID列表

        Raises:
            ValueError: 如果没有找到进程ID
        """
        process_ids, _ = self.get_app_pids()
        if not process_ids:
            Log.error('Memory collection enabled but no application PIDs found')
            raise ValueError('No process IDs available for memory collection')
        return process_ids

    def build_processes_args(self, sample_all: bool) -> str:
        """
        构建进程参数

        Args:
            sample_all: 是否采样所有进程

        Returns:
            进程参数字符串（如 '-a' 或 '-p 1234,5678'）
        """
        if sample_all:
            return '-a'

        process_ids, _ = self.get_app_pids()
        if not process_ids:
            Log.error('No application processes found for collection')
            return ''

        pid_args = ','.join(map(str, process_ids))
        return f'-p {pid_args}'

    def save_process_info(self, directory: str):
        """
        保存进程信息到JSON文件

        Args:
            directory: 保存目录
        """
        process_ids, process_names = self.get_app_pids()
        info_path = os.path.join(directory, FILENAME_PIDS_JSON)
        maps = []

        for pid in process_ids:
            maps_path = PROC_MAPS_PATH_TEMPLATE.format(pid=pid)
            result = self.driver.shell(f'cat {maps_path}')
            maps.append(result.split('\n'))

        with open(info_path, 'w', encoding='utf-8') as file:
            json.dump(
                {'pids': process_ids, 'process_names': process_names, 'maps': maps},
                file,
                indent=4,
                ensure_ascii=False,
            )
