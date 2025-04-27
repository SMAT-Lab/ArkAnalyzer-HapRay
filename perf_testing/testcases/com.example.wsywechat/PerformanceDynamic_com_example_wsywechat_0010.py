# !/usr/bin/env python
# coding: utf-8

from devicetest.core.test_case import TestCase, Step
from hypium.advance.perf.driver_perf.uiexplorer_perf import UiExplorerPerf

import os
import yaml
from aw.Utils import save_testInfo, generate_hapray_report
from hypium.model import KeyCode
from hypium import BY

from aw.dynamic_script import execute_step_with_perf


class PerformanceDynamic_com_example_wsywechat_0010(TestCase):
    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        TestCase.__init__(self, self.TAG, controllers)
        self.driver = UiExplorerPerf(self.device1)
        self.config = self._load_config()
        self.test_success = True  # 添加测试状态标志
        self.current_step = 1  # 当前测试步骤
        self.report_path = self.configs['report_path']

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
        step_dir = str(self.current_step)

        # 构建完整的目录结构
        self.hiperf_dir = os.path.join(self.report_path, 'hiperf')
        self.step_dir = os.path.join(self.hiperf_dir, step_dir)

        # 构建文件路径
        self.local_output_path = os.path.join(self.step_dir, config['data_filename'])
        self.local_output_db_path = os.path.join(self.step_dir, config['db_filename'])

        # 确保所有必要的目录都存在
        os.makedirs(self.step_dir, exist_ok=True)
        os.makedirs(os.path.join(self.report_path, 'report'), exist_ok=True)

        # 其他设置
        self.app_package = config['app_package']

    def setup(self):
        Step('1.初始化设置')
        self.settings()

        Step('2.回到桌面')
        self.driver.swipe_to_home()

        Step('3.启动被测应用')
        self.driver.stop_app(package_name=self.app_package)
        self.driver.start_app(package_name=self.app_package)

    def process(self):
        """执行测试流程"""

        # 执行默认的测试步骤
        self.perform_dynamic_test()

    def teardown(self):
        Step(f'{self.current_step + 2}.关闭被测应用')
        self.driver.stop_app(self.app_package)

        # 读取配置文件中的步骤信息
        steps = self.config['test_settings']['steps']
        steps_info = []
        for i, step in enumerate(steps, 1):
            steps_info.append({
                "name": step['name'],
                "description": step['description'],
                "stepIdx": i
            })

        # 保存步骤信息到steps.json
        steps_json_path = os.path.join(self.hiperf_dir, 'steps.json')
        import json
        with open(steps_json_path, 'w', encoding='utf-8') as f:
            json.dump(steps_info, f, ensure_ascii=False, indent=4)

        # 保存测试信息
        save_testInfo(
            driver=self.driver,
            app_id=self.app_package,
            scene=self.config['test_settings'].get('scene', 'default'),
            output_dir=self.report_path,
            success=self.test_success,
            config=self.config
        )

        # 生成 HapRay 报告
        Step(f'{self.current_step + 3}.生成HapRay报告')
        if not generate_hapray_report(self.report_path):
            self.test_success = False

    def perform_dynamic_test(self):
        # 定义步骤1的动作函数：与丁真的聊天操作
        def chat_with_dingzhen(driver):
            # 点击type为{Text}并且text为{联系人}的控件
            driver.touch(BY.type('Text').text('联系人'))
            driver.wait(1)

            # 点击type为{Text}并且text为{丁真}的控件
            driver.touch(BY.type('Text').text('丁真'))
            driver.wait(1)  # 等待时间改为1秒

            # 点击输入框
            driver.touch(BY.type('TextInput'))
            driver.wait(1)

            # 输入文本
            driver.input_text(BY.type('TextInput'), "你好啊")
            driver.wait(1)

            # 按下回车键发送消息
            driver.press_key(KeyCode.ENTER)
            driver.wait(1)

            driver.touch(BY.type('TextInput'))
            driver.wait(1)

            # 输入文本
            driver.input_text(BY.type('TextInput'), "最近在忙什么呢？")
            driver.wait(1)

            # 按下回车键发送消息
            driver.press_key(KeyCode.ENTER)
            driver.wait(1)

            driver.touch(BY.type('TextInput'))
            driver.wait(1)

            # 输入文本
            driver.input_text(BY.type('TextInput'), "那就好，辛苦了")
            driver.wait(1)

            # 按下回车键发送消息
            driver.press_key(KeyCode.ENTER)
            driver.wait(1)

            driver.touch(BY.type('TextInput'))
            driver.wait(1)

            # 输入文本
            driver.input_text(BY.type('TextInput'), "谢谢关心，我先去忙了")
            driver.wait(1)

            # 按下回车键发送消息
            driver.press_key(KeyCode.ENTER)
            driver.wait(1)

            driver.touch(BY.type('TextInput'))
            driver.wait(1)

            # 输入文本
            driver.input_text(BY.type('TextInput'), "好的，再见")
            driver.wait(1)

            # 按下回车键发送消息
            driver.press_key(KeyCode.ENTER)
            driver.wait(1)

            # 滑动返回
            driver.swipe_to_back()

            driver.wait(1)

            driver.swipe_to_back()

            # 滑动返回
            driver.swipe_to_back()
            driver.wait(1)

        # 定义步骤2的动作函数：扫一扫和收付款操作
        def scan_and_payment(driver):
            driver.start_app(package_name=self.app_package)
            driver.wait(2)

            # 点击type为{Text}并且text为{微小信}的控件
            driver.touch(BY.type('Text').text('微小信'))
            driver.wait(0.5)

            # 通过相对位置点击控件
            driver.touch(BY.isAfter(BY.text('微小信')).isBefore(BY.type('List')).type('Image'))
            driver.wait(0.5)

            driver.touch(BY.type('Text').text('收付款'))
            driver.wait(0.5)

            # 滑动返回
            driver.swipe_to_back()
            driver.wait(1)

            driver.swipe_to_back()
            driver.wait(1)

            driver.start_app(package_name=self.app_package)
            driver.wait(2)  # 等待应用启动

            # 点击type为{Text}并且text为{丁真}的控件
            driver.touch(BY.type('Text').text('丁真'))
            driver.wait(0.5)
            # 滑动返回
            driver.swipe_to_back()
            driver.wait(1)

            driver.touch(BY.type('TextInput'))
            driver.wait(1)

            # 输入文本
            driver.input_text(BY.type('TextInput'), "我又来了，告辞")
            driver.wait(1)

            # 按下回车键发送消息
            driver.press_key(KeyCode.ENTER)
            driver.wait(1)
            # 滑动返回
            driver.swipe_to_back()
            driver.wait(1)

            # 滑动返回
            driver.swipe_to_back()
            driver.wait(1)

        # 定义步骤3的动作函数：发现和联系人操作
        def discover_and_contacts(driver):
            driver.start_app(package_name=self.app_package)

            # 点击type为{Text}并且text为{我的}的控件
            driver.touch(BY.type('Text').text('我的'))
            driver.wait(0.5)

            # 点击type为{Text}并且text为{发现}的控件
            driver.touch(BY.type('Text').text('发现'))
            driver.wait(0.5)

            # 点击type为{Text}并且text为{联系人}的控件
            driver.touch(BY.type('Text').text('联系人'))
            driver.wait(0.5)

            # 点击type为{Text}并且text为{微小信}的控件
            driver.touch(BY.type('Text').text('微小信'))
            driver.wait(0.5)

            # 点击type为{Text}并且text为{丁真}的控件
            driver.touch(BY.type('Text').text('丁真'))
            driver.wait(0.5)

            # 通过相对位置点击控件
            driver.touch(BY.isAfter(BY.key('input')).type('Image'))
            driver.wait(0.5)

            # 点击type为{Text}并且text为{位置}的控件
            driver.touch(BY.type('Text').text('位置'))
            driver.wait(2)

            # 点击type为{Button}并且text为{确认}的控件
            driver.touch(BY.type('Button').text('确认'))
            driver.wait(0.5)

            # 从(1101, 620)滑动至(1049, 2310)
            driver.slide((1101, 620), (1049, 2310))
            driver.wait(0.5)

            # 从(981, 429)滑动至(989, 2024)
            driver.slide((981, 429), (989, 2024))
            driver.wait(0.5)

            # 从(1073, 1547)滑动至(1272, 1420)
            driver.slide((1073, 1547), (1272, 1420))
            driver.wait(0.5)

        # 获取应用 PID
        pid_cmd = f"pidof {self.app_package}"
        pid = self.driver.shell(pid_cmd).strip()

        # 执行步骤1：与丁真的聊天操作
        execute_step_with_perf(self.driver, self.report_path, pid, 1, chat_with_dingzhen)

        # 执行步骤2：扫一扫和收付款操作
        execute_step_with_perf(self.driver, self.report_path, pid, 2, scan_and_payment)

        # 执行步骤3：发现和联系人操作
        execute_step_with_perf(self.driver, self.report_path, pid, 3, discover_and_contacts)
