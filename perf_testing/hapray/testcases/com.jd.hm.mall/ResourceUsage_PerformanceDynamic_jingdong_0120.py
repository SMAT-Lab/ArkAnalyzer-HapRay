# coding: utf-8
import time

from hapray.core.perf_testcase import PerfTestCase


class ResourceUsage_PerformanceDynamic_jingdong_0120(PerfTestCase):

    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(self.TAG, controllers)

        self._app_package = 'com.jd.hm.mall'
        self._app_name = '京东'
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

        # Step('启动京东应用')
        self.driver.start_app(self.app_package)
        self.driver.wait(5)

        def step1():
            # 点击9.9包邮第一个商品
            self.driver.touch(self.convert_coordinate(144, 1214))
            time.sleep(3)

            # Step('上滑操作')
            self.swipes_up(swip_num=3, sleep=2)
            # Step('下滑操作')
            self.swipes_down(swip_num=3, sleep=2)

        self.execute_performance_step("京东-9块9包邮场景-step1九块九包邮页面上下滑动", 30, step1)
