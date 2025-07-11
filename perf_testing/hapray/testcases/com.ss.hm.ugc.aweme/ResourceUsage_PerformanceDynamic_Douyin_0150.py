# coding: utf-8
import time

from hypium import BY

from hapray.core.perf_testcase import PerfTestCase


class ResourceUsage_PerformanceDynamic_Douyin_0150(PerfTestCase):

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

            # 2. 点击搜索框，输入【与辉同行】
            self.touch_by_id('topTabsRightSlot', 2)
            self.driver.input_text(BY.type('TextInput'), '与辉同行')
            time.sleep(2)
            self.touch_by_id('search_button')

            # 3. 预加载
            self.swipes_up(15, 1, 300)
            self.swipes_down(10, 1, 300)

        def step1():
            # 搜索列表上滑10次，每次间隔1s
            self.swipes_up(10, 1, 300)
            self.swipes_down(10, 1, 300)

        start()
        self.execute_performance_step("抖音-搜索列表滑动场景-step1搜索列表浏览", 35, step1)
