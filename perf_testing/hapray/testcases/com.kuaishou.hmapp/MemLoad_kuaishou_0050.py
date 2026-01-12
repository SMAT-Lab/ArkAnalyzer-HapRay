import time

from hypium import BY

from hapray.core.perf_testcase import PerfTestCase


class MemLoad_kuaishou_0050(PerfTestCase):
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
            # 2.进入直播tab页面：点击首页（等待2s），点击直播tab页面（等待2s）
            self.driver.touch(BY.text('首页'), wait_time=2)
            self.driver.touch(BY.text('直播'), wait_time=2)

        def step3():
            # 3.进入直播间：点击进入第一个直播间（等待2s）
            self.driver.touch(BY.type('FlowItem'), wait_time=2)

        def step4():
            # 4.直播间切换：上滑5次（滑动间隔5s）
            self.swipes_up(swip_num=5, sleep=5)

        def step5():
            # 5.退出直播间：返回等待（2s）
            self.driver.swipe_to_back()
            time.sleep(2)
            self.driver.check_component_exist(BY.text('直播'))

        def step6():
            # 6.浏览直播：上滑5次（滑动间隔5s）
            self.swipes_up(swip_num=5, sleep=5)

        self.execute_performance_step('快手-直播间浏览-step1启动快手（等待5s）', 10, step1, sample_all_processes=True)
        self.execute_performance_step(
            '快手-直播间浏览-step2进入直播tab页面：点击首页（等待2s），点击直播tab页面（等待2s）', 10, step2
        )
        self.execute_performance_step('快手-直播间浏览-step3进入直播间：点击进入第一个直播间（等待2s）', 10, step3)
        self.execute_performance_step('快手-直播间浏览-step4直播间切换：上滑5次（滑动间隔5s）', 10, step4)
        self.execute_performance_step('快手-直播间浏览-step5退出直播间：返回等待（2s）', 10, step5)
        self.execute_performance_step('快手-直播间浏览-step6浏览直播：上滑5次（滑动间隔5s）', 10, step6)
