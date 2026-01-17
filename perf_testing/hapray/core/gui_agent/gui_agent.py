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
from dataclasses import dataclass
from typing import Callable, Optional

from hypium import UiDriver
from hypium.uidriver.ohos.app_manager import get_bundle_info
from phone_agent import PhoneAgent
from phone_agent.agent import AgentConfig, StepResult
from phone_agent.device_factory import DeviceType, set_device_type
from phone_agent.model import ModelConfig

from hapray.core.collection.data_collector import DataCollector


@dataclass
class GuiAgentConfig:
    """Configuration for GuiAgent.

    Environment Variables:
        GLM_BASE_URL: Model API base URL (default: http://localhost:8000/v1)
        GLM_API_KEY: API key for model authentication (default: None)
        GLM_MODEL: Model name (default: autoglm-phone-9b)
    """

    # Model configuration
    model_base_url: str = os.getenv('GLM_BASE_URL', 'http://localhost:8000/v1')
    model_name: str = os.getenv('GLM_MODEL', 'autoglm-phone-9b')
    model_temperature: float = 0.1
    model_api_key: Optional[str] = os.getenv('GLM_API_KEY')

    # Agent configuration
    max_steps: int = 50
    device_id: Optional[str] = None
    lang: str = 'cn'
    verbose: bool = True

    # Data collection configuration
    report_path: Optional[str] = None
    step_duration: int = 5  # 每个步骤的数据采集时长（秒）

    # UiDriver
    driver: Optional[UiDriver] = None

    # Real-time analysis configuration
    analysis_workers: int = 4  # 分析进程线程池大小

    # Callbacks
    confirmation_callback: Optional[Callable[[str], bool]] = None
    takeover_callback: Optional[Callable[[str], None]] = None


@dataclass
class SceneResult:
    """Result of a task execution."""

    scene: str
    success: bool
    result: str
    error: Optional[str] = None
    page_count: Optional[int] = None
    pages: Optional[list[dict]] = None


