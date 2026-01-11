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
import re
from dataclasses import dataclass
from typing import Callable, Optional

from phone_agent import PhoneAgent
from phone_agent.agent import AgentConfig, StepResult
from phone_agent.config import get_messages
from phone_agent.device_factory import get_device_factory
from phone_agent.model import ModelConfig

try:
    from hapray.core.capture_ui import CaptureUI
except ImportError:
    CaptureUI = None


@dataclass
class GuiAgentConfig:
    """Configuration for GuiAgent.

    Environment Variables:
        GUI_LLM_BASE_URL: Model API base URL (default: http://localhost:8000/v1)
        GUI_LLM_API_KEY: API key for model authentication (default: None)
        GUI_LLM_MODEL: Model name (default: autoglm-phone-9b)
    """

    # Model configuration
    model_base_url: str = os.getenv('GUI_LLM_BASE_URL', 'http://localhost:8000/v1')
    model_name: str = os.getenv('GUI_LLM_MODEL', 'autoglm-phone-9b')
    model_temperature: float = 0.1
    model_api_key: Optional[str] = os.getenv('GUI_LLM_API_KEY')

    # Agent configuration
    max_steps: int = 50
    device_id: Optional[str] = None
    lang: str = 'cn'
    verbose: bool = True

    # Data collection configuration
    report_path: Optional[str] = None

    # Callbacks
    confirmation_callback: Optional[Callable[[str], bool]] = None
    takeover_callback: Optional[Callable[[str], None]] = None


@dataclass
class TaskResult:
    """Result of a task execution."""

    task: str
    success: bool
    result: str
    error: Optional[str] = None
    step_count: Optional[int] = None


