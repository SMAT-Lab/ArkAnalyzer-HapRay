# coding: utf-8

from hapray.core.perf_testcase import PerfTestCase


class ResourceUsage_PerformanceDynamic_jingdong_0010(PerfTestCase):

    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(self.TAG, controllers)

        self._app_package = 'com.jd.hm.mall'
        self._app_name = '京东'
        self._steps = [
            {
                "name": "step1",
                "description": "1.京东首页-滑动-应用内操作"
            }
        ]

        # 原始采集设备的屏幕尺寸（Mate 60 Pro）
        self.source_screen_width = 1260
        self.source_screen_height = 2720

    @property
    def steps(self) -> list:
        return self._steps

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
            # Step('京东首页上滑操作')
            self.swipes_up(swip_num=5, sleep=2)
            # Step('京东首页下滑操作')
            self.swipes_down(swip_num=5, sleep=2)

        self.execute_performance_step(1, step1, 30)