class GuiAgent:
    """
    GUI Agent wrapper for Phone Agent automation.

    This class provides a simplified interface for executing single and batch tasks
    using the Phone Agent framework.
    """

    def __init__(self, config: Optional[GuiAgentConfig] = None):
        """
        Initialize GuiAgent.

        Args:
            config: Configuration for the agent. If None, uses default configuration.
        """
        self.config = config or GuiAgentConfig()
        self.logger = logging.getLogger(__name__)
        self.stepId = 1

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
        set_device_type(DeviceType.HDC)

        # Create PhoneAgent instance
        self.agent = PhoneAgent(
            model_config=model_config,
            agent_config=agent_config,
            confirmation_callback=self.config.confirmation_callback,
            takeover_callback=self.config.takeover_callback,
        )

        self.logger.info('GuiAgent initialized with config: %s', self.config)

        self.driver = self.config.driver

        # DataCollector instance (lazy initialization, requires app_package)
        self.data_collector: Optional[DataCollector] = None

        # Store page information for current scene
        # Format: [page1, page2, ...]
        # Each page contains action, thinking, message, pageIdx
        self._scene_pages: list[dict] = []

        self.report_path: Optional[str] = self.config.report_path
        self.app_package: Optional[str] = None

    def process(self, app_package: str, scene: str) -> SceneResult:
        """
        Process a single scene for a specific app.

        Args:
            app_package: Application package name.
            scene: Scene description in natural language.

        Returns:
            TaskResult object containing scene execution result.
        """
        self.logger.info('Processing scene for app %s: %s', app_package, scene)

        try:
            # Execute setup
            self._setup(app_package)

            # Reset page information for current scene
            self._scene_pages = []

            self.data_collector.collect_step_data_start(self.stepId, self.report_path, 30)
            # Execute first step with scene description
            prompt = (
                f'你正在测试鸿蒙应用（bundleName: {app_package}），应用已通过 bundle 启动。'
                '请尽量探索不同页面/功能，但避免登录、支付、下单、转账、发帖/评论发布等不可逆操作。'
                '如遇到登录/授权/定位/通知权限弹窗，优先选择取消/暂不/稍后/返回。'
                f'不要打开其他应用。任务：{scene}'
            )
            step_result = self.agent.step(prompt)
            step_count = self.agent.step_count

            # Collect page data after first step
            self.collect_page_data(step_count, step_result)

            # Continue steps until finished or max steps reached
            task_result = None
            while not step_result.finished and step_count < self.config.max_steps:
                step_result = self.agent.step()
                step_count = self.agent.step_count

                # Collect page data after each step
                self.collect_page_data(step_count, step_result)

                # Check if task completed successfully
                if step_result.finished:
                    result_message = step_result.message or 'Scene completed'
                    self.logger.info('Scene completed successfully: %s (steps: %d)', scene, step_count)
                    task_result = SceneResult(
                        scene=scene,
                        success=True,
                        result=result_message,
                        page_count=step_count,
                        pages=self._scene_pages.copy(),
                    )
                    break

            # If max steps reached without finishing
            if task_result is None:
                error_msg = f'Max steps ({self.config.max_steps}) reached'
                self.logger.warning('Scene reached max steps: %s', scene)
                task_result = SceneResult(
                    scene=scene,
                    success=False,
                    result=step_result.message or '',
                    error=error_msg,
                    page_count=step_count,
                    pages=self._scene_pages.copy(),
                )

            self.data_collector.collect_step_data_end(self.stepId, self.report_path)
            # Execute teardown
            self._teardown()

            return task_result

        except Exception as e:
            error_msg = str(e)
            self.logger.error('Scene failed: %s, Error: %s', scene, error_msg)

            # Execute teardown even on failure
            try:
                self._teardown()
            except Exception as teardown_error:
                self.logger.warning('Teardown failed: %s', teardown_error)

            return SceneResult(
                scene=scene,
                success=False,
                result='',
                error=error_msg,
                pages=self._scene_pages.copy(),
            )

    def _setup(self, app_package: str) -> None:
        """
        Setup before processing scenes.

        Args:
            app_package: Application package name. If provided, will prepare the app for testing.
        """
        self.logger.info('GuiAgent setup')
        # Reset agent state before executing new task
        self.agent.reset()
        # Create data collector with specified app_package
        self._create_data_collector_with_package(app_package)
        self.logger.info('GuiAgent setup completed')

    def _teardown(self) -> None:
        """
        Teardown after processing scenes.
        """
        self.logger.info('GuiAgent teardown')

        # Clean up resources
        if self.data_collector:
            self.data_collector = None
            self.logger.info('DataCollector cleaned up')

        self.logger.info('GuiAgent teardown completed')

    def _create_data_collector_with_package(self, app_package: str) -> Optional[DataCollector]:
        """
        Create DataCollector instance with specified app_package.

        Args:
            app_package: Application package name

        Returns:
            DataCollector instance, or None if creation fails
        """
        if not app_package:
            self.logger.warning('App package name is empty, skipping data collection')
            return None

        bundle_info = get_bundle_info(self.driver, app_package)
        module_name = bundle_info.get('entryModuleName')

        # Create DataCollector instance
        try:
            self.data_collector = DataCollector(self.driver, app_package, module_name=module_name)
            self.logger.info('DataCollector instance created, app_package: %s', app_package)
            return self.data_collector
        except Exception as e:
            self.logger.warning('Failed to create DataCollector: %s', e)
            return None

    def collect_page_data(self, step_count: int, step_result: StepResult) -> None:
        """
        Collect data after each step completion.

        This function can be overridden in subclasses to implement custom data collection logic.

        Args:
            step_count: Current step count
            step_result: StepResult object containing step execution result
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

        # Create page information
        page_info = {
            'action': step_result.action or '',
            'thinking': step_result.thinking or '',
            'message': step_result.message or '',
            'pageIdx': step_count,
        }

        self._scene_pages.append(page_info)
