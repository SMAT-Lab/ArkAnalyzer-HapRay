# coding: utf-8
import os
import time

from devicetest.core.test_case import Step
from hypium import BY

from hapray.core.PerfTestCase import PerfTestCase, Log


class ResourceUsage_PerformanceDynamic_xhs_0020(PerfTestCase):

    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(self.TAG, controllers)

        self._app_package = 'com.xingin.xhs_hos'
        self._app_name = '小红书'
        self._steps = [
            {
                "name": "step1",
                "description": "1. 搜索 穿搭图片"
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
            Step('1. 搜索 穿搭图片')

            # 点击右上角搜索，停留1s
            # driver.touch((1215， 205))
            driver.touch((1169, 195)) # Mate60Pro  Mate70
            time.sleep(1)
            for i in range(3):
                driver.input_text((300, 200), '穿搭图片')
                time.sleep(1)
                driver.touch(BY.text('搜索'))
                time.sleep(2)
                driver.swipe_to_back()
                time.sleep(2)

        self.execute_step_with_perf_and_trace(1, step1, 20)

    def teardown(self):
        Log.info('teardown')
        self.driver.stop_app(self.app_package)
        self.make_reports()
