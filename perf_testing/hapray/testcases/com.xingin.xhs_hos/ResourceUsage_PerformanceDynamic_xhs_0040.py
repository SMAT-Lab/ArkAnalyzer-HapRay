# coding: utf-8
import time

from hapray.core.perf_testcase import PerfTestCase


class ResourceUsage_PerformanceDynamic_xhs_0040(PerfTestCase):

    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(self.TAG, controllers)

        self._app_package = 'com.xingin.xhs_hos'
        self._app_name = '小红书'
        self._steps = [
            {
                "name": "step1",
                "description": "1. 观看长视频"
            }
        ]
        # 原始采集设备的屏幕尺寸（Mate 60 Pro）
        self.source_screen_width = 1260
        self.source_screen_height = 2720

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
        # 启动被测应用
        self.start_app()

        # 首页点击 ”我“
        self.touch_by_text('我', 1)
        # ”我“ 页面点击“收藏”
        self.touch_by_text('收藏', 1)

        video_tag = '一口气看完历史上最荒唐的王朝北齐！'

        def step1():
            # 点击收藏的视频链接“一口气看完历史上最荒唐的王朝北齐！”，观看20s')
            self.touch_by_text(video_tag, 20)

        def step2():
            self.touch_by_text('全屏观看', 10)
            self.driver.swipe_to_back()
            time.sleep(5)

        self.find_by_text_up(video_tag)
        self.execute_performance_step(1, step1, 20)
        self.execute_performance_step(2, step2, 20)
