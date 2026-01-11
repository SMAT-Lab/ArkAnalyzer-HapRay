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
import json
import logging
import os
from typing import Optional

from hapray import VERSION
from hapray.gui_agent import GuiAgent, GuiAgentConfig


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
            '--gui-llm-base-url',
            type=str,
            default=os.getenv('GUI_LLM_BASE_URL', 'http://localhost:8000/v1'),
            help='LLM API base URL (default: http://localhost:8000/v1, env: GUI_LLM_BASE_URL)',
        )
        parser.add_argument(
            '--gui-llm-model',
            type=str,
            default=os.getenv('GUI_LLM_MODEL', 'autoglm-phone-9b'),
            help='Model name (default: autoglm-phone-9b, env: GUI_LLM_MODEL)',
        )
        parser.add_argument(
            '--gui-llm-api-key',
            type=str,
            default=os.getenv('GUI_LLM_API_KEY', ''),
            help='API key for model authentication (env: GUI_LLM_API_KEY)',
        )

        # Agent configuration
        parser.add_argument(
            '--max-steps',
            type=int,
            default=50,
            help='Maximum steps per task (default: 50)',
        )
        parser.add_argument(
            '--device-id',
            type=str,
            default=None,
            help='Device ID for multi-device setups',
        )

        # Task configuration
        parser.add_argument(
            '--task',
            type=str,
            help='Single task to execute (natural language description)',
        )
        parser.add_argument(
            '--tasks',
            type=str,
            nargs='+',
            help='Multiple tasks to execute (natural language descriptions)',
        )
        parser.add_argument(
            '--tasks-file',
            type=str,
            help='JSON file containing tasks list (array of strings)',
        )

        # Data collection configuration
        parser.add_argument(
            '-o',
            '--output',
            type=str,
            default=None,
            help='Path to save step data (format: output / app_name / task_name)',
        )

        parsed_args = parser.parse_args(args)

        # Validate arguments
        if not parsed_args.task and not parsed_args.tasks and not parsed_args.tasks_file:
            parser.error('Must specify one of --task, --tasks, or --tasks-file')

        # Load tasks
        tasks = []
        if parsed_args.task:
            tasks = [parsed_args.task]
        elif parsed_args.tasks:
            tasks = parsed_args.tasks
        elif parsed_args.tasks_file:
            if not os.path.exists(parsed_args.tasks_file):
                logging.error(f'Tasks file not found: {parsed_args.tasks_file}')
                return 1
            try:
                with open(parsed_args.tasks_file, encoding='utf-8') as f:
                    tasks = json.load(f)
                    if not isinstance(tasks, list):
                        logging.error('Tasks file must contain a JSON array')
                        return 1
            except json.JSONDecodeError as e:
                logging.error(f'Failed to parse tasks file: {e}')
                return 1
            except Exception as e:
                logging.error(f'Failed to read tasks file: {e}')
                return 1

        if not tasks:
            logging.error('No tasks specified')
            return 1

        # Create configuration
        config = GuiAgentConfig(
            model_base_url=parsed_args.gui_llm_base_url,
            model_name=parsed_args.gui_llm_model,
            model_api_key=parsed_args.gui_llm_api_key,
            max_steps=parsed_args.max_steps,
            device_id=parsed_args.device_id,
            report_path=os.path.abspath(parsed_args.output) if parsed_args.output else None,
        )

        # Create agent
        try:
            agent = GuiAgent(config)
        except Exception as e:
            logging.error(f'Failed to initialize GUI Agent: {e}')
            return 1

        # Execute tasks
        try:
            if len(tasks) == 1:
                # Single task
                logging.info(f'Executing task: {tasks[0]}')
                result = agent.run_task(tasks[0])
                if result.success:
                    logging.info(f'Task completed successfully: {result.result}')
                    return 0
                logging.error(f'Task failed: {result.error}')
                return 1
            # Batch tasks
            logging.info(f'Executing {len(tasks)} tasks...')
            results = agent.run_batch_tasks(tasks)

            # Summary
            success_count = sum(1 for r in results if r.success)
            failed_count = len(results) - success_count

            logging.info('=' * 50)
            logging.info('Task Execution Summary')
            logging.info('=' * 50)
            logging.info(f'Total tasks: {len(results)}')
            logging.info(f'Successful: {success_count}')
            logging.info(f'Failed: {failed_count}')

            # Print details
            for idx, result in enumerate(results, 1):
                status = '✓' if result.success else '✗'
                logging.info(f'{status} Task {idx}: {result.task}')
                if result.success:
                    logging.info(f'  Result: {result.result}')
                else:
                    logging.info(f'  Error: {result.error}')

            return 0 if failed_count == 0 else 1

        except KeyboardInterrupt:
            logging.warning('Execution interrupted by user')
            return 130
        except Exception as e:
            logging.error(f'Execution failed: {e}', exc_info=True)
            return 1

    @staticmethod
    def get_help_text():
        """Returns help text for the GUI Agent action."""
        return """
GUI Agent Action - AI-powered phone automation using LLM

This action uses an LLM-powered agent to automate phone interactions.
It supports both single task and batch task execution.

Examples:
  # Execute a single task
  hapray gui-agent --task "打开微信查看消息"

  # Execute multiple tasks
  hapray gui-agent --tasks "打开微信查看消息" "打开小红书搜索美食攻略"

  # Execute tasks from a JSON file
  hapray gui-agent --tasks-file tasks.json

  # With custom model configuration
  hapray gui-agent --task "打开微信查看消息" \\
    --model-base-url "http://your-server:8000/v1" \\
    --model-name "your-model" \\
    --model-api-key "your-api-key"

  # With output path for data collection
  hapray gui-agent --task "打开微信查看消息" \\
    --output "./reports"

Environment Variables:
  GUI_LLM_BASE_URL: Model API base URL (default: http://localhost:8000/v1)
  GUI_LLM_API_KEY: API key for model authentication
  GUI_LLM_MODEL: Model name (default: autoglm-phone-9b)
"""
