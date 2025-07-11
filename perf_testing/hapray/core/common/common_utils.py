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
from importlib.resources import files
from pathlib import Path


class CommonUtils:

    @staticmethod
    def load_all_testcases() -> dict:
        all_testcases = dict({})
        testcases_path = files("hapray.testcases")
        for second_dir in os.listdir(testcases_path):
            second_path = os.path.join(testcases_path, second_dir)

            if not os.path.isdir(second_path):
                continue
            for third_file in os.listdir(second_path):
                third_path = os.path.join(second_path, third_file)

                if os.path.isdir(third_path) or (not third_file.endswith('.py') and not third_file.endswith('.yaml')):
                    continue
                case_name, file_extension = os.path.splitext(third_file)
                all_testcases[case_name] = second_path, file_extension
        return all_testcases

    @staticmethod
    def get_project_root() -> Path:
        """获取项目根目录"""
        return Path(__file__).parent.parent.parent.parent
