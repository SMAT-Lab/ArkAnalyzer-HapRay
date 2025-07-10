# coding: utf-8
import time

from hypium import BY

from hapray.core.perf_testcase import PerfTestCase


class ResourceUsage_PerformanceDynamic_zhifubao_0030(PerfTestCase):

    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(self.TAG, controllers)

        self._app_package = 'com.alipay.mobile.client'
        self._app_name = '支付宝'
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
            # 点击出行
            self.driver.touch(BY.type('Text').text('出行'))
            time.sleep(5)

            # 点击地铁码
            self.touch_by_coordinates(400, 400, 5)

            # 点击打车
            self.touch_by_coordinates(360, 360, 5)

            # 点击骑行
            self.touch_by_coordinates(950, 360, 5)

        # 启动被测应用
        self.driver.start_app(self.app_package)
        self.driver.wait(5)

        # 点击出行
        self.driver.touch(BY.type('Text').text('出行'))
        time.sleep(2)

        # 点击公交地铁
        self.touch_by_coordinates(173, 360, 2)
        # 点击公交码
        self.touch_by_coordinates(200, 400, 2)

        self.swipe_to_back()
        time.sleep(1)

        self.execute_performance_step("支付宝-出行场景-step1出行页浏览", 30, step1)
