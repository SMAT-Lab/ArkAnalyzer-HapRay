# coding: utf-8
import time

from hypium import BY

from hapray.core.perf_testcase import PerfTestCase


class ResourceUsage_PerformanceDynamic_zhifubao_0010(PerfTestCase):

    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(self.TAG, controllers)

        self._app_package = 'com.alipay.mobile.client'
        self._app_name = '支付宝'
        # 原始采集设备的屏幕尺寸（Mate 60 Pro）
        self.source_screen_width = 1260
        self.source_screen_height = 2720

    @property
    def app_package(self) -> str:
        return self._app_package

    @property
    def app_name(self) -> str:
        return self._app_name

    def process(self):
        self.driver.swipe_to_home()

        # 启动被测应用
        self.driver.start_app(self.app_package)
        self.driver.wait(5)

        def step1():
            # 1. 支付宝-首页上下滑5次，间隔2s
            self.swipes_up(swip_num=5, sleep=2, timeout=300)
            self.swipes_down(swip_num=5, sleep=2, timeout=300)

        def without_perf_after_step1():
            # 点击“我的”
            self.driver.touch(BY.type('Text').text('我的'))
            time.sleep(2)
            # 点击“首页”
            self.driver.touch(BY.type('Text').text('首页'))
            time.sleep(2)

        def step2():
            self.driver.touch(BY.type('Text').text('我的'))
            time.sleep(5)

            self.driver.touch(BY.type('Text').text('理财'))
            time.sleep(5)

            self.driver.touch(BY.type('Text').text('消息'))
            time.sleep(5)

            self.driver.touch(BY.type('Text').text('首页'))
            time.sleep(5)

        self.execute_performance_step("支付宝-首页及Tab页浏览-step1首页浏览", 30, step1)
        time.sleep(10)
        without_perf_after_step1()
        self.execute_performance_step("支付宝-首页及Tab页浏览-step2TAB页切换", 30, step2)
