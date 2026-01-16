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

import json
import logging
import os
import time
from dataclasses import dataclass
from typing import Callable, Optional

from hypium import UiDriver
from hypium.uidriver.ohos.app_manager import get_bundle_info
from phone_agent import PhoneAgent
from phone_agent.agent import AgentConfig, StepResult
from phone_agent.config import get_messages
from phone_agent.device_factory import DeviceType, set_device_type
from phone_agent.model import ModelConfig

from hapray.core.collection.data_collector import DataCollector
from hapray.core.gui_agent.realtime_analysis import RealTimeAnalysisProcess


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
        self.device_id = self.config.device_id

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

        self.msgs = get_messages(self.config.lang)
        self.logger.info('GuiAgent initialized with config: %s', self.config)

        self.driver = UiDriver.connect(device_sn=self.config.device_id)

        # DataCollector instance (延迟初始化，需要app_package)
        self.data_collector: Optional[DataCollector] = None

        # 保存每个场景的步骤信息，格式: {scene_idx: [{'name': 'step1', 'description': '...', 'stepIdx': 1, 'pages': [...]}, ...]}
        # 每个 step 包含 pages 数组，每个 page 包含 action, thinking, message, pageIdx
        self._scene_steps: dict[int, list] = {}

        self.report_path: Optional[str] = None
        self.app_package: Optional[str] = None
        self.current_scene_idx: Optional[int] = None

        # Real-time analysis process (实时分析进程)
        self.realtime_analyzer = RealTimeAnalysisProcess(
            max_workers=self.config.analysis_workers,
            logger=self.logger,
        )
        self.realtime_analyzer.start()

    def process(self, app_package: str, scene_idx: int, scene: str) -> SceneResult:
        """
        Process a single scene for a specific app.

        Args:
            app_package: Application package name.
            scene_idx: Scene index for tracking.
            scene: Scene description in natural language.

        Returns:
            TaskResult object containing scene execution result.
        """
        self.logger.info('Processing scene %d for app %s: %s', scene_idx, app_package, scene)

        try:
            # 执行 setup
            self._setup(app_package, scene_idx)

            # 重置当前场景的步骤信息
            self._scene_steps[scene_idx] = [{'name': 'step1', 'description': scene, 'stepIdx': 1, 'pages': []}]

            self.data_collector.collect_step_data_start(1, self.report_path, 30)
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
            self.collect_page_data(step_count, step_result, scene_idx)

            # Continue steps until finished or max steps reached
            task_result = None
            while not step_result.finished and step_count < self.config.max_steps:
                step_result = self.agent.step()
                step_count = self.agent.step_count

                # Collect page data after each step
                self.collect_page_data(step_count, step_result, scene_idx)

                # Check if task completed successfully
                if step_result.finished:
                    result_message = step_result.message or 'Scene completed'
                    self.logger.info('Scene completed successfully: %s (steps: %d)', scene, step_count)
                    task_result = SceneResult(
                        scene=scene,
                        success=True,
                        result=result_message,
                        page_count=step_count,
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
                )

            self.data_collector.collect_step_data_end(1, self.report_path)
            # 执行 teardown
            self._teardown()

            return task_result

        except Exception as e:
            error_msg = str(e)
            self.logger.error('Scene failed: %s, Error: %s', scene, error_msg)

            # 即使失败也执行 teardown
            try:
                self._teardown()
            except Exception as teardown_error:
                self.logger.warning(f'Teardown failed: {teardown_error}')

            return SceneResult(
                scene=scene,
                success=False,
                result='',
                error=error_msg,
            )

    def _setup(self, app_package: str, scene_idx: int) -> None:
        """
        Setup before processing scenes.

        Args:
            app_package: Application package name. If provided, will prepare the app for testing.
        """
        self.logger.info('GuiAgent setup')

        # 唤醒屏幕
        try:
            self.driver.wake_up_display()
        except Exception as e:
            self.logger.warning(f'唤醒屏幕失败: {e}')

        # 回到主页
        try:
            self.driver.swipe_to_home()
        except Exception as e:
            self.logger.warning(f'回到主页失败: {e}')

        # 如果提供了应用包名，停止应用以确保干净的状态
        self._stop_app(app_package)
        self._start_app(app_package)

        # Reset agent state before executing new task
        self.agent.reset()

        # 创建数据采集器，使用指定的 app_package
        self._create_data_collector_with_package(app_package)

        self.report_path = os.path.join(self.config.report_path, app_package, f'scene{scene_idx}')
        self.app_package = app_package
        self.current_scene_idx = scene_idx
        os.makedirs(self.report_path, exist_ok=True)

        self.logger.info('GuiAgent setup completed')

    def _teardown(self) -> None:
        """
        Teardown after processing scenes.
        """
        self.logger.info('GuiAgent teardown')

        # 保存步骤信息
        self._save_steps_info()
        self._save_test_metadata()

        # 通知实时分析进程启动报告分析（不等待完成）
        if self.realtime_analyzer and self.report_path and self.current_scene_idx:
            try:
                # 通知数据采集完成，触发分析任务
                self.realtime_analyzer.notify_data_collected(
                    task_id=self.current_scene_idx,
                    step_count=1,  # 场景只有一个步骤
                    task_report_path=self.report_path,
                )
                self.logger.info('已提交实时分析任务，将在后台执行')
            except Exception as e:
                self.logger.warning(f'提交实时分析任务失败: {e}')

        self._stop_app(self.app_package)

        # 清理资源
        if self.data_collector:
            self.data_collector = None
            self.logger.info('DataCollector 已清理')

        self.report_path = None
        self.app_package = None
        self.current_scene_idx = None

        self.logger.info('GuiAgent teardown completed')

    def _start_app(self, package_name: str = None, page_name: str = None, params: str = '', wait_time: float = 5):
        """通用应用启动方法"""
        self.driver.start_app(package_name, page_name, params, wait_time)

    def _stop_app(self, package_name: str = None, wait_time: float = 0.5):
        """通用应用退出方法"""
        # 桌面应用不能退出
        if package_name == 'com.ohos.sceneboard':
            return
        self.driver.stop_app(package_name, wait_time)

    def _create_data_collector_with_package(self, app_package: str) -> Optional[DataCollector]:
        """
        使用指定的 app_package 创建 DataCollector 实例（私有方法）

        Args:
            app_package: 应用包名

        Returns:
            DataCollector 实例，如果无法创建则返回None
        """
        if not app_package:
            self.logger.warning('应用包名为空，跳过数据采集')
            return None

        bundle_info = get_bundle_info(self.driver, app_package)
        module_name = bundle_info.get('entryModuleName')

        # 创建 DataCollector 实例
        try:
            self.data_collector = DataCollector(self.driver, app_package, module_name=module_name)
            self.logger.info(f'创建 DataCollector 实例，app_package: {app_package}')
            return self.data_collector
        except Exception as e:
            self.logger.warning(f'创建 DataCollector 失败: {e}')
            return None

    def collect_page_data(self, step_count: int, step_result: StepResult, scene_idx: int = 1) -> None:
        """
        Collect data after each step completion.

        This function can be overridden in subclasses to implement custom data collection logic.

        Args:
            step_count: Current step count
            step_result: StepResult object containing step execution result
            task_id: Task ID for tracking steps (scene_idx)
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

        # 生成步骤描述：优先使用 action，如果没有则使用 message

        # 创建页面信息
        page_info = {
            'action': step_result.action or '',
            'thinking': step_result.thinking or '',
            'message': step_result.message or '',
            'pageIdx': step_count,
        }

        self._scene_steps[scene_idx][0]['pages'].append(page_info)

    def _save_steps_info(self) -> None:
        """
        保存场景步骤信息到 JSON 文件
        格式: [{'name': 'step1', 'description': '...', 'stepIdx': 1, 'pages': [...]}, ...]
        """
        if not self.current_scene_idx or self.current_scene_idx not in self._scene_steps:
            self.logger.warning(f'场景 {self.current_scene_idx} 没有步骤信息，跳过生成 steps.json')
            return

        if not self.report_path:
            self.logger.warning('报告路径为空，跳过生成 steps.json')
            return

        try:
            # 保存步骤信息到 steps.json
            steps_path = os.path.join(self.report_path, 'steps.json')
            steps_info = self._scene_steps[self.current_scene_idx]

            with open(steps_path, 'w', encoding='utf-8') as file:
                json.dump(steps_info, file, ensure_ascii=False, indent=4)

            total_pages = sum(len(step.get('pages', [])) for step in steps_info)
            self.logger.info(f'步骤信息已保存到: {steps_path} (共 {len(steps_info)} 个步骤, {total_pages} 个页面)')
        except Exception as e:
            self.logger.error(f'保存步骤信息失败: {e}')

    def _save_test_metadata(self):
        """Save test metadata to JSON file"""
        metadata = {
            'app_id': self.app_package,
            'app_version': self._get_app_version(),
            'scene': self._scene_steps[self.current_scene_idx][0]['description'],
            'device': {
                'sn': self.driver.get_device_sn(),
                'type': self.driver.get_device_type().strip(),
                'platform': self.driver.get_os_type(),
                'version': self.driver.shell('param get const.product.software.version').strip(),
            },
            'timestamp': int(time.time() * 1000),  # Millisecond precision
        }

        metadata_path = os.path.join(self.report_path, 'testInfo.json')
        with open(metadata_path, 'w', encoding='utf-8') as file:
            json.dump(metadata, file, indent=4, ensure_ascii=False)

    def _get_app_version(self) -> str:
        """Retrieve application version from device"""
        cmd = f'bm dump -n {self.app_package}'
        result = self.driver.shell(cmd)

        try:
            # Extract JSON portion from command output
            json_str = result.split(':', 1)[1].strip()
            data = json.loads(json_str)
            return data.get('applicationInfo', {}).get('versionName', 'Unknown')
        except (json.JSONDecodeError, IndexError, KeyError):
            return 'Unknown'
