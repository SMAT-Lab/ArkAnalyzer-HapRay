# coding: utf-8
import time

from devicetest.core.test_case import Step
from hypium import BY

from hapray.core.common.coordinate_adapter import CoordinateAdapter
from hapray.core.perf_testcase import PerfTestCase


class ResourceUsage_PerformanceDynamic_zhifubao_0100(PerfTestCase):

    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(self.TAG, controllers)

        self._app_package = 'com.alipay.mobile.client'
        self._app_name = '支付宝'
        self._steps = [
            {
                "name": "step1",
                "description": "1. 支付宝-饿了么 页面浏览 上滑5次，间隔2s"
            },
            {
                "name": "step2",
                "description": "2. 支付宝-饿了么 店铺浏览 上滑10次，间隔2s"
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
        Step('启动被测应用')
        self.driver.start_app(self.app_package)
        self.driver.wait(5)
        # 点击 饿了么
        component = self.driver.find_component(BY.type('Text').text('饿了么'))
        self.driver.touch(component)
        time.sleep(5)
        self.driver.touch(BY.text('超市便利'))
        time.sleep(5)
        self.driver.touch(CoordinateAdapter.convert_coordinate(
            self.driver,
            x=631,  # 原始x坐标
            y=185,  # 原始y坐标
            source_width=self.source_screen_width,
            source_height=self.source_screen_height
        ))
        self.driver.touch(BY.text('西安半导体产业园 0102'))
        time.sleep(2)

        def step1():
            Step('1. 支付宝-饿了么 页面浏览 上滑5次，间隔2s')
            for i in range(5):
                self.swipes_up(1, 2, 300)

        def step2():
            Step('2. 支付宝-饿了么 店铺浏览 上滑10次，间隔2s')
            for i in range(10):
                self.swipes_up(1, 2, 300)

        self.execute_performance_step(1, step1, 20)
        time.sleep(10)
        self.driver.swipe_to_back()
        time.sleep(2)
        self.driver.touch(BY.text('我的'))  # 点不到
        time.sleep(2)
        self.driver.touch(BY.text('店铺关注'))
        time.sleep(2)
        self.driver.touch(BY.text('每一天便利店(西滩社区店)'))
        time.sleep(2)
        self.execute_performance_step(2, step2, 35)
