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
from typing import Any, Optional

import yaml
from xdevice.__main__ import main_process

from hapray.core.gui_agent import GuiAgent, GuiAgentConfig
from hapray.core.perf_testcase import PerfTestCase

logger = logging.getLogger(__name__)


class GUIAgentRunner(PerfTestCase):
    """GUI Agent 测试运行器，使用 GuiAgent 执行场景测试"""

    def __init__(self, controllers):
        """初始化 GUIAgentRunner

        Args:
            controllers: 测试控制器，应包含 testargs 参数，格式：
                testargs: {
                    'gui_agent': [config_file_path],  # GUI Agent 配置文件路径（YAML格式）
                }
                或者直接传入参数：
                testargs: {
                    'app_package': [app_package],
                    'scene': [scene_description],
                    'scene_idx': [scene_idx],  # 可选，默认为1
                }
        """
        # 加载配置
        testargs = controllers.get('testargs', {})
        self.config_data = self._load_config(testargs)
        self.config = self._parse_config()

        # 从配置中获取必要信息
        self._app_package = self.config['app_package']
        self._app_name = self._app_package
        self._scene = self.config['scene']
        self._scene_idx = self.config.get('scene_idx', 1)
        scene_name = self.config.get('scene_name', f'{self._app_package}_scene{self._scene_idx}')

        # pylint: disable=C0103
        self.TAG = scene_name
        super().__init__(self.TAG, controllers)

        # 创建 GuiAgentConfig
        self.gui_agent_config = self._create_gui_agent_config()

        # GuiAgent 实例（延迟初始化）
        self.gui_agent: Optional[GuiAgent] = None

    @staticmethod
    def run_testcase(config_file: str, output: str, device_id: str):
        """运行 GUI Agent 测试用例

        Args:
            config_file: GUI Agent 配置文件路径
            output: 输出路径
            device_id: 设备ID
        """
        device = f'-sn {device_id}' if device_id else ''
        command = f'run -l gui_agent_runner {device} -tcpath {os.path.dirname(__file__)} -rp {output} -ta gui_agent:{config_file}'
        main_process(command)

    @property
    def app_package(self) -> str:
        """应用包名"""
        return self._app_package

    @property
    def app_name(self) -> str:
        """应用名称"""
        return self._app_name

    def process(self):
        """执行测试场景"""
        # 延迟初始化 GuiAgent（需要 report_path）
        if self.gui_agent is None:
            self.gui_agent = GuiAgent(self.gui_agent_config)

        self.start_app()

        # 执行场景
        logger.info(
            '开始执行 GUI Agent 场景: %s (app: %s, scene_idx: %d)', self._scene, self._app_package, self._scene_idx
        )
        result = self.gui_agent.process(
            app_package=self._app_package,
            scene_idx=self._scene_idx,
            scene=self._scene,
        )

        if result.success:
            logger.info('场景执行成功: %s', result.result)
        else:
            logger.error('场景执行失败: %s', result.error)
            raise RuntimeError(f'场景执行失败: {result.error}')

    def teardown(self):
        """清理资源"""
        # 关闭 GuiAgent 的实时分析进程
        if self.gui_agent and hasattr(self.gui_agent, 'realtime_analyzer'):
            try:
                self.gui_agent.realtime_analyzer.shutdown()
                logger.info('实时分析进程已关闭')
            except Exception as e:
                logger.warning(f'关闭实时分析进程时出错: {e}')

        # 调用父类的 teardown
        super().teardown()

    def _load_config(self, testargs: dict) -> dict[str, Any]:
        """加载配置文件

        Args:
            testargs: 测试参数字典

        Returns:
            配置数据字典
        """
        # 方式1: 从配置文件加载
        if 'gui_agent' in testargs and testargs['gui_agent']:
            config_file = testargs['gui_agent'][0]
            if os.path.exists(config_file):
                with open(config_file, encoding='UTF-8') as f:
                    return yaml.safe_load(f)
            else:
                raise FileNotFoundError(f'配置文件不存在: {config_file}')

        # 方式2: 从 testargs 直接获取参数
        config = {}
        if 'app_package' in testargs and testargs['app_package']:
            config['app_package'] = testargs['app_package'][0]
        if 'scene' in testargs and testargs['scene']:
            config['scene'] = testargs['scene'][0]
        if 'scene_idx' in testargs and testargs['scene_idx']:
            config['scene_idx'] = int(testargs['scene_idx'][0])
        if 'app_name' in testargs and testargs['app_name']:
            config['app_name'] = testargs['app_name'][0]
        if 'scene_name' in testargs and testargs['scene_name']:
            config['scene_name'] = testargs['scene_name'][0]

        if 'app_package' not in config or 'scene' not in config:
            raise ValueError('必须提供 app_package 和 scene 参数')

        return config

    def _parse_config(self) -> dict[str, Any]:
        """解析配置数据

        Returns:
            解析后的配置字典
        """
        # 如果 config_data 已经有完整的配置结构，直接返回
        if 'config' in self.config_data:
            config = self.config_data['config']
            # 合并顶层配置（兼容不同的配置格式）
            config.update({k: v for k, v in self.config_data.items() if k != 'config'})
            return config

        # 否则直接使用 config_data
        return self.config_data

    def _create_gui_agent_config(self) -> GuiAgentConfig:
        """创建 GuiAgentConfig 对象

        Returns:
            GuiAgentConfig 实例
        """
        # 从 driver 获取设备ID
        device_id = None
        try:
            if hasattr(self, 'driver') and self.driver:
                device_id = self.driver.get_device_sn()
        except Exception as e:
            logger.warning(f'获取设备ID失败: {e}')

        # 设置报告路径
        # GuiAgent 会在 report_path 下创建 {app_package}/scene{scene_idx} 目录
        # PerfTestCase 的 report_path 已经是场景目录，我们需要使用父目录
        # 这样 GuiAgent 创建的最终路径会是 {base_path}/{app_package}/scene{scene_idx}
        report_path = os.path.dirname(self.report_path) if self.report_path else None

        # 从配置中获取其他参数
        agent_config = self.config.get('gui_agent_config', {})

        return GuiAgentConfig(
            model_base_url=agent_config.get('model_base_url', os.getenv('GLM_BASE_URL', 'http://localhost:8000/v1')),
            model_name=agent_config.get('model_name', os.getenv('GLM_MODEL', 'autoglm-phone-9b')),
            model_temperature=agent_config.get('model_temperature', 0.1),
            model_api_key=agent_config.get('model_api_key', os.getenv('GLM_API_KEY')),
            max_steps=agent_config.get('max_steps', 50),
            device_id=device_id,
            lang=agent_config.get('lang', 'cn'),
            verbose=agent_config.get('verbose', True),
            report_path=report_path,
            step_duration=agent_config.get('step_duration', 5),
            analysis_workers=agent_config.get('analysis_workers', 4),
            driver=self.driver,
        )


# pylint: disable=C0103
gui_agent_runner = GUIAgentRunner
