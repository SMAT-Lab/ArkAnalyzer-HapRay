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
import os
import time
from typing import Optional

from hapray import VERSION
from hapray.core.config.config import Config
from hapray.core.gui_agent import GuiAgentConfig, execute_scenes


class GuiAgentAction:
    """GUI Agent命令行入口，支持单任务和批量任务执行"""

    @staticmethod
    def execute(args) -> Optional[int]:
        """
        执行GUI Agent工作流

        Args:
            args: 命令行参数列表

        Returns:
            返回码，0表示成功，非0表示失败
        """
        if '--multiprocessing-fork' in args:
            return None

        parser = argparse.ArgumentParser(
            description='GUI Agent - AI-powered phone automation using LLM',
            prog='ArkAnalyzer-HapRay gui-agent',
        )

        parser.add_argument(
            '-v',
            '--version',
            action='version',
            version=f'%(prog)s {VERSION}',
            help="Show program's version number and exit",
        )

        # Model configuration
        parser.add_argument(
            '--glm-base-url',
            type=str,
            default=os.getenv('GLM_BASE_URL', 'http://localhost:8000/v1'),
            help='LLM API base URL (default: http://localhost:8000/v1, env: GLM_BASE_URL)',
        )
        parser.add_argument(
            '--glm-model',
            type=str,
            default=os.getenv('GLM_MODEL', 'autoglm-phone-9b'),
            help='Model name (default: autoglm-phone-9b, env: GLM_MODEL)',
        )
        parser.add_argument(
            '--glm-api-key',
            type=str,
            default=os.getenv('GLM_API_KEY', ''),
            help='API key for model authentication (env: GLM_API_KEY)',
        )

        # Agent configuration
        parser.add_argument(
            '--max-steps',
            type=int,
            default=20,
            help='Maximum steps per task (default: 20)',
        )
        parser.add_argument(
            '--device-id',
            type=str,
            default=None,
            help='Device ID for multi-device setups',
        )
        parser.add_argument(
            '--package-name',
            '--apps',
            type=str,
            nargs='+',
            dest='app_packages',
            help='Application package names (supports multiple packages)',
        )

        parser.add_argument(
            '--scenes',
            type=str,
            nargs='+',
            help='Multiple scenes to execute (natural language descriptions)',
        )

        # Data collection configuration
        parser.add_argument(
            '-o',
            '--output',
            type=str,
            default=None,
            help='Path to save step data (format: output / app_name / task_name)',
        )
        parser.add_argument('--no-trace', action='store_true', help='Disable trace capturing')
        parser.add_argument('--no-perf', action='store_true', help='Disable perf capturing (for memory-only mode)')
        parser.add_argument(
            '--memory',
            action='store_true',
            help='Enable Memory profiling using hiprofiler nativehook plugin',
        )
        parser.add_argument(
            '--snapshot',
            action='store_true',
            help='Enable heap snapshot collection at step end',
        )

        parsed_args = parser.parse_args(args)
        if parsed_args.no_trace:
            Config.set('trace.enable', False)
        if parsed_args.no_perf:
            Config.set('hiperf.enable', False)
        if parsed_args.memory:
            Config.set('memory.enable', True)
        if parsed_args.snapshot:
            Config.set('memory.snapshot_enable', True)
        # Validate arguments
        if not parsed_args.app_packages:
            parser.error('Must specify --app')

        timestamp = time.strftime('%Y%m%d%H%M%S', time.localtime(time.time()))
        output = os.path.abspath(parsed_args.output) if parsed_args.output else os.getcwd()
        reports_path = os.path.join(output, 'reports', timestamp)

        # Create configuration
        config = GuiAgentConfig(
            model_base_url=parsed_args.glm_base_url,
            model_name=parsed_args.glm_model,
            model_api_key=parsed_args.glm_api_key,
            max_steps=parsed_args.max_steps,
            device_id=parsed_args.device_id,
            report_path=reports_path,
        )

        # Execute scenes
        return execute_scenes(parsed_args.app_packages, parsed_args.scenes, config)
