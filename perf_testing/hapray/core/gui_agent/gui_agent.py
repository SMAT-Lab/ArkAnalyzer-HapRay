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
from phone_agent import PhoneAgent
from phone_agent.agent import AgentConfig, StepResult
from phone_agent.device_factory import DeviceType, set_device_type
from phone_agent.model import ModelConfig


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

    # App package
    app_package: Optional[str] = None


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

    def step(self, task: str | None = None) -> StepResult:
        """
        Execute a single step of the agent.

        Args:
            task: Task description (only needed for first step).

        Returns:
            StepResult with step details.
        """
        if task is not None:
            prompt = (
                f'你正在测试鸿蒙应用（bundleName: {self.config.app_package}），应用已通过 bundle 启动。'
                '请尽量探索不同页面/功能，但避免登录、支付、下单、转账、发帖/评论发布等不可逆操作。'
                '如遇到登录/授权/定位/通知权限弹窗，优先选择取消/暂不/稍后/返回。'
                f'不要打开其他应用。任务：{task}'
            )
        else:
            prompt = task

        return self.agent.step(prompt)

    def reset(self) -> None:
        """
        Reset the agent state for a new task.
        """
        self.agent.reset()

    @property
    def step_count(self) -> int:
        """Get the current step count."""
        return self.agent.step_count

    @property
    def max_steps(self) -> int:
        """Get the maximum number of steps."""
        return self.config.max_steps
