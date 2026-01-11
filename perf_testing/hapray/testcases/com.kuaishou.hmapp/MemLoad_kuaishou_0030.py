import time

from hypium import BY

from hapray.core.perf_testcase import PerfTestCase


class MemLoad_kuaishou_0030(PerfTestCase):
    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(self.TAG, controllers)

        self._app_package = 'com.kuaishou.hmapp'
        self._app_name = '快手'
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
            # 1.启动快手（等待5s）
            self.driver.start_app(self.app_package)
            self.driver.wait(5)
            time.sleep(5)

        def step2():
            # 2.进入博主主页：点击我（等待2s），点击关注（等待2s），点击胡锡进博主（等待2s）
            self.driver.touch(BY.text('我'), wait_time=2)
            self.driver.touch(BY.text('关注'), wait_time=2)
            self.driver.touch(BY.text('胡锡进'), wait_time=2)

        def step3():
            # 3.主页浏览：上滑2次，下滑3次（滑动间隔2s）
            self.swipes_up(swip_num=2, sleep=2)
            self.swipes_down(swip_num=3, sleep=2)

        self.execute_performance_step('快手-博主主页浏览-step1启动快手（等待5s）', 10, step1, sample_all_processes=True)
        self.execute_performance_step(
            '快手-博主主页浏览-step2进入博主主页：点击我（等待2s），点击关注（等待2s），点击胡锡进博主（等待2s）',
            30,
            step2,
        )
        self.execute_performance_step('快手-博主主页浏览-step3主页浏览：上滑2次，下滑3次（滑动间隔2s）', 30, step3)
