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
import shutil
from pathlib import Path
from typing import Any

from xdevice import platform_logger

from hapray.core.config.config import Config

Log = platform_logger('FolderUtils')

"""
扫描ResourceUsage_PerformanceDynamic_jingdong_0020_round0/hiperf
文件夹下是否每个step文件夹下都有perf.data

"""


def scan_folders(root_dir):
    """
    检查性能测试数据是否完整
    trace、perf、memory 三者有一种数据完整就算成功
    """

    root_dir_path = Path(root_dir)
    hiperf_dir = root_dir_path / 'hiperf'

    # 读取 steps.json 获取步骤数量
    steps_json = read_json_arrays_from_dir(str(hiperf_dir))
    if len(steps_json) == 0:
        return False

    total_steps = len(steps_json)

    # 获取配置
    trace_enabled = Config.get('trace.enable', True)
    perf_enabled = Config.get('perf.enable', True)
    memory_enabled = Config.get('memory.enable', False)

    # 统计各类数据文件数量
    perf_data_num = 0
    trace_data_num = 0
    memory_data_num = 0

    # 检查 hiperf 目录中的 perf.data
    if hiperf_dir.exists():
        for item in os.listdir(hiperf_dir):
            item_path = hiperf_dir / item
            if item_path.is_dir() and (item_path / 'perf.data').exists():
                perf_data_num += 1

    # 检查 htrace 目录中的 trace.htrace（trace 或 memory 都会生成到这里）
    htrace_dir = root_dir_path / 'htrace'
    if htrace_dir.exists():
        for item in os.listdir(htrace_dir):
            item_path = htrace_dir / item
            if item_path.is_dir() and (item_path / 'trace.htrace').exists():
                if trace_enabled:
                    trace_data_num += 1
                if memory_enabled:
                    memory_data_num += 1

    # 计算各类数据的完整度百分比（仅计算启用的数据类型）
    perf_percent = (perf_data_num / total_steps * 100) if total_steps > 0 and perf_enabled else 0
    trace_percent = (trace_data_num / total_steps * 100) if total_steps > 0 and trace_enabled else 0
    memory_percent = (memory_data_num / total_steps * 100) if total_steps > 0 and memory_enabled else 0

    # 只要有一种数据完整度超过 50%，就认为测试成功
    return perf_percent > 50 or trace_percent > 50 or memory_percent > 50


def delete_folder(folder_path):
    """删除指定的文件夹及其所有内容"""
    if not os.path.exists(folder_path):
        print(f"错误: 目录 '{folder_path}' 不存在")
        return False

    if not os.path.isdir(folder_path):
        print(f"错误: '{folder_path}' 不是一个目录")
        return False

    try:
        print(f'正在删除目录: {folder_path}')
        shutil.rmtree(folder_path)
        print('操作完成: 目录已被完全删除')
        return True
    except Exception as e:
        print(f'错误: 删除过程中发生异常: {e}')
        return False


def read_json_arrays_from_dir(
    directory: str, filename_pattern: str = 'steps.json', encoding: str = 'utf-8'
) -> list[dict[str, Any]]:
    """
    读取指定目录下所有匹配的 JSON 文件并解析其中的 JSON 数组

    参数:
        directory: 目标目录路径
        filename_pattern: 文件名模式，默认为 "xxx.json"
        encoding: 文件编码，默认为 "utf-8"

    返回:
        包含所有 JSON 对象的列表
    """
    all_objects = []

    # 检查目录是否存在
    if not os.path.exists(directory):
        Log.info(f'目录不存在: {directory}')
        return all_objects

    # 遍历目录中的所有文件
    for filename in os.listdir(directory):
        # 检查文件是否匹配模式且为文件类型
        if filename.endswith(filename_pattern) and os.path.isfile(os.path.join(directory, filename)):
            file_path = os.path.join(directory, filename)

            try:
                # 读取文件内容
                with open(file_path, encoding=encoding) as f:
                    # 解析 JSON 数组
                    data = json.load(f)

                    # 验证是否为数组类型
                    if isinstance(data, list):
                        all_objects.extend(data)
                        Log.info(f'成功读取 {len(data)} 个对象 from {filename}')
                    else:
                        Log.info(f'警告: 文件 {filename} 不包含 JSON 数组，跳过')

            except json.JSONDecodeError as e:
                Log.info(f'错误: 无法解析文件 {filename}: {e}')
            except Exception as e:
                Log.info(f'错误: 读取文件 {filename} 时发生意外错误: {e}')

    return all_objects
