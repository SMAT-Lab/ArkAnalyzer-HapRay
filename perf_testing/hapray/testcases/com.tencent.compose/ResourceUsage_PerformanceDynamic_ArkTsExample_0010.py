# coding: utf-8

from hapray.core.perf_testcase import PerfTestCase


class ResourceUsage_PerformanceDynamic_ArkTsExample_0010(PerfTestCase):

    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(self.TAG, controllers)
        self._app_package = 'com.ovcompose.test'
        self._app_name = 'ArkTsExample'
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

        # Step('启动被测应用')
        self.driver.start_app(self.app_package, page_name='EntryAbility')
        self.driver.wait(5)

        def step1():
            self.touch_by_text('ComposeView1500', 5)
            self.swipes_up(5, 2)
            self.swipes_down(5, 2)

        def step2():
            self.touch_by_text('ComposeLazyView1500Page', 5)
            self.swipes_up(5, 2)
            self.swipes_down(5, 2)

        self.execute_performance_step("ArkTsExample-1500View测试场景-step1 ComposeView1500", 30, step1,
                                      sample_all_processes=True)
        self.driver.swipe_to_back()
        self.execute_performance_step("ArkTsExample-1500View测试场景-step2 ComposeLazyView1500Page", 30, step2,
                                      sample_all_processes=True)
        self.driver.swipe_to_back()
