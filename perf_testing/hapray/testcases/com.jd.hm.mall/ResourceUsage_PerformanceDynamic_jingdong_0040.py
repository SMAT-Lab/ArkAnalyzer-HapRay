# coding: utf-8
import time

from hypium import BY

from hapray.core.common.coordinate_adapter import CoordinateAdapter
from hapray.core.perf_testcase import PerfTestCase


class ResourceUsage_PerformanceDynamic_jingdong_0040(PerfTestCase):

    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(self.TAG, controllers)

        self._app_package = 'com.jd.hm.mall'
        self._app_name = '京东'
        self._steps = [
            {
                "name": "step1",
                "description": "1.京东购物车结算场景"
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
            # 点击购物车
            self.driver.touch(BY.text('购物车'))
            self.driver.wait(0.5)
            # 选中购物车提前预置的商品
            self.driver.touch(CoordinateAdapter.convert_coordinate(
                self.driver,
                x=81,  # 原始x坐标
                y=462,  # 原始y坐标
                source_width=self.source_screen_width,
                source_height=self.source_screen_height
            ))
            time.sleep(2)
            # 点击去结算
            self.driver.touch(CoordinateAdapter.convert_coordinate(
                self.driver,
                x=994,  # 原始x坐标
                y=2361,  # 原始y坐标
                source_width=self.source_screen_width,
                source_height=self.source_screen_height
            ))
            time.sleep(2)

        self.execute_performance_step(1, step1, 15)

        # 返回购物车
        self.driver.swipe_to_back()
        self.driver.wait(2)
        # 取消选中购物车提前预置的商品
        self.driver.touch(CoordinateAdapter.convert_coordinate(
            self.driver,
            x=81,  # 原始x坐标
            y=462,  # 原始y坐标
            source_width=self.source_screen_width,
            source_height=self.source_screen_height
        ))
        self.driver.wait(2)
