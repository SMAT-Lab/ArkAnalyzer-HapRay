# coding: utf-8
import time

from devicetest.core.test_case import Step
from hypium import BY

from hapray.core.perf_testcase import PerfTestCase


class ResourceUsage_PerformanceDynamic_bilibili_0030(PerfTestCase):

    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(self.TAG, controllers)
        self._activityName = 'EntryAbility'
        self._app_package = 'yylx.danmaku.bili'
        self._app_name = '哔哩哔哩'
        self._steps = [
            {
                "name": "step1",
                "description": "1. 竖屏视频播放30s"
            },
            {
                "name": "step2",
                "description": "2. 点击视频中间，点击全屏按钮，全屏播放30s"
            },
            {
                "name": "step3",
                "description": "3. 点击视频中间，点击关闭弹幕，全屏播放30s"
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
            Step('1. 竖屏视频播放30s')
            time.sleep(10)

        def step2():
            Step('2. 点击视频中间，点击全屏按钮，全屏播放30s')
            # 1. 点击视频中间，等待1s
            self.driver.touch((600, 500))
            time.sleep(1)

            # 2. 点击全屏按钮，等待1s
            self.driver.touch((1188, 1670))  # Mate60 Pro
            # driver.touch((1144, 709))  # Mate70
            time.sleep(1)

            # 3. 全屏播放30s
            time.sleep(10)

        def step3():
            Step('3. 点击视频中间，点击关闭弹幕，全屏播放30s')
            # 1. 点击视频中间，等待1s
            self.driver.touch((630, 1373))
            time.sleep(1)

            # 2. 点击关闭弹幕，等待1s
            self.driver.touch((90, 2519))  # Mate60 Pro
            # driver.touch((526, 1125))  # Mate70
            time.sleep(1)

            # 3. 全屏播放30s
            time.sleep(10)

        Step('启动被测应用')
        self.driver.start_app(self.app_package, self._activityName)
        self.driver.wait(5)

        # 点击“我的”页面
        self.driver.touch(BY.text('我的'))
        time.sleep(2)

        # 点击“我的收藏”
        self.driver.touch(BY.text('我的收藏'))
        time.sleep(2)

        # 点击播放”当各省风景出现在课本上“
        self.driver.touch(BY.text('“当各省风景出现在课本上”'))
        self.driver.wait(0.5)
        time.sleep(2)

        # 暂停播放
        self.driver.touch((600, 500))
        time.sleep(1)
        self.driver.touch((71, 1670))
        # self.driver.touch((71, 709)) # Mate70
        time.sleep(1)

        # 点击到视频00分00秒
        self.driver.touch((169, 1670))
        self.driver.wait(0.5)
        # self.driver.touch((169, 709)) # Mate70

        # 点击视频播放
        self.driver.touch((71, 1670))
        # self.driver.touch((71, 709))  # Mate70
        time.sleep(1)

        # 竖屏视频播放30s
        self.execute_performance_step(1, step1, 30)
        self.execute_performance_step(2, step2, 40)
        self.execute_performance_step(3, step3, 40)

        # 侧滑4次返回哔哩哔哩首页
        for i in range(4):
            self.driver.swipe_to_back()
            time.sleep(1)
