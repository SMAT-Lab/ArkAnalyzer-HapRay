# !/usr/bin/env python
# coding: utf-8

from devicetest.core.test_case import TestCase, Step
from hypium.advance.perf.driver_perf.uiexplorer_perf import UiExplorerPerf
import time
import os
import yaml
from aw.Utils import convert_data_to_db, save_testInfo
from aw.dynamic_script import perform_dynamic_test # 导入动态测试函数


class Example(TestCase):
    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        TestCase.__init__(self, self.TAG, controllers)
        self.driver = UiExplorerPerf(self.device1)
        self.config = self._load_config()
        self.test_success = True  # 添加测试状态标志
        self.current_step = 1  # 当前测试步骤

    def _load_config(self):
        """加载配置文件"""
        config_path = os.path.join(os.path.dirname(__file__), 'config.yaml')
        with open(config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)

    def settings(self, duration=None):
        """设置测试相关的参数"""
        config = self.config['test_settings']
        
        # 如果提供了duration参数，则覆盖配置文件中的值
        self.duration = duration if duration is not None else config['duration']
        
        # 从配置文件加载其他设置
        self.pid = None  # 稍后通过包名获取 PID
        self.output_path = config['output_path']
        
        # 构建本地输出路径
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        output_dir = config['output_dir']
        scene = config['scene']
        step_dir = str(self.current_step)
        
        # 构建完整的目录结构
        self.scene_dir = os.path.normpath(os.path.join(project_root, output_dir, scene))
        self.hiperf_dir = os.path.join(self.scene_dir, 'hiperf')
        self.step_dir = os.path.join(self.hiperf_dir, step_dir)
        
        # 构建文件路径
        self.local_output_path = os.path.join(self.step_dir, config['data_filename'])
        self.local_output_db_path = os.path.join(self.step_dir, config['db_filename'])
        
        # 确保所有必要的目录都存在
        os.makedirs(self.step_dir, exist_ok=True)
        os.makedirs(os.path.join(self.scene_dir, 'report'), exist_ok=True)
        
        # 其他设置
        self.app_package = config['app_package']
        self.trace_streamer = config['trace_streamer']

    def setup(self):
        Step('1.初始化设置')
        self.settings()
        
        Step('2.回到桌面')
        self.driver.swipe_to_home()
        
        Step('3.启动被测应用')
        self.driver.start_app(package_name=self.app_package)

    def process(self):
        # 使用动态步骤执行功能
        steps_info = []  # 用于存储步骤信息
        
        # 从配置中获取步骤信息
        steps = self.config['test_settings']['steps']
        
        # 记录步骤信息
        for i, step in enumerate(steps, 1):
            Step(f'{i + 2}.{step["name"]}')
            if step.get('description'):
                Step(f'描述: {step["description"]}')
            
            # 设置当前步骤
            self.current_step = i
            
            # 记录步骤信息
            steps_info.append({
                "name": step['name'],
                "stepIdx": i
            })
            
        # 保存步骤信息到steps.json
        steps_json_path = os.path.join(self.hiperf_dir, 'steps.json')
        import json
        with open(steps_json_path, 'w', encoding='utf-8') as f:
            json.dump(steps_info, f, ensure_ascii=False, indent=4)
            
        # 执行动态测试步骤
        perform_dynamic_test(self.driver, self.config)

    def teardown(self):
        Step(f'{self.current_step + 2}.关闭被测应用')
        self.driver.stop_app(self.app_package)

        # 保存测试信息
        save_testInfo(
            driver=self.driver,
            app_id=self.app_package,
            scene=self.config['test_settings'].get('scene', 'default'),
            output_dir=self.scene_dir,
            success=self.test_success,
            config=self.config
        )


