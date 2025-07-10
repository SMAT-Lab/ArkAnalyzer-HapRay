# coding: utf-8
import time

from hypium import BY

from hapray.core.perf_testcase import PerfTestCase


class ResourceUsage_PerformanceDynamic_bilibili_0010(PerfTestCase):

    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(self.TAG, controllers)
        self._app_package = 'yylx.danmaku.bili'
        self._app_name = '哔哩哔哩'

    @property
    def app_package(self) -> str:
        return self._app_package

    @property
    def app_name(self) -> str:
        return self._app_name

    def process(self):
        def step1():
            # b站首页上滑操作
            self.swipes_up(swip_num=10, sleep=2)
            # b站首页下滑操作
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

        # 启动被测应用
        self.start_app()

        self.execute_performance_step("哔哩哔哩-首页浏览场景-step1首页滑动", 60, step1)

        # 点击哔哩哔哩“热门”页面，停留3秒
        self.driver.touch(BY.text('热门'))
        time.sleep(3)

        # 哔哩哔哩“热门”页面，上滑3次
        self.swipes_up(swip_num=3, sleep=2)

        self.execute_performance_step("哔哩哔哩-首页浏览场景-step2页面点击", 30, step2)
