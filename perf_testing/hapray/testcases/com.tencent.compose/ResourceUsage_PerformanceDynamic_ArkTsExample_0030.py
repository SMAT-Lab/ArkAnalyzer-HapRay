from hypium import BY

from hapray.core.perf_testcase import PerfTestCase


class ResourceUsage_PerformanceDynamic_ArkTsExample_0030(PerfTestCase):
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

        self.driver.start_app(self.app_package, page_name='EntryAbility')
        self.driver.wait(5)

        def step():
            self.touch_by_text('生成layers', 1)
            self.driver.wait(8)

        self.touch_by_text('NestedLayerPage', 2)
        self.driver.input_text(BY.type('TextInput'), '10')
        self.execute_performance_step(
            'ArkTsExample-组件嵌套测试场景-step1 10layers', 10, step, sample_all_processes=True
        )
        self.driver.swipe_to_back()

        self.touch_by_text('NestedLayerPage', 2)
        self.driver.input_text(BY.type('TextInput'), '50')
        self.execute_performance_step(
            'ArkTsExample-组件嵌套测试场景-step2 50layers', 10, step, sample_all_processes=True
        )
        self.driver.swipe_to_back()

        self.touch_by_text('NestedLayerPage', 2)
        self.driver.input_text(BY.type('TextInput'), '100')
        self.execute_performance_step(
            'ArkTsExample-组件嵌套测试场景-step3 100layers', 10, step, sample_all_processes=True
        )
        self.driver.swipe_to_back()

        self.touch_by_text('NestedLayerPage', 2)
        self.driver.input_text(BY.type('TextInput'), '500')
        self.execute_performance_step(
            'ArkTsExample-组件嵌套测试场景-step4 500layers', 10, step, sample_all_processes=True
        )
        self.driver.swipe_to_back()
