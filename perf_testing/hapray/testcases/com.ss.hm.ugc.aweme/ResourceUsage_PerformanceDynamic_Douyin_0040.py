import time

from hypium import BY
from hypium.model import UiParam

from hapray.core.perf_testcase import PerfTestCase


class ResourceUsage_PerformanceDynamic_Douyin_0040(PerfTestCase):
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
        def step1():
            # 抖音点击直播页签
            self.touch_by_text('直播', 2)

        def step2():
            # 直播页签上滑5次，每次等待10s
            self.swipes_up(5, 10, 300)

        self.start_app()

        component_toptabs = self.driver.find_component(BY.id('HomePage_Top_Tabs_Tree_Container'))
        for _ in range(3):
            self.driver.swipe(
                UiParam.RIGHT, area=component_toptabs, distance=60, start_point=(0.4, 0.1), swipe_time=0.4
            )
            time.sleep(2)
            component_live = self.driver.find_component(BY.id('home-top-tab-text-homepage_tablive'))
            if component_live:
                break
        self.execute_performance_step('抖音-视频直播浏览场景-step1抖音点击直播页签', 30, step1)
        self.execute_performance_step('抖音-视频直播浏览场景-step2直播页浏览', 60, step2)
