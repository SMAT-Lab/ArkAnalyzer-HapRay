# coding: utf-8
import time

from hypium import BY

from hapray.core.common.coordinate_adapter import CoordinateAdapter
from hapray.core.perf_testcase import PerfTestCase


class ResourceUsage_PerformanceDynamic_jingdong_0080(PerfTestCase):

    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(self.TAG, controllers)

        self._app_package = 'com.jd.hm.mall'
        self._app_name = '京东'
        self._steps = [
            {
                "name": "step1",
                "description": "1.京东-搜索商品购物"
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
        time.sleep(3)

        def step1():
            # 点击搜索框
            self.driver.touch(CoordinateAdapter.convert_coordinate(
                self.driver,
                x=608,  # 原始x坐标
                y=315,  # 原始y坐标
                source_width=self.source_screen_width,
                source_height=self.source_screen_height
            ))
            time.sleep(2)

            # 搜索华为手机
            search_coords = CoordinateAdapter.convert_coordinate(
                self.driver,
                x=475,  # 原始x坐标
                y=198,  # 原始y坐标
                source_width=self.source_screen_width,
                source_height=self.source_screen_height
            )
            self.driver.input_text(search_coords, '华为手机')
            self.driver.touch(BY.text('搜索'))
            time.sleep(2)

            # Step('搜索结果页浏览，上滑操作')
            self.swipes_up(swip_num=3, sleep=2)
            # Step('搜索结果页浏览，下滑操作')
            self.swipes_down(swip_num=5, sleep=2)

        self.execute_performance_step(1, step1, 30)
