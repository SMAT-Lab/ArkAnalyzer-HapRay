# coding: utf-8
import time

from devicetest.core.test_case import Step
from hypium import BY

from hapray.core.common.coordinate_adapter import CoordinateAdapter
from hapray.core.perf_testcase import PerfTestCase


class ResourceUsage_PerformanceDynamic_zhifubao_0010(PerfTestCase):

    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(self.TAG, controllers)

        self._app_package = 'com.alipay.mobile.client'
        self._app_name = '支付宝'
        self._steps = [
            {
                "name": "step1",
                "description": "1. 支付宝-首页上下滑5次，间隔2s"
            },
            {
                "name": "step2",
                "description": "2. 支付宝-切换回到支付宝主界面"
            },
            {
                "name": "step3",
                "description": "3. 支付宝-点击收付款"
            },
            {
                "name": "step4",
                "description": "4. 支付宝-点击收转账"
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

        def step1():
            Step('1. 支付宝-首页上下滑5次，间隔2s')
            for i in range(5):
                self.swipes_up(swip_num=1, sleep=2, timeout=300)
            for i in range(5):
                self.swipes_down(swip_num=1, sleep=2, timeout=300)
            time.sleep(3)

        def without_perf_after_step1():
            # 点击“我的”
            # driver.touch((1180, 2631))
            self.driver.touch(BY.type('Text').text('我的'))
            time.sleep(2)

        def step2():
            Step('2. 支付宝-切换回到支付宝主界面')
            component = self.driver.find_component(BY.type('Text').text('首页'))
            self.driver.touch(component)
            time.sleep(5)

        def step3():
            Step('3. 支付宝-点击收付款')
            component = self.driver.find_component(BY.type('Text').text('收付款'))
            self.driver.touch(component)
            time.sleep(5)

        def step4():
            Step('4. 支付宝-点击收转账')
            # component = driver.find_component(BY.type('Text').text('转账'))
            # driver.touch(component)
            self.driver.touch(CoordinateAdapter.convert_coordinate(
                self.driver,
                x=662,  # 原始x坐标
                y=2350,  # 原始y坐标
                source_width=self.source_screen_width,
                source_height=self.source_screen_height
            ))
            time.sleep(5)

        def finish():
            # 点击右上角关闭
            self.driver.touch(CoordinateAdapter.convert_coordinate(
                self.driver,
                x=1175,  # 原始x坐标
                y=197,  # 原始y坐标
                source_width=self.source_screen_width,
                source_height=self.source_screen_height
            ))
            time.sleep(2)
            # 侧滑返回
            self.driver.swipe_to_back()
            time.sleep(2)
            # 上滑返回桌面
            self.driver.swipe_to_home()

        self.execute_performance_step(1, step1, 30)
        time.sleep(10)
        without_perf_after_step1()
        self.execute_performance_step(2, step2, 10)
        self.execute_performance_step(3, step3, 10)
        self.execute_performance_step(4, step4, 10)
        finish()
