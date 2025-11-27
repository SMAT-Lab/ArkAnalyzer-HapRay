from hypium import BY

from hapray.core.perf_testcase import PerfTestCase


class PerfLoad_taobao_0070(PerfTestCase):
    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(self.TAG, controllers)

        self._app_package = 'com.taobao.taobao4hmos'
        self._app_name = '淘宝'
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
            self.driver.touch(BY.text('关注'))
            self.driver.wait(1)

            # Step('关注页，上滑5次')
            self.swipes_up(swip_num=5, sleep=3)
            # Step('关注页，下滑5次')
            self.swipes_down(swip_num=5, sleep=3)

        self.execute_performance_step('淘宝-关注-step1关注页面上下滑动', 40, step1)
