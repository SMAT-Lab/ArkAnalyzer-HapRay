# coding: utf-8
import time

from devicetest.core.test_case import Step
from hypium import BY

from hapray.core.perf_testcase import PerfTestCase


class ResourceUsage_PerformanceDynamic_zhifubao_0020(PerfTestCase):

    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(self.TAG, controllers)

        self._app_package = 'com.alipay.mobile.client'
        self._app_name = '支付宝'
        self._steps = [
            {
                "name": "step1",
                "description": "1. 支付宝-首页扫一扫"
            },
            {
                "name": "step2",
                "description": "2. 支付宝-点击“相册”按钮"
            }
        ]

    @property
    def steps(self) -> list:
        return self._steps

    @property
    def app_package(self) -> str:
        return self._app_package

    @property
    def app_name(self) -> str:
        return self._app_name

    def process(self):
        self.driver.swipe_to_home()

        Step('启动被测应用')
        self.driver.start_app(self.app_package)
        self.driver.wait(5)

        def step1():
            Step('1. 支付宝-首页扫一扫')
            component = self.driver.find_component(BY.type('Text').text('扫一扫'))
            self.driver.touch(component)
            time.sleep(5)

        def step2():
            Step('2. 支付宝-点击“相册”按钮')
            component = self.driver.find_component(BY.type('Text').text('相册'))
            self.driver.touch(component)
            time.sleep(5)

        def finish():
            # 上滑返回桌面
            self.driver.swipe_to_home()
            time.sleep(2)

        self.execute_performance_step(1, step1, 10)
        time.sleep(10)
        self.execute_performance_step(2, step2, 10)
        finish()
