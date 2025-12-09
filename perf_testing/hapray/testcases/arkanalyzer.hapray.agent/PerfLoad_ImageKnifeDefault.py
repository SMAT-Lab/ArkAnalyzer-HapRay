from hapray.core.perf_testcase import PerfTestCase


class PerfLoad_ImageKnifeDefault(PerfTestCase):
    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(self.TAG, controllers)
        self._app_package = 'arkanalyzer.hapray.agent'
        self._app_name = 'HapRay'
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
        self.driver.start_app(self.app_package)
        self.driver.wait(5)

        def step1():
            self.driver.start_app(
                self.app_package, 'ExecutorAbility', '--ps testSuite test_suite --ps testCase ImageKnifeDefaultPageTest'
            )
            self.swipes_up(swip_num=1, sleep=2, timeout=300)
            self.swipes_down(swip_num=1, sleep=2, timeout=300)

        self.execute_performance_step('ImageKnife-DownSampling-Default', 30, step1)
