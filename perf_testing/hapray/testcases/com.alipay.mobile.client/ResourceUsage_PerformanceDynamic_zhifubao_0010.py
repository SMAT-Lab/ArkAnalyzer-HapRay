# coding: utf-8
import os
import time

from devicetest.core.test_case import Step
from hypium import BY

from hapray.core.PerfTestCase import PerfTestCase, Log
from hapray.core.common.CommonUtils import CommonUtils


class ResourceUsage_PerformanceDynamic_zhifubao_0010(PerfTestCase):

    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(self.TAG, controllers)

        self._app_package = 'com.alipay.mobile.client'
        self._app_name = '支付宝'
        self._steps = [
            {
                "name": "step1",
                "description": "1. 支付宝-首页上下滑5次，间隔2s"
            },
            {
                "name": "step2",
                "description": "2. 支付宝-切换回到支付宝主界面"
            },
            {
                "name": "step3",
                "description": "3. 支付宝-点击收付款"
            },
            {
                "name": "step4",
                "description": "4. 支付宝-点击收转账"
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
        os.makedirs(os.path.join(self.report_path, 'report'), exist_ok=True)
        os.makedirs(os.path.join(self.report_path, 'htrace'), exist_ok=True)

    def process(self):
        self.driver.swipe_to_home()

        Step('启动被测应用')
        self.driver.start_app(self.app_package)
        self.driver.wait(5)

        def step1(driver):
            Step('1. 支付宝-首页上下滑5次，间隔2s')
            for i in range(5):
                CommonUtils.swipe(driver.device_sn, 625, 2000, 625, 1000, 300)
                time.sleep(2)
            for i in range(5):
                CommonUtils.swipe(driver.device_sn, 625, 1100, 625, 2100, 300)
                time.sleep(2)
            time.sleep(3)

        def without_perf_after_step1(driver):
            driver.touch(BY.type('Text').text('出行'))
            time.sleep(2)
            # 点击地铁，切换到地铁页
            driver.touch((327, 348))
            time.sleep(2)
            # 侧滑返回上一页
            driver.swipe_to_back()
            time.sleep(2)
            # 点击卡包
            # driver.touch((1157, 401))
            driver.touch(BY.type('Text').text('卡包'))
            time.sleep(2)
            # 返回上一页
            driver.touch((88, 208))
            time.sleep(2)
            # 点击“我的”
            # driver.touch((1180, 2631))
            driver.touch(BY.type('Text').text('我的'))
            time.sleep(2)

        def step2(driver):
            Step('2. 支付宝-切换回到支付宝主界面')
            component = driver.find_component(BY.type('Text').text('首页'))
            driver.touch(component)
            time.sleep(5)

        def step3(driver):
            Step('3. 支付宝-点击收付款')
            component = driver.find_component(BY.type('Text').text('收付款'))
            driver.touch(component)
            time.sleep(5)

        def step4(driver):
            Step('4. 支付宝-点击收转账')
            # component = driver.find_component(BY.type('Text').text('转账'))
            # driver.touch(component)
            # driver.touch((662, 2330))  # TODO Mate60
            driver.touch((662, 2520))  # TODO Mate70
            time.sleep(5)

        def finish(driver):
            # 点击右上角关闭
            # driver.touch((1131, 181))  # TODO Mate60
            driver.touch((1224, 216))  # TODO Mate70
            time.sleep(2)
            # 侧滑返回
            driver.swipe_to_back()
            time.sleep(2)
            # 上滑返回桌面
            driver.swipe_to_home()

        self.execute_step_with_perf_and_trace(1, step1, 30)
        time.sleep(10)
        without_perf_after_step1(self.driver)
        self.execute_step_with_perf_and_trace(2, step2, 10)
        self.execute_step_with_perf_and_trace(3, step3, 10)
        self.execute_step_with_perf_and_trace(4, step4, 10)
        finish(self.driver)

    def teardown(self):
        Log.info('teardown')
        self.driver.stop_app(self.app_package)
        self.make_reports()
