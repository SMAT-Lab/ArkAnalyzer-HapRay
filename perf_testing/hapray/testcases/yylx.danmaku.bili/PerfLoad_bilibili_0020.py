import time

from hypium import BY

from hapray.core.perf_testcase import PerfTestCase


class PerfLoad_bilibili_0020(PerfTestCase):
    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(self.TAG, controllers)
        self._app_package = 'yylx.danmaku.bili'
        self._app_name = '哔哩哔哩'
        # 原始采集设备的屏幕尺寸（Nova 14）
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
            # 视频播放30s
            time.sleep(30)

        def step2():
            # 视频区评论
            time_start = time.time()
            # 评论区上滑10次
            self.swipes_up(10, 2)

            # 评论区下滑10次
            self.swipes_down(10, 2)
            time_end = time.time()
            if time_end - time_start < 60:
                time.sleep(60 - (time_end - time_start))

        def step3():
            # 全屏播放30s
            # 1. 点击视频中间，等待1s
            self.touch_by_coordinates(600, 500, 1)

            # 2. 点击全屏按钮，等待1s
            self.touch_by_coordinates(1018, 637, 1)

            # 3. 全屏播放30s
            time.sleep(30)

        def step4():
            # 关闭弹幕，全屏播放30s

            # 1. 点击视频中间，等待1s
            self.driver.touch((1416, 680))
            time.sleep(1)

            # 2. 点击关闭弹幕，等待1s
            self.touch_by_coordinates(486, 1000, 1)

            # 3. 全屏播放30s
            time.sleep(30)

        def step5():
            #  长按视频中间，倍速播放30s
            time_start = time.time()
            # 1. 长按视频中间
            self.driver.long_click((1416, 680), press_time=30)
            time.sleep(1)
            time_end = time.time()
            if time_end - time_start < 30:
                time.sleep(30 - (time_end - time_start))

        # 启动被测应用
        self.start_app()

        # 点击“我的”页面
        self.driver.touch(BY.text('我的'))
        time.sleep(2)

        # 点击“我的收藏”
        self.driver.touch(BY.text('我的收藏'))
        time.sleep(2)

        # 点击播放”航拍中国第一季“
        self.driver.touch(BY.text('航拍中国 第一季'))
        time.sleep(2)

        # 暂停播放
        self.touch_by_coordinates(600, 500, 1)
        self.touch_by_coordinates(66, 637, 1)

        # 点击到视频00分00秒
        self.touch_by_coordinates(156, 637, 1)
        time.sleep(1)

        # 点击视频播放
        self.touch_by_coordinates(66, 637, 1)

        # 视频播放30s
        self.execute_performance_step('哔哩哔哩-横屏视频播放场景-step1视频播放', 30, step1)
        # 点击评论
        self.driver.touch(BY.text('评论'))
        time.sleep(3)
        self.execute_performance_step('哔哩哔哩-横屏视频播放场景-step2评论区滑动', 60, step2)
        self.execute_performance_step('哔哩哔哩-横屏视频播放场景-step3全屏播放', 40, step3)
        self.execute_performance_step('哔哩哔哩-横屏视频播放场景-step4关闭弹幕', 40, step4)
        self.execute_performance_step('哔哩哔哩-横屏视频播放场景-step5倍速播放', 30, step5)
