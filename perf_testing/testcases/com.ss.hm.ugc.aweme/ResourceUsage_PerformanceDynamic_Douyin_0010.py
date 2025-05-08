# coding: utf-8
import os
import time

from devicetest.core.test_case import Step
from hypium import BY

from aw.PerfTestCase import PerfTestCase, Log
from aw.common.CommonUtils import CommonUtils


class ResourceUsage_PerformanceDynamic_Douyin_0010(PerfTestCase):

    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(self.TAG, controllers)

        self._app_package = 'com.ss.hm.ugc.aweme'
        self._app_name = '抖音'
        self._steps = [
            {
                "name": "step1",
                "description": "1. 抖音“我”页面点击观看历史，等待2s"
            },
            {
                "name": "step2",
                "description": "2. 观看历史上滑5次，每次等待1s;观看历史下滑5次，每次等待1s"
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

    def process(self):
        def start(driver):
            Step('启动被测应用')
            driver.wake_up_display()
            time.sleep(1)
            self.driver.swipe_to_home()
            time.sleep(1)
            # 1. 打开抖音，等待 5s
            self.driver.start_app(self.app_package)
            driver.wait(2)  # 等待应用启动
            time.sleep(3)

            # 2. 抖音点击“我”，等待 2s
            driver.touch(BY.text('我'))
            time.sleep(2)

            # 3. 抖音“我”页面点击右上角选项，等待2s
            driver.touch((1114, 180))
            time.sleep(2)

        def step1(driver):
            Step('1. 抖音“我”页面点击观看历史，等待2s')
            component = driver.find_component(BY.text('观看历史'))
            if not component:
                component = (758, 726)
            driver.touch(component)
            time.sleep(2)

        def step2(driver):
            Step('2. 观看历史上滑5次，每次等待1s;观看历史下滑5次，每次等待1s')
            for _ in range(5):
                CommonUtils.swipes_up_load(driver, 1, 1, 300)

            for _ in range(5):
                CommonUtils.swipes_down_load(driver, 1, 1, 300)

        def finish(driver):
            for _ in range(6):
                driver.swipe_to_back()
                time.sleep(1)
            driver.swipe_to_home()

        start(self.driver)
        self.execute_step_with_perf_and_trace(1, step1, 10)
        self.execute_step_with_perf_and_trace(2, step2, 20)
        finish(self.driver)

    def teardown(self):
        Log.info('teardown')
        self.driver.stop_app(self.app_package)
        self.make_reports()
