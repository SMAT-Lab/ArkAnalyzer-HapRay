# coding: utf-8
import os
import time

from devicetest.core.test_case import Step
from hypium import BY

from hapray.core.perf_testcase import PerfTestCase, Log


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

    def setup(self):
        Log.info('setup')
        os.makedirs(os.path.join(self.report_path, 'hiperf'), exist_ok=True)
        os.makedirs(os.path.join(self.report_path, 'htrace'), exist_ok=True)

    def process(self):
        self.driver.swipe_to_home()

        Step('启动被测应用')
        self.driver.start_app(self.app_package)
        self.driver.wait(5)

        def step1(driver):
            Step('1. 支付宝-首页扫一扫')
            component = driver.find_component(BY.type('Text').text('扫一扫'))
            driver.touch(component)
            time.sleep(5)

        def step2(driver):
            Step('2. 支付宝-点击“相册”按钮')
            component = driver.find_component(BY.type('Text').text('相册'))
            driver.touch(component)
            time.sleep(5)

        def finish(driver):
            # 上滑返回桌面
            driver.swipe_to_home()
            time.sleep(2)

        self.execute_performance_step(1, step1, 10)
        time.sleep(10)
        self.execute_performance_step(2, step2, 10)
        finish(self.driver)

    def teardown(self):
        Log.info('teardown')
        self.driver.stop_app(self.app_package)
        self.generate_reports()
