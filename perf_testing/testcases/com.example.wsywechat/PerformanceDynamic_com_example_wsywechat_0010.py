# !/usr/bin/env python
# coding: utf-8

import os
from devicetest.core.test_case import Step

from hypium.model import KeyCode
from hypium import BY

from aw.PerfTestCase import PerfTestCase


class PerformanceDynamic_com_example_wsywechat_0010(PerfTestCase):

    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(self.TAG, controllers)

        self._app_package = 'com.example.wsywechat'
        self._app_name = 'mini wechat'
        self._steps = [
            {
                "name": "step1",
                "description": "1. 启动微信"
            },
            {
                "name": "step2",
                "description": "2. 与丁真聊天"
            },
            {
                "name": "step3",
                "description": "3. 返回桌面"
            }]

    @property
    def steps(self) -> []:
        return self._steps

    @property
    def app_package(self) -> str:
        return self._app_package

    @property
    def app_name(self) -> str:
        return self._app_name

    def setup(self):
        os.makedirs(os.path.join(self.report_path, 'hiperf'), exist_ok=True)
        os.makedirs(os.path.join(self.report_path, 'report'), exist_ok=True)

    def teardown(self):
        self.driver.stop_app(self.app_package)
        self.make_reports()

    def process(self):
        # 定义步骤1的动作函数：与丁真的聊天操作
        def chat_with_dingzhen(driver):
            Step('1. 与丁真的聊天操作')
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
            Step('2. 扫一扫和收付款操作')

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
            Step('3. 发现和联系人操作')
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

        self.driver.swipe_to_home()
        self.driver.start_app(package_name=self.app_package)

        # 执行步骤1：与丁真的聊天操作
        self.execute_step_with_perf(1, chat_with_dingzhen)

        # 执行步骤2：扫一扫和收付款操作
        self.execute_step_with_perf(2, scan_and_payment)

        # 执行步骤3：发现和联系人操作
        self.execute_step_with_perf(3, discover_and_contacts)
