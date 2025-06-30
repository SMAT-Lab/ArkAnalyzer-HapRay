# coding: utf-8
import os
import time

from devicetest.core.test_case import Step
from hypium import BY

from hapray.core.perf_testcase import PerfTestCase, Log


class ResourceUsage_PerformanceDynamic_zhifubao_0060(PerfTestCase):

    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(self.TAG, controllers)

        self._app_package = 'com.alipay.mobile.client'
        self._app_name = '支付宝'
        self._steps = [
            {
                "name": "step1",
                "description": "1. 支付宝-理财-我的-消息-首页"
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
            Step('1. 支付宝-理财-我的-消息-首页')
            component = driver.find_component(BY.type('Text').text('理财'))
            driver.touch(component)
            time.sleep(5)
            # 点击 “我的”
            # driver.touch((1178, 2640))
            component = driver.find_component(BY.type('Text').text('我的'))
            driver.touch(component)
            time.sleep(5)
            # 点击 “消息”
            # driver.touch((924, 2618))
            component = driver.find_component(BY.type('Text').text('消息'))
            driver.touch(component)
            time.sleep(5)
            component = driver.find_component(BY.type('Text').text('首页'))
            driver.touch(component)
            time.sleep(5)

        def finish(driver):
            time.sleep(10)
            driver.swipe_to_home()

        self.execute_performance_step(1, step1, 30)
        finish(self.driver)

    def teardown(self):
        Log.info('teardown')
        self.driver.stop_app(self.app_package)
        self.generate_reports()
