# coding: utf-8
import time

from hapray.core.perf_testcase import PerfTestCase


class ResourceUsage_PerformanceDynamic_jingdong_0110(PerfTestCase):

    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(self.TAG, controllers)

        self._app_package = 'com.jd.hm.mall'
        self._app_name = '京东'
        self._steps = [
            {
                "name": "step1",
                "description": "1.京东-首页静置场景"
            }
        ]

        # 原始采集设备的屏幕尺寸（Mate 60）
        self.source_screen_width = 1216
        self.source_screen_height = 2688

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

        # Step('启动京东应用')
        self.driver.start_app(self.app_package)
        self.driver.wait(5)

        def step1():
            # 点击直播
            time.sleep(30)

        self.execute_performance_step(1, step1, 30)
