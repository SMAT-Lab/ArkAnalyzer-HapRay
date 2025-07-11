# coding: utf-8
import time

from hypium import BY

from hapray.core.perf_testcase import PerfTestCase


class ResourceUsage_PerformanceDynamic_bilibili_0050(PerfTestCase):

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
            time.sleep(60)

        self.start_app()

        # 点击直播
        self.driver.touch(BY.text('直播'))
        time.sleep(2)
        # 点击哔哩哔哩王者荣耀赛事
        self.driver.touch(BY.text('哔哩哔哩王者荣耀赛事'))
        time.sleep(2)

        self.execute_performance_step("哔哩哔哩-直播播放场景-step1直播播放", 60, step1)
