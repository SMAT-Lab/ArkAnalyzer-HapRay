# coding: utf-8
import time

from hypium import BY

from hapray.core.perf_testcase import PerfTestCase


class ResourceUsage_PerformanceDynamic_Douyin_0200(PerfTestCase):

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
        # 1. 打开抖音，等待 5s
        self.start_app()

        # 2. 左滑进入‘经验’ tab页
        self.driver.swipe('RIGHT', 60, area=BY.id("topTabsMiddleSlot"))
        time.sleep(3)
        self.touch_by_text('经验', 5)

        # 3. 预先下滑预加载10次，再上滑8次
        self.swipes_up(10, 2, 100)
        self.swipes_down(8, 2, 100)

        def step1():
            self.swipes_up(5, 2, 100)
            self.swipes_down(5, 2, 100)

        self.execute_performance_step("抖音-经验页面浏览场景-step1经验页浏览", 30, step1)
