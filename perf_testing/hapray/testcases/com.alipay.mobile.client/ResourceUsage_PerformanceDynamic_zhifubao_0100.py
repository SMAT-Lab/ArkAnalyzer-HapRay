# coding: utf-8
import os
import time

from devicetest.core.test_case import Step
from hypium import BY

from hapray.core.PerfTestCase import PerfTestCase, Log
from hapray.core.common.CommonUtils import CommonUtils


class ResourceUsage_PerformanceDynamic_zhifubao_0100(PerfTestCase):

    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(self.TAG, controllers)

        self._app_package = 'com.alipay.mobile.client'
        self._app_name = '支付宝'
        self._steps = [
            {
                "name": "step1",
                "description": "1. 支付宝-饿了么 页面浏览 上滑10次，间隔2s"
            },
            {
                "name": "step2",
                "description": "2. 支付宝-饿了么 店铺浏览 上滑10次，间隔2s"
            }
        ]

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
        Log.info('setup')
        os.makedirs(os.path.join(self.report_path, 'hiperf'), exist_ok=True)
        os.makedirs(os.path.join(self.report_path, 'htrace'), exist_ok=True)

    def process(self):
        self.driver.swipe_to_home()
        Step('启动被测应用')
        self.driver.start_app(self.app_package)
        self.driver.wait(5)
        # 点击 饿了么
        component = self.driver.find_component(BY.type('Text').text('饿了么'))
        self.driver.touch(component)
        time.sleep(5)

        def step1(driver):
            Step('1. 支付宝-饿了么 页面浏览 上滑10次，间隔2s')
            for i in range(10):
                CommonUtils.swipes_up_load(driver, 1, 2, 300)

        def step2(driver):
            Step('2. 支付宝-饿了么 任意店铺浏览 上滑10次，间隔2s')
            driver.touch((263, 1255))
            time.sleep(2)
            for i in range(10):
                CommonUtils.swipes_up_load(driver, 1, 2, 300)

        self.execute_step_with_perf_and_trace(1, step1, 30)
        time.sleep(10)
        self.execute_step_with_perf_and_trace(2, step2, 35)

    def teardown(self):
        Log.info('teardown')
        self.driver.stop_app(self.app_package)
        self.make_reports()
