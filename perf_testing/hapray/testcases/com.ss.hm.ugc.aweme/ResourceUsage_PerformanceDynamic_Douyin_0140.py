# coding: utf-8
import time

from hypium import BY
from hypium.model import UiParam

from hapray.core.perf_testcase import PerfTestCase


class ResourceUsage_PerformanceDynamic_Douyin_0140(PerfTestCase):

    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(self.TAG, controllers)

        self._app_package = 'com.ss.hm.ugc.aweme'
        self._app_name = '抖音'
        # 原始采集设备的屏幕尺寸（Pura 70 Pro）
        self.source_screen_width = 1260
        self.source_screen_height = 2844

    @property
    def app_package(self) -> str:
        return self._app_package

    @property
    def app_name(self) -> str:
        return self._app_name

    def process(self):
        def start():
            # 1. 打开抖音，等待 5s
            self.start_app()

            component_toptabs = self.driver.find_component(BY.id('HomePage_Top_Tabs_Tree_Container'))
            self.driver.swipe(UiParam.RIGHT, area=component_toptabs, distance=60, start_point=(0.4, 0.1),
                              swipe_time=0.4)
            time.sleep(2)
            self.touch_by_id('home-top-tab-text-homepage_pad_hot', 5)

            # 2. 点击第一个抖音热榜进入视频页，点击进入第一个视频
            self.touch_by_text('1', 2)

        def step1():
            # 点击底部热榜，左右拖滑切换tab页5次，每次间隔2s'
            self.touch_by_text('热榜', 2)
            self.swipes_left(5, 2, 300)
            self.swipes_right(5, 2, 300)

        def step2():
            # 点击下一个热榜跳转视频，每次间隔10s
            for _ in range(5):
                self.touch_by_coordinates(1196, 2621, 10)

        start()
        self.execute_performance_step("抖音-热榜浏览场景-step1热榜页签切换", 30, step1)
        self.driver.swipe_to_back()
        time.sleep(5)
        self.execute_performance_step("抖音-热榜浏览场景-step2热榜视频跳转", 60, step2)
