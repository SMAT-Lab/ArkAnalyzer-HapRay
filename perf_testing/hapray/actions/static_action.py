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
from typing import Optional

from hapray import VERSION
from hapray.core.common.exe_utils import ExeUtils


class StaticAction:
    """Handles HAP static analysis actions."""

    @staticmethod
    def execute(args) -> Optional[int]:
        """Executes HAP static analysis workflow."""
        parser = argparse.ArgumentParser(
            description='Static analysis for HAP packages - analyzing SO files and resources',
            prog='ArkAnalyzer-HapRay static',
        )
        parser.add_argument(
            '-v',
            '--version',
            action='version',
            version=f'%(prog)s {VERSION}',
            help="Show program's version number and exit",
        )
        parser.add_argument('--input', '-i', required=True, help='HAP file path to analyze')
        parser.add_argument(
            '--output',
            '-o',
            default='./static-output',
            help='Output directory for analysis results (default: ./static-output)',
        )

        parser.add_argument('--include-details', action='store_true', help='Include detailed analysis information')
        parser.add_argument(
            '-j',
            '--jobs',
            type=str,
            default='auto',
            help='Number of parallel jobs for analysis (default: auto, uses CPU core count)',
        )

        parsed_args = parser.parse_args(args)

        # 验证输入文件
        if not os.path.exists(parsed_args.input):
            logging.error(f'Input file does not exist: {parsed_args.input}')
            return 1

        # 构建命令参数
        cmd_args = [
            'hap',
            '-i',
            parsed_args.input,
            '-o',
            parsed_args.output,
        ]

        # 添加并发数参数
        if parsed_args.jobs != 'auto':
            cmd_args.extend(['-j', parsed_args.jobs])

        if parsed_args.include_details:
            # 新CLI默认包含详细信息，不需要额外参数
            pass

        logging.info('Starting HAP static analysis...')
        logging.info(f'Input: {parsed_args.input}')
        logging.info(f'Output: {parsed_args.output}')
        if parsed_args.jobs != 'auto':
            logging.info(f'Jobs: {parsed_args.jobs}')
        else:
            logging.info('Jobs: auto (using CPU core count)')

        # 使用 execute_hapray_cmd 执行静态分析
        success = ExeUtils.execute_hapray_cmd(cmd_args)

        if success:
            logging.info('Static analysis completed successfully')
            return 0
        logging.error('Static analysis failed')
        return 1

    @staticmethod
    def get_help_text():
        """Returns help text for the static action."""
        return """
Static Analysis Action:
  Performs static analysis on HAP packages to identify:
  - SO files and framework detection (React Native, Flutter, etc.)
  - Resource files and their types
  - JavaScript files and Hermes bytecode
  - Archive files and nested content analysis

Examples:
  # Basic analysis (generates all formats by default)
  python main.py static -i app.hap -o ./output

  # Analysis with detailed information
  python main.py static -i app.hap -o ./output --include-details

  # Analysis with custom concurrency (4 parallel jobs)
  python main.py static -i app.hap -o ./output -j 4

  # Analysis with auto concurrency (uses CPU core count)
  python main.py static -i app.hap -o ./output -j auto

Note: The static analysis now uses the hapray hap command internally.
"""
