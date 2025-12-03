import time

from hypium import BY

from hapray.core.perf_testcase import PerfTestCase


class PerfLoad_meituan_0020(PerfTestCase):
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

        # Step('启动被测应用')
        self.driver.start_app(self.app_package)
        self.driver.wait(5)
        time.sleep(2)

        self.driver.touch(BY.text('美食'))
        self.driver.wait(2)
        time.sleep(2)

        def step1():
            # Step('美团美食页上滑操作')
            self.swipes_up(swip_num=5, sleep=2)
            # Step('美团美食页下滑操作')
            self.swipes_down(swip_num=5, sleep=2)

        self.execute_performance_step('美团-美食、酒店民宿页面滑动浏览场景-step1美食页上下滑动', 30, step1)

        self.driver.swipe_to_back()
        time.sleep(2)
        self.driver.touch(BY.text('酒店民宿'))
        self.driver.wait(2)
        time.sleep(2)

        def step2():
            # Step('美团酒店民宿页上滑操作')
            self.swipes_up(swip_num=5, sleep=2)
            # Step('美团酒店民宿页下滑操作')
            self.swipes_down(swip_num=5, sleep=2)

        self.execute_performance_step('美团-美食、酒店民宿页面滑动浏览场景-step2酒店民宿页上下滑动', 30, step2)
