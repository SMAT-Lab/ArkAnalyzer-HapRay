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
from hapray.core.common.common_utils import CommonUtils


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
        parser.add_argument(
            '--format',
            '-f',
            choices=['json', 'html', 'excel', 'all'],
            default='json',
            help='Output format (default: json)',
        )

        parser.add_argument('--include-details', action='store_true', help='Include detailed analysis information')

        parsed_args = parser.parse_args(args)

        # 验证输入文件
        if not os.path.exists(parsed_args.input):
            logging.error(f'Input file does not exist: {parsed_args.input}')
            return 1

        if not parsed_args.input.lower().endswith('.hap'):
            logging.error(f'Input file must be a HAP file: {parsed_args.input}')
            return 1

        # 获取hapray-sa路径，支持exe环境
        project_root = CommonUtils.get_project_root()
        static_analyzer_path = project_root / 'hapray-sa' / 'hapray-static.js'

        if not static_analyzer_path.exists():
            logging.error(f'Static analyzer not found: {static_analyzer_path}')
            logging.error('Please ensure hapray-sa is properly installed')
            logging.error(f'Project root: {project_root}')
            return 1

        # 构建命令
        cmd = [
            'node',
            str(static_analyzer_path),
            '-i',
            parsed_args.input,
            '-o',
            parsed_args.output,
            '-f',
            parsed_args.format,
        ]

        if parsed_args.include_details:
            cmd.append('--include-details')

        try:
            logging.info('Starting HAP static analysis...')
            logging.info(f'Input: {parsed_args.input}')
            logging.info(f'Output: {parsed_args.output}')
            logging.info(f'Format: {parsed_args.format}')

            # 执行静态分析
            result = subprocess.run(
                cmd,
                check=False,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='ignore',
                cwd=str(project_root),
            )

            if result.returncode == 0:
                logging.info('Static analysis completed successfully')
                if result.stdout:
                    print(result.stdout)
                return 0
            logging.error(f'Static analysis failed with return code: {result.returncode}')
            if result.stderr:
                logging.error(f'Error output: {result.stderr}')
            if result.stdout:
                logging.info(f'Standard output: {result.stdout}')
            return result.returncode

        except FileNotFoundError:
            logging.error('Node.js not found. Please ensure Node.js is installed and in PATH')
            return 1
        except Exception as e:
            logging.error(f'Failed to execute static analysis: {e}')
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
  # Basic JSON analysis
  python main.py static -i app.hap -o ./output

  # HTML report with verbose output
  python main.py static -i app.hap -o ./output -f html -v

  # All formats with detailed analysis
  python main.py static -i app.hap -o ./output -f all --include-details
"""
