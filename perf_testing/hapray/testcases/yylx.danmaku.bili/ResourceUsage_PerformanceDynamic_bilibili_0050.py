# coding: utf-8
import os
import time

from devicetest.core.test_case import Step
from hypium import BY

from hapray.core.perf_testcase import PerfTestCase, Log


class ResourceUsage_PerformanceDynamic_bilibili_0050(PerfTestCase):

    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(self.TAG, controllers)
        self._activityName = 'EntryAbility'
        self._app_package = 'yylx.danmaku.bili'
        self._app_name = '哔哩哔哩'
        self._steps = [
            {
                "name": "step1",
                "description": "1. 观看哔哩哔哩王者荣耀赛事直播，观看60s"
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
        def step1(driver):
            time.sleep(5)

        Step('启动被测应用')
        self.driver.start_app(self.app_package, self._activityName)
        self.driver.wait(5)

        # 点击直播
        self.driver.touch(BY.text('直播'))
        time.sleep(2)
        # 点击哔哩哔哩王者荣耀赛事
        self.driver.touch(BY.text('哔哩哔哩王者荣耀赛事'))
        time.sleep(2)

        self.execute_performance_step(1, step1, 5)

        # 侧滑2次返回哔哩哔哩首页
        for i in range(2):
            self.driver.swipe_to_back()
            time.sleep(1)

    def teardown(self):
        Log.info('teardown')
        self.driver.stop_app(self.app_package)
        self.generate_reports()
