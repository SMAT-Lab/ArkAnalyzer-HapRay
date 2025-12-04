import time

from hypium import BY

from hapray.core.perf_testcase import PerfTestCase


class PerfLoad_bilibili_0030(PerfTestCase):
    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(self.TAG, controllers)
        self._app_package = 'yylx.danmaku.bili'
        self._app_name = '哔哩哔哩'
        self.source_screen_width = 1084
        self.source_screen_height = 2412

    @property
    def app_package(self) -> str:
        return self._app_package

    @property
    def app_name(self) -> str:
        return self._app_name

    def process(self):
        def step1():
            # 竖屏视频播放30s
            time.sleep(10)

        def step2():
            # 点击视频中间，点击全屏按钮，全屏播放30s
            # 1. 点击视频中间，等待1s
            self.touch_by_coordinates(600, 500, 1)

            # 2. 点击全屏按钮，等待1s
            self.touch_by_coordinates(1018, 1474, 1)

            # 3. 全屏播放30s
            time.sleep(30)

        def step3():
            # 点击视频中间，点击关闭弹幕，全屏播放30s
            self.driver.touch((1416, 680))
            time.sleep(1)

            # 2. 点击关闭弹幕，等待1s
            self.touch_by_coordinates(102, 2241, 1)

            # 3. 全屏播放30s
            time.sleep(30)

        # 启动被测应用
        self.start_app()

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
        self.touch_by_coordinates(600, 500, 1)
        self.touch_by_coordinates(66, 1473, 1)

        # 点击到视频00分00秒
        self.touch_by_coordinates(155, 1474, 1)
        time.sleep(1)

        # 点击视频播放
        self.touch_by_coordinates(66, 1473, 1)

        # 竖屏视频播放30s
        self.execute_performance_step('哔哩哔哩-竖屏视频播放场景-step1视频播放', 30, step1)
        self.execute_performance_step('哔哩哔哩-竖屏视频播放场景-step2全屏播放', 40, step2)
        self.execute_performance_step('哔哩哔哩-竖屏视频播放场景-step3关闭弹幕', 40, step3)
