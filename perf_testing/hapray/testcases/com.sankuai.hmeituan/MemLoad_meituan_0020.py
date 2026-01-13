import time

from hypium import BY

from hapray.core.perf_testcase import PerfTestCase


class MemLoad_meituan_0020(PerfTestCase):
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
            # 2.点击美食页面，等待2s
            self.driver.touch(BY.text('美食'), wait_time=2)

        def step3():
            # 3.美食页面上滑动5次，等待2s
            self.swipes_up(swip_num=5, sleep=2)

        def step4():
            # 4.美食页面下滑动5次，等待2s
            self.swipes_down(swip_num=5, sleep=2)

        def step5():
            # 5.返回首页，点击酒店民宿等待2s
            self.driver.swipe_to_back()
            time.sleep(2)
            self.driver.touch(BY.text('酒店民宿'), wait_time=2)

        def step6():
            # 6.酒店民宿页面上滑动5次，等待2s
            self.swipes_up(swip_num=5, sleep=2)

        def step7():
            # 7.酒店民宿页面下滑动5次，等待2s
            self.swipes_down(swip_num=5, sleep=2)

        self.execute_performance_step('美团-美食、酒店民宿滑动浏览场景-step1打开美团，等待5s', 10, step1)
        self.execute_performance_step('美团-美食、酒店民宿滑动浏览场景-step2点击美食页面，等待2s', 10, step2)
        self.execute_performance_step('美团-美食、酒店民宿滑动浏览场景-step3美食页面上滑动5次，等待2s', 20, step3)
        self.execute_performance_step('美团-美食、酒店民宿滑动浏览场景-step4美食页面下滑动5次，等待2s', 20, step4)
        self.execute_performance_step('美团-美食、酒店民宿滑动浏览场景-step5返回首页，点击酒店民宿等待2s', 10, step5)
        self.execute_performance_step('美团-美食、酒店民宿滑动浏览场景-step6酒店民宿页面上滑动5次，等待2s', 20, step6)
        self.execute_performance_step('美团-美食、酒店民宿滑动浏览场景-step7酒店民宿页面下滑动5次，等待2s', 20, step7)
