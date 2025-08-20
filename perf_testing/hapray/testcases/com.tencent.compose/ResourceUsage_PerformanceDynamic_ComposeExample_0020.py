# coding: utf-8

from hapray.core.perf_testcase import PerfTestCase


class ResourceUsage_PerformanceDynamic_ComposeExample_0020(PerfTestCase):

    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(self.TAG, controllers)
        self._app_package = 'com.tencent.compose'
        self._app_name = 'ComposeSample'
        # 原始采集设备的屏幕尺寸（Nova 14）
        self.source_screen_width = 1084
        self.source_screen_height = 2412

    @property
    def app_package(self) -> str:
        return self._app_package

    @property
    def app_name(self) -> str:
        return self._app_name

    def process(self):
        self.driver.swipe_to_home()

        self.driver.start_app(self.app_package)
        self.driver.wait(5)

        def step1():
            self.touch_by_text('AutoScrollingInfiniteList', 8)
            self.swipes_up(5, 2)
            self.swipes_down(5, 2)

        self.swipes_up(1, 2)
        self.execute_performance_step("ComposeSample-活动列表测试场景-step1 AutoScrollingInfiniteList", 30, step1,
                                      sample_all_processes=True)
        self.driver.swipe_to_back()
