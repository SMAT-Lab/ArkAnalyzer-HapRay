# coding: utf-8
import time

from devicetest.core.test_case import Step
from hypium import BY

from hapray.core.perf_testcase import PerfTestCase


class ResourceUsage_PerformanceDynamic_bilibili_0010(PerfTestCase):

    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(self.TAG, controllers)
        self._activityName = 'EntryAbility'
        self._app_package = 'yylx.danmaku.bili'
        self._app_name = '哔哩哔哩'
        self._steps = [
            {
                "name": "step1",
                "description": "1. 哔哩哔哩首页-推荐页面上滑10次，下滑10次，间隔2秒"
            },
            {
                "name": "step2",
                "description": "2. 点击4次，每次等待5秒"
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
        def step1():
            Step('b站首页上滑操作')
            self.swipes_up(swip_num=10, sleep=2)
            Step('b站首页下滑操作')
            self.swipes_down(swip_num=10, sleep=2)

        def step2():
            # 点击“追番”页面，等待5秒
            self.driver.touch(BY.text('追番'))
            time.sleep(5)

            # 点击“影视”页面，等待5秒
            self.driver.touch(BY.text('影视'))
            time.sleep(5)

            # 点击“我的”页面，等待5秒
            self.driver.touch(BY.text('我的'))
            time.sleep(5)

            # 点击“关注”页面，等待5秒
            self.driver.touch(BY.text('关注'))
            time.sleep(5)

        Step('启动被测应用')
        self.driver.start_app(self.app_package, self._activityName)
        self.driver.wait(5)

        self.execute_performance_step(1, step1, 60)

        # 点击哔哩哔哩“热门”页面，停留3秒
        self.driver.touch(BY.text('热门'))
        time.sleep(3)

        # 哔哩哔哩“热门”页面，上滑3次
        Step('b站“热门”页上滑操作')
        self.swipes_up(swip_num=3, sleep=2)

        self.execute_performance_step(2, step2, 20)