class GuiAgent:
    """
    GUI Agent wrapper for Phone Agent automation.

    This class provides a simplified interface for executing single and batch tasks
    using the Phone Agent framework.

    Example:
        >>> from hapray.gui_agent import GuiAgent, GuiAgentConfig
        >>>
        >>> # Create configuration
        >>> config = GuiAgentConfig(
        ...     model_base_url="http://localhost:8000/v1",
        ...     model_name="autoglm-phone-9b",
        ...     max_steps=50,
        ...     lang="cn"
        ... )
        >>>
        >>> # Create agent
        >>> agent = GuiAgent(config)
        >>>
        >>> # Execute single task
        >>> result = agent.run_task("打开小红书搜索美食攻略")
        >>> print(f"Task result: {result.result}")
        >>>
        >>> # Execute batch tasks
        >>> tasks = [
        ...     "打开高德地图查看实时路况",
        ...     "打开大众点评搜索附近的咖啡店",
        ... ]
        >>> results = agent.run_batch_tasks(tasks)
        >>> for result in results:
        ...     print(f"Task: {result.task}, Success: {result.success}")
    """

    def __init__(self, config: Optional[GuiAgentConfig] = None):
        """
        Initialize GuiAgent.

        Args:
            config: Configuration for the agent. If None, uses default configuration.
        """
        self.config = config or GuiAgentConfig()
        self.logger = logging.getLogger(__name__)

        # Create model configuration
        model_config = ModelConfig(
            base_url=self.config.model_base_url,
            model_name=self.config.model_name,
            temperature=self.config.model_temperature,
            api_key=self.config.model_api_key,
            lang=self.config.lang,
        )

        # Create agent configuration
        agent_config = AgentConfig(
            max_steps=self.config.max_steps,
            device_id=self.config.device_id,
            lang=self.config.lang,
            verbose=self.config.verbose,
        )

        # Create PhoneAgent instance
        self.agent = PhoneAgent(
            model_config=model_config,
            agent_config=agent_config,
            confirmation_callback=self.config.confirmation_callback,
            takeover_callback=self.config.takeover_callback,
        )

        self.msgs = get_messages(self.config.lang)
        self.logger.info('GuiAgent initialized with config: %s', self.config)

        # Current task name for data collection
        self.current_task: Optional[str] = None

    def _sanitize_filename(self, name: str) -> str:
        """
        Sanitize filename by removing or replacing invalid characters.

        Args:
            name: Original filename

        Returns:
            Sanitized filename safe for use in file paths
        """
        # Remove or replace invalid characters for file paths
        # Replace spaces and special characters with underscores
        name = re.sub(r'[<>:"/\\|?*]', '_', name)
        name = re.sub(r'\s+', '_', name)
        # Remove leading/trailing dots and spaces
        name = name.strip('. ')
        # Limit length
        if len(name) > 100:
            name = name[:100]
        return name if name else 'unknown'

    def collect_step_data(self, step_count: int, step_result: StepResult) -> None:
        """
        Collect data after each step completion.

        This function can be overridden in subclasses to implement custom data collection logic.

        Args:
            step_count: Current step count
            step_result: StepResult object containing step execution result

        Example:
            >>> class CustomGuiAgent(GuiAgent):
            ...     def collect_step_data(self, step_count: int, step_result: StepResult):
            ...         # Custom data collection logic
            ...         print(f"Step {step_count}: {step_result.action}")
        """
        self.logger.debug(
            'Step %d data - success: %s, finished: %s, action: %s, thinking: %s, message: %s',
            step_count,
            step_result.success,
            step_result.finished,
            step_result.action,
            step_result.thinking[:100] if step_result.thinking else None,
            step_result.message,
        )

        # Save step data to path: report_path / app_name / task_name
        if self.config.report_path and self.current_task:
            try:
                # Get current app name
                device_factory = get_device_factory()
                app_name = device_factory.get_current_app(self.config.device_id)
                app_name = self._sanitize_filename(app_name)
                task_name = self._sanitize_filename(self.current_task)

                # Build path: report_path / app_name / task_name
                step_report_path = os.path.join(self.config.report_path, app_name, task_name)
                os.makedirs(step_report_path, exist_ok=True)

                # Capture UI if available
                if CaptureUI is not None:
                    # Note: CaptureUI requires a driver instance, which needs to be initialized
                    # For now, just log the path. The actual UI capture can be implemented
                    # by initializing CaptureUI with a proper driver in __init__ if needed.
                    self.logger.debug(f'Step data path: {step_report_path}')
                else:
                    self.logger.debug(f'Step data path: {step_report_path} (CaptureUI not available)')
            except Exception as e:
                self.logger.warning(f'Failed to save step data: {e}')

    def run_task(self, task: str) -> TaskResult:
        """
        Execute a single task.

        Args:
            task: Task description in natural language.

        Returns:
            TaskResult object containing task execution result.

        Example:
            >>> agent = GuiAgent()
            >>> result = agent.run_task("打开微信查看消息")
            >>> if result.success:
            ...     print(f"Task completed: {result.result}")
            ... else:
            ...     print(f"Task failed: {result.error}")
        """
        self.logger.info('Executing task: %s', task)

        try:
            # Save current task name for data collection
            self.current_task = task

            # Reset agent state before executing new task
            self.agent.reset()

            # Execute first step with task description
            step_result = self.agent.step(task)
            step_count = self.agent.step_count

            # Collect step data after first step
            self.collect_step_data(step_count, step_result)

            # Continue steps until finished or max steps reached
            while not step_result.finished and step_count < self.config.max_steps:
                step_result = self.agent.step()
                # Get step count
                step_count = self.agent.step_count

                # Collect step data after each step
                self.collect_step_data(step_count, step_result)

                # Check if task completed successfully
                if step_result.finished:
                    result_message = step_result.message or 'Task completed'
                    self.logger.info('Task completed successfully: %s (steps: %d)', task, step_count)
                    return TaskResult(
                        task=task,
                        success=True,
                        result=result_message,
                        step_count=step_count,
                    )
                error_msg = f'Max steps ({self.config.max_steps}) reached'
                self.logger.warning('Task reached max steps: %s', task)
                return TaskResult(
                    task=task,
                    success=False,
                    result=step_result.message or '',
                    error=error_msg,
                    step_count=step_count,
                )
        except Exception as e:
            error_msg = str(e)
            self.logger.error('Task failed: %s, Error: %s', task, error_msg)
            return TaskResult(
                task=task,
                success=False,
                result='',
                error=error_msg,
            )

    def run_batch_tasks(self, tasks: list[str]) -> list[TaskResult]:
        """
        Execute multiple tasks in sequence.

        Args:
            tasks: List of task descriptions in natural language.

        Returns:
            List of TaskResult objects, one for each task.

        Example:
            >>> agent = GuiAgent()
            >>> tasks = [
            ...     "打开高德地图查看实时路况",
            ...     "打开大众点评搜索附近的咖啡店",
            ...     "打开bilibili搜索Python教程",
            ... ]
            >>> results = agent.run_batch_tasks(tasks)
            >>> for result in results:
            ...     print(f"Task: {result.task}")
            ...     print(f"Success: {result.success}")
            ...     print(f"Result: {result.result}")
        """
        self.logger.info('Executing batch tasks: %d tasks', len(tasks))

        results = []
        for idx, task in enumerate(tasks, 1):
            self.logger.info('=' * 50)
            self.logger.info('Task %d/%d: %s', idx, len(tasks), task)
            self.logger.info('=' * 50)

            # Execute task
            result = self.run_task(task)
            results.append(result)

            # Log result
            if result.success:
                self.logger.info('Task %d completed successfully', idx)
            else:
                self.logger.error('Task %d failed: %s', idx, result.error)

        self.logger.info(
            'Batch tasks execution completed: %d/%d successful', sum(1 for r in results if r.success), len(results)
        )
        return results
