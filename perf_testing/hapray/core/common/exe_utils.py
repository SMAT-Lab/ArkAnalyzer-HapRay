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

import logging
import os
import subprocess
from typing import List

from hapray.core.common.common_utils import CommonUtils


class ExeUtils:
    """Generates and updates performance analysis reports"""
    hapray_cmd_path = os.path.abspath(os.path.join(
        CommonUtils.get_project_root(), 'hapray-toolbox', 'hapray-cmd.js'
    ))

    @staticmethod
    def build_hapray_cmd(args) -> List[str]:
        cmd = ['node', ExeUtils.hapray_cmd_path, 'hapray']
        cmd.extend(args)
        return cmd

    @staticmethod
    def execute_hapray_cmd(args) -> bool:
        cmd = ExeUtils.build_hapray_cmd(args)
        return ExeUtils.execute_command(cmd)

    @staticmethod
    def execute_command(cmd: List[str]) -> bool:
        try:
            result = subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace'
            )

            if result.stdout:
                logging.debug(" %s output: %s", ' '.join(cmd), result.stdout)

            if result.stderr:
                logging.warning("%s warnings: %s", ' '.join(cmd), result.stdout)

            logging.debug("execute command %s completed successfully", ' '.join(cmd))
            return True

        except subprocess.CalledProcessError as e:
            error_msg = f"{' '.join(cmd)} failed with code {e.returncode}"
            if e.stdout:
                logging.error(f"{' '.join(cmd)} stdout: {e.stdout}")
            if e.stderr:
                logging.error(f"{' '.join(cmd)} stderr: {e.stderr}")
            logging.error(error_msg)
            return False

        except FileNotFoundError:
            logging.error("Node.js command not found. Please ensure Node.js is installed and in PATH.")
            return False
