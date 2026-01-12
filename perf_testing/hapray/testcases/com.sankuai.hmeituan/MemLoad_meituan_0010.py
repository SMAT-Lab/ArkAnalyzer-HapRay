import time

from hapray.core.perf_testcase import PerfTestCase


class MemLoad_meituan_0010(PerfTestCase):
    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(self.TAG, controllers)

        self._app_package = 'com.sankuai.hmeituan'
        self._app_name = '美团'
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

        def step1():
            # 1.打开美团，等待5s
            self.driver.start_app(self.app_package)
            self.driver.wait(5)
            time.sleep(2)

        def step2():
            # 2.首页页面上滑动5次，等待2s
            self.swipes_up(swip_num=5, sleep=2)

        def step3():
            # 3.首页页面下滑动5次，等待2s
            self.swipes_down(swip_num=5, sleep=2)

        self.execute_performance_step('美团-首页滑动浏览场景-step1打开美团，等待5s', 10, step1)
        self.execute_performance_step('美团-首页滑动浏览场景-step2首页页面上滑动5次，等待2s', 20, step2)
        self.execute_performance_step('美团-首页滑动浏览场景-step3首页页面下滑动5次，等待2s', 20, step3)
