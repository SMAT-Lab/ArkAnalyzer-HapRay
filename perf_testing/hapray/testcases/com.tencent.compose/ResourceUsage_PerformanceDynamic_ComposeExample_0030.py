# coding: utf-8

from hypium import BY

from hapray.core.perf_testcase import PerfTestCase


class ResourceUsage_PerformanceDynamic_ComposeExample_0030(PerfTestCase):

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

        def step():
            self.touch_by_text('生成 layers', 1)

        self.swipes_up(1, 2)
        self.touch_by_text('组件嵌套 Demo', 2)
        self.driver.touch(BY.type('TextInput'))
        self.touch_by_coordinates(320, 1695, 1)  # 1
        self.touch_by_coordinates(540, 2190, 1)  # 0
        self.execute_performance_step("ComposeSample-组件嵌套测试场景-step1 10layers", 5, step,
                                      sample_all_processes=True)
        self.driver.swipe_to_back()

        self.touch_by_text('组件嵌套 Demo', 2)
        self.driver.touch(BY.type('TextInput'))
        self.touch_by_coordinates(540, 1862, 1)  # 5
        self.touch_by_coordinates(540, 2190, 1)  # 0
        self.execute_performance_step("ComposeSample-组件嵌套测试场景-step2 50layers", 5, step,
                                      sample_all_processes=True)
        self.driver.swipe_to_back()

        self.touch_by_text('组件嵌套 Demo', 2)
        self.driver.touch(BY.type('TextInput'))
        self.touch_by_coordinates(320, 1695, 1)  # 1
        self.touch_by_coordinates(540, 2190, 1)  # 0
        self.touch_by_coordinates(540, 2190, 1)  # 0
        self.execute_performance_step("ComposeSample-组件嵌套测试场景-step3 100layers", 5, step,
                                      sample_all_processes=True)
        self.driver.swipe_to_back()

        self.touch_by_text('组件嵌套 Demo', 2)
        self.driver.touch(BY.type('TextInput'))
        self.touch_by_coordinates(540, 1862, 1)  # 5
        self.touch_by_coordinates(540, 2190, 1)  # 0
        self.touch_by_coordinates(540, 2190, 1)  # 0
        self.execute_performance_step("ComposeSample-组件嵌套测试场景-step4 500layers", 5, step,
                                      sample_all_processes=True)
        self.driver.swipe_to_back()
