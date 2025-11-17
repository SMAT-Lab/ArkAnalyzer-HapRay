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

import argparse
import logging
import os
import subprocess
from typing import Optional

from hapray import VERSION
from hapray.core.common.exe_utils import ExeUtils


class OptAction:
    """Handles binary optimization analysis actions by delegating to opt-detector command."""

    @staticmethod
    def execute(args) -> Optional[int]:
        """Executes binary optimization detection workflow by calling opt-detector command."""
        parser = argparse.ArgumentParser(
            description='Analyze binary files for optimization flags', prog='ArkAnalyzer-HapRay opt'
        )
        parser.add_argument(
            '-v',
            '--version',
            action='version',
            version=f'%(prog)s {VERSION}',
            help="Show program's version number and exit",
        )
        parser.add_argument('--input', '-i', required=True, help='Directory containing binary files to analyze')
        parser.add_argument(
            '--output',
            '-o',
            default='binary_analysis_report.xlsx',
            help='Output Excel file path (default: binary_analysis_report.xlsx)',
        )
        parser.add_argument('--jobs', '-j', type=int, default=1, help='Number of parallel jobs (default: 1)')
        parser.add_argument('--report_dir', '-r', help='Directory containing reports to update')
        parser.add_argument(
            '--timeout',
            '-t',
            type=int,
            default=None,
            help='Timeout in seconds for processing a single file (default: no timeout)',
        )
        parser.add_argument(
            '--no-lto',
            dest='lto',
            action='store_false',
            default=True,
            help='Disable LTO (Link-Time Optimization) detection for .so files (default: enabled)',
        )
        parser.add_argument(
            '--no-opt',
            dest='opt',
            action='store_false',
            default=True,
            help='Disable optimization level (Ox) detection, only run LTO detection (default: enabled)',
        )
        parsed_args = parser.parse_args(args)

        # 检查 opt-detector 命令是否可用
        opt_detector_cmd = ExeUtils.opt_detector_path
        if not opt_detector_cmd or not os.path.exists(opt_detector_cmd):
            logging.error('opt-detector executable not found at: %s', opt_detector_cmd)
            logging.error('请确认仓库已包含 tools/opt_detector/opt-detector，或执行安装脚本生成该工具。')
            return 1

        # 构建 opt-detector 命令
        cmd = [
            opt_detector_cmd,
            '-i',
            str(parsed_args.input),
            '-o',
            str(parsed_args.output),
            '-j',
            str(parsed_args.jobs),
        ]

        if parsed_args.timeout:
            cmd.extend(['--timeout', str(parsed_args.timeout)])

        if not parsed_args.lto:
            cmd.append('--no-lto')

        if not parsed_args.opt:
            cmd.append('--no-opt')

        if parsed_args.report_dir:
            cmd.extend(['-r', str(parsed_args.report_dir)])

        logging.info('Executing opt-detector command: %s', ' '.join(cmd))

        # 执行命令（启动后立即返回，不等待进程结束，且主进程退出后子进程继续运行）
        try:
            process = subprocess.Popen(
                cmd,
                start_new_session=True,  # 与主进程分离，避免主进程退出时子进程被终止
            )
            logging.info('opt-detector command started (pid=%s).', process.pid)
            logging.info('分析结果将输出至: %s', parsed_args.output)
            return 0

        except FileNotFoundError:
            logging.error('opt-detector command not found. Please install optimization-detector package.')
            return 1
        except Exception as e:
            logging.error('Error running opt-detector: %s', str(e))
            logging.exception('Full traceback:')
            return 1
