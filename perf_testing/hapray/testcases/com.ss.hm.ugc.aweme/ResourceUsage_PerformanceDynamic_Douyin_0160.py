# coding: utf-8

from hapray.core.perf_testcase import PerfTestCase


class ResourceUsage_PerformanceDynamic_Douyin_0160(PerfTestCase):

    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(self.TAG, controllers)

        self._app_package = 'com.ss.hm.ugc.aweme'
        self._app_name = '抖音'
        self._steps = [
            {
                "name": "step1",
                "description": "1. 图文视频轮播"
            },
            {
                "name": "step2",
                "description": "2. 弹幕视频轮播"
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
            # 1. 打开抖音，等待 5s
            self.start_app(5)

            # 2. 抖音点击“我”，等待 2s
            self.touch_by_text('我', 2)

            # 3. 点击收藏
            self.touch_by_text('收藏', 2)

            # 4. 点击进入第一个视频
            self.touch_by_coordinates(235, 2020, 2)

        def step1():
            # 观看收藏的5个固定图文轮播视频，每个观看10s
            self.swipes_up(5, 10, 300)

        def step2():
            # 观看收藏的5个固定带弹幕的视频，每个观看10s
            self.swipes_up(5, 10, 300)

        start()
        self.execute_performance_step(1, step1, 60)
        self.execute_performance_step(2, step2, 60)
