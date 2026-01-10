import time

from hypium import BY
from hypium.model.basic_data_type import UiParam

from hapray.core.perf_testcase import PerfTestCase


class MemLoad_Douyin_0060(PerfTestCase):
    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(self.TAG, controllers)

        self._app_package = 'com.ss.hm.ugc.aweme'
        self._app_name = '抖音'
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
        def step1():
            # 1. 打开抖音，等待 5s
            self.start_app()

        def step2():
            # 2.进入直播tab页面：点击直播tab页面（等待2s）
            for _i in range(3):
                if self.driver.find_component(BY.text('直播')):
                    break
                self.driver.swipe(UiParam.RIGHT, distance=60, start_point=(0.16, 0.08))
                time.sleep(1)
            self.driver.touch(BY.text('直播'), wait_time=2)

        def step3():
            # 3.进入直播间：点击屏幕显示进入直播间，点击进入直播间（等待2s）
            if not self.driver.find_component(BY.text('点击进入直播间')):
                self.driver.touch((0.5, 0.5), wait_time=2)
            self.driver.touch(BY.text('点击进入直播间'), wait_time=2)

        def step4():
            # 4.直播间切换：上滑5次（滑动间隔5s）
            self.swipes_up(5, 5)

        def step5():
            # 5.退出直播间：返回等待（2s）
            self.driver.swipe_to_back()
            time.sleep(2)
            self.driver.check_component_exist(BY.text('点击进入直播间'))

        def step6():
            # 6.浏览直播：上滑5次（滑动间隔5s）
            self.swipes_up(5, 5)

        self.execute_performance_step('抖音-直播浏览场景-step1打开抖音', 10, step1, sample_all_processes=True)
        self.execute_performance_step('抖音-直播浏览场景-step2进入直播tab页面：点击直播tab页面（等待2s）', 10, step2)
        self.execute_performance_step(
            '抖音-直播浏览场景-step3进入直播间：点击屏幕显示进入直播间，点击进入直播间（等待2s）', 10, step3
        )
        self.execute_performance_step('抖音-直播浏览场景-step4直播间切换：上滑5次（滑动间隔5s）', 10, step4)
        self.execute_performance_step('抖音-直播浏览场景-step5退出直播间：返回等待（2s）', 10, step5)
        self.execute_performance_step('抖音-直播浏览场景-step6浏览直播：上滑5次（滑动间隔5s）', 10, step6)
