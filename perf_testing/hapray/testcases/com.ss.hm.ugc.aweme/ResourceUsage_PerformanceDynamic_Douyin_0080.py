# coding: utf-8
import time

from devicetest.core.test_case import Step
from hypium import BY
from hypium.model import UiParam

from hapray.core.perf_testcase import PerfTestCase


class ResourceUsage_PerformanceDynamic_Douyin_0080(PerfTestCase):

    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(self.TAG, controllers)

        self._app_package = 'com.ss.hm.ugc.aweme'
        self._app_name = '抖音'
        self._steps = [
            {
                "name": "step1",
                "description": "1. 点击热榜"
            },
            {
                "name": "step2",
                "description": "2. 滑动浏览"
            },
            {
                "name": "step3",
                "description": "3. 侧滑返回"
            },
            {
                "name": "step4",
                "description": "4. 点击长视频"
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
        Step('启动被测应用')
        self.start_app()

        # 2. 点击热点，等待5s
        component_toptabs = self.driver.find_component(BY.id('HomePage_Top_Tabs_Tree_Container'))
        self.driver.swipe(UiParam.RIGHT, area=component_toptabs, distance=60, start_point=(0.4, 0.1),
                          swipe_time=0.4)
        time.sleep(2)
        self.touch_by_id('home-top-tab-text-homepage_pad_hot', 5)

        def step1():
            # 点击查看热榜，等待2s
            self.touch_by_text('完整热榜', 2)

        def step2():
            # 抖音热榜左滑5次，右滑5次，每次等待1s
            self.swipes_left(5, 1, 300)
            self.swipes_right(5, 1, 300)

        def step3():
            # 侧滑返回热点，等待2s
            self.swipe_to_back(2)

        def step4():
            # 点击长视频
            self.touch_by_id('home-top-tab-text-homepage_mediumvideo')

        self.execute_performance_step(1, step1, 10)
        self.execute_performance_step(2, step2, 20)
        self.execute_performance_step(3, step3, 10)
        self.execute_performance_step(4, step4, 30)
