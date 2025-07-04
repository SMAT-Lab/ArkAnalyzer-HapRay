# coding: utf-8

from devicetest.core.test_case import Step

from hapray.core.perf_testcase import PerfTestCase


class ResourceUsage_PerformanceDynamic_Douyin_0110(PerfTestCase):

    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(self.TAG, controllers)

        self._app_package = 'com.ss.hm.ugc.aweme'
        self._app_name = '抖音'
        self._steps = [
            {
                "name": "step1",
                "description": "1. 评论区图片放大/缩小"
            }
        ]
        # 原始采集设备的屏幕尺寸（Pura 70 Pro）
        self.source_screen_width = 1260
        self.source_screen_height = 2844

    @property
    def steps(self) -> list[dict[str, str]]:
        return self._steps

    @property
    def app_package(self) -> str:
        return self._app_package

    @property
    def app_name(self) -> str:
        return self._app_name

    def process(self):
        def start():
            self.start_app()

            # 2. 抖音点击“我”，等待 2s
            self.touch_by_text('我', 2)

            # 3. 点击私密
            self.touch_by_text('私密', 2)

            # 4. 点击第一个视频
            self.touch_by_coordinates(222, 1877, 2)

            # 5. 点击评论区
            self.touch_by_coordinates(1187, 1750, 2)

        def step1():
            Step('1. 点击评论区图片放大、侧滑缩小各5次，每次间隔1s')
            for _ in range(5):
                self.touch_by_key('comment_content')
                self.swipe_to_back(1)

        start()
        self.execute_performance_step(1, step1, 20)
