import time

from hypium import BY
from hypium.model import UiParam

from hapray.core.perf_testcase import PerfTestCase


class PerfLoad_Douyin_0040(PerfTestCase):
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
        self.start_app()

        component_toptabs = self.driver.find_component(BY.id('HomePage_Top_Tabs_Tree_Container'))
        self.driver.swipe(UiParam.RIGHT, area=component_toptabs, distance=60, start_point=(0.4, 0.1), swipe_time=0.4)
        time.sleep(2)

        def step1():
            # 点击精选
            # self.touch_by_id('home-top-tab-text-homepage_mediumvideo', 2)
            self.touch_by_text('精选', 5)

        def step2():
            for _i in range(3):
                # 点击横屏
                self.touch_by_text('全屏观看', 5)
                # 返回竖屏
                self.swipe_to_back(3)

        self.execute_performance_step('抖音-抖音热点页面-点击-页面切换-抖音长视频页面-step1点击长视频', 30, step1)
        # 点击第一个视频
        self.touch_by_coordinates(562, 549, 2)
        self.execute_performance_step(
            '抖音-视频书评播放页-点击-应用内操作-视频横屏播放页-step2进入横屏，观看10s，返回竖屏', 30, step2
        )
