# coding: utf-8

from hapray.core.perf_testcase import PerfTestCase


class ResourceUsage_PerformanceDynamic_compose_0030(PerfTestCase):

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
            self.touch_by_text('CApi 1500Image', 5)
            self.swipes_up(5, 2)
            self.swipes_down(5, 2)

        def step2():
            self.touch_by_text('Compose 1500Image CApi', 5)
            self.swipes_up(5, 2)
            self.swipes_down(5, 2)

        self.swipes_up(1, 2)

        self.execute_performance_step("ComposeSample-1500Image测试场景-step1 CApi 1500Image", 30, step1,
                                      sample_all_processes=False)
        self.driver.swipe_to_back()
        self.execute_performance_step("ComposeSample-1500Image测试场景-step2 1500Image CApi", 30, step2,
                                      sample_all_processes=False)
        self.driver.swipe_to_back()
