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

from hapray.core.gui_agent.gui_agent import GuiAgent, GuiAgentConfig
from hapray.core.gui_agent.realtime_analysis import RealTimeAnalysisProcess
from hapray.core.perf_testcase import PerfTestCase

logger = logging.getLogger(__name__)


class GUIAgentRunner(PerfTestCase):
    """GUI Agent test runner, uses GuiAgent to execute scene tests"""

    def __init__(self, controllers):
        """Initialize GUIAgentRunner.

        Args:
            controllers: Test controllers, should contain testargs parameter, format:
                testargs: {
                    'gui_agent': [config_file_path],  # GUI Agent config file path (YAML format)
                }
                Or pass parameters directly:
                testargs: {
                    'app_package': [app_package],
                    'scene': [scene_description],
                    'scene_idx': [scene_idx],  # Optional, default is 1
                }
        """
        # Load configuration
        testargs = controllers.get('testargs', {})
        self.config_data = self._load_config(testargs)
        self.config = self._parse_config()

        # Get necessary information from config
        self._app_package = self.config['app_package']
        self._app_name = self._app_package
        self._scene = self.config['scene']
        self._scene_idx = self.config.get('scene_idx', 1)
        scene_name = self.config.get('scene_name', f'{self._app_package}_scene{self._scene_idx}')

        # pylint: disable=C0103
        self.TAG = scene_name
        super().__init__(self.TAG, controllers)

        self._steps.append({'name': 'step1', 'description': self._scene})
        # Create GuiAgentConfig
        self.gui_agent_config = self._create_gui_agent_config()

        # GuiAgent instance (lazy initialization)
        self.gui_agent: Optional[GuiAgent] = None

    @staticmethod
    def run_testcase(config_file: str, output: str, device_id: str):
        """Run GUI Agent test case.

        Args:
            config_file: GUI Agent configuration file path
            output: Output path
            device_id: Device ID
        """
        device = f'-sn {device_id}' if device_id else ''
        command = f'run -l gui_agent_runner {device} -tcpath {os.path.dirname(__file__)} -rp {output} -ta gui_agent:{config_file}'
        main_process(command)

    @property
    def app_package(self) -> str:
        """Application package name"""
        return self._app_package

    @property
    def app_name(self) -> str:
        """Application name"""
        return self._app_name

    def process(self):
        """Execute test scene"""
        # Lazy initialize GuiAgent (requires report_path)
        if self.gui_agent is None:
            self.gui_agent = GuiAgent(self.gui_agent_config)

        self.start_app()

        # Execute scene
        logger.info('Starting GUI Agent scene: %s (app: %s)', self._scene, self._app_package)
        result = self.gui_agent.process(
            app_package=self._app_package,
            scene=self._scene,
        )
        self._steps[0]['pages'] = result.pages
        if result.success:
            logger.info('Scene executed successfully: %s', result.result)
        else:
            logger.error('Scene execution failed: %s', result.error)

    def teardown(self):
        """Clean up resources"""
        super().teardown()
        RealTimeAnalysisProcess.get_instance().notify_data_collected(self.report_path)

    def _load_config(self, testargs: dict) -> dict[str, Any]:
        """Load configuration file.

        Args:
            testargs: Test arguments dictionary

        Returns:
            Configuration data dictionary
        """
        # Method 1: Load from config file
        if 'gui_agent' in testargs and testargs['gui_agent']:
            config_file = testargs['gui_agent'][0]
            if os.path.exists(config_file):
                with open(config_file, encoding='UTF-8') as f:
                    return yaml.safe_load(f)
            else:
                raise FileNotFoundError(f'Config file not found: {config_file}')

        # Method 2: Get parameters directly from testargs
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
            raise ValueError('app_package and scene parameters are required')

        return config

    def _parse_config(self) -> dict[str, Any]:
        """Parse configuration data.

        Returns:
            Parsed configuration dictionary
        """
        # If config_data already has complete config structure, return directly
        if 'config' in self.config_data:
            config = self.config_data['config']
            # Merge top-level config (compatible with different config formats)
            config.update({k: v for k, v in self.config_data.items() if k != 'config'})
            return config

        # Otherwise use config_data directly
        return self.config_data

    def _create_gui_agent_config(self) -> GuiAgentConfig:
        """Create GuiAgentConfig object.

        Returns:
            GuiAgentConfig instance
        """
        # Get device ID from driver
        device_id = None
        try:
            if hasattr(self, 'driver') and self.driver:
                device_id = self.driver.get_device_sn()
        except Exception as e:
            logger.warning('Failed to get device ID: %s', e)

        # Get other parameters from config
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
            report_path=self.report_path,
            step_duration=agent_config.get('step_duration', 5),
            analysis_workers=agent_config.get('analysis_workers', 4),
            driver=self.driver,
        )


# pylint: disable=C0103
gui_agent_runner = GUIAgentRunner
