# coding: utf-8
import time

from hypium import BY
from hypium.model import UiParam

from hapray.core.perf_testcase import PerfTestCase


class ResourceUsage_PerformanceDynamic_Douyin_0060(PerfTestCase):

    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(self.TAG, controllers)

        self._app_package = 'com.ss.hm.ugc.aweme'
        self._app_name = '抖音'
        self._steps = [
            {
                "name": "step1",
                "description": "1. 页签切换浏览"
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
        self.start_app()

        # 抖音-热点、关注、朋友tab页切换场景
        component_toptabs = self.driver.find_component(BY.id('HomePage_Top_Tabs_Tree_Container'))
        for _ in range(3):
            self.driver.swipe(UiParam.RIGHT, area=component_toptabs, distance=60, start_point=(0.4, 0.1),
                              swipe_time=0.4)
            time.sleep(2)
            component_hotspots = self.driver.find_component(BY.id('home-top-tab-text-homepage_pad_hot'))
            if component_hotspots:
                break

        def step1():
            # 1. 点击热点
            self.driver.touch(component_hotspots)
            time.sleep(2)

            # 2. 热点页面上滑3次
            self.swipes_up(3, 2, 300)

            # 3. 点击关注
            self.touch_by_id('home-top-tab-text-homepage_follow', 2)
            # 4. 关注页面上滑3次
            self.swipes_up(3, 2, 300)

            # 5. 点击朋友
            self.touch_by_id('main-bottom-tab-text-homepage_familiar', 2)
            # 6. 朋友页面上滑3次，间隔2秒
            self.swipes_up(3, 2, 300)

        self.execute_performance_step(1, step1, 35)
