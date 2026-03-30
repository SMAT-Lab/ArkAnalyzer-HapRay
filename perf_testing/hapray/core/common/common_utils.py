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

# coding: utf-8
import os
import sys
from importlib.resources import files
from pathlib import Path


class CommonUtils:
    @staticmethod
    def _scan_testcases_directory(testcases_root) -> dict:
        """扫描 testcases 目录树（与 hapray/testcases 布局一致：包名子目录 / 用例脚本）。
        testcases_root 可为 pathlib.Path、str 或 importlib.resources 的 Traversable（支持 os.listdir）。"""
        all_testcases = {}
        try:
            second_dirs = os.listdir(testcases_root)
        except (FileNotFoundError, NotADirectoryError):
            return all_testcases
        for second_dir in second_dirs:
            second_path = os.path.join(testcases_root, second_dir)
            if not os.path.isdir(second_path):
                continue
            for third_file in os.listdir(second_path):
                third_path = os.path.join(second_path, third_file)
                if os.path.isdir(third_path) or (not third_file.endswith('.py') and not third_file.endswith('.yaml')):
                    continue
                case_name, file_extension = os.path.splitext(third_file)
                all_testcases[case_name] = (second_path, file_extension)
        return all_testcases

    @staticmethod
    def load_all_testcases() -> dict:
        """先加载包内 hapray.testcases，再与可执行文件旁 testcases 目录合并；同名用例以外部为准。"""
        internal = CommonUtils._scan_testcases_directory(files('hapray.testcases'))
        external_root = CommonUtils.get_project_root() / 'testcases'
        if external_root.is_dir():
            external = CommonUtils._scan_testcases_directory(external_root)
            return {**internal, **external}
        return internal

    @staticmethod
    def get_project_root() -> Path:
        """获取项目根目录，支持打包后的环境"""
        # 如果是 PyInstaller 打包后的环境
        if getattr(sys, 'frozen', False):
            # sys.executable 是可执行文件的路径
            # 例如: D:\haprayTest\tools\perf-testing\perf-testing.exe
            # 我们需要返回 D:\haprayTest\tools\perf-testing
            return Path(sys.executable).parent
        # 开发环境：从当前文件向上4级
        return Path(__file__).parent.parent.parent.parent
