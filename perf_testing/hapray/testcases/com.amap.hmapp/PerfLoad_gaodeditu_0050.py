import time
from typing import Optional

from hypium import BY

from hapray.core.perf_testcase import Log, PerfTestCase


class PerfLoad_gaodeditu_0050(PerfTestCase):
    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(self.TAG, controllers)

        self._app_package = 'com.amap.hmapp'
        self._app_name = '高德地图'
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

        # Step('启动被测应用')
        self.driver.start_app(self.app_package)
        self.driver.wait(5)
        time.sleep(2)

        # 点击搜索框
        self.driver.touch(self.convert_coordinate(500, 1450))
        time.sleep(2)

        # 搜索大雁塔北广场
        search_coords = self.convert_coordinate(475, 198)
        self.driver.input_text(search_coords, '大雁塔北广场')
        time.sleep(2)

        # 点击大雁塔北广场路线
        self.driver.touch(self.convert_coordinate(973, 400))
        time.sleep(2)

        self.driver.touch(BY.text('驾车'))
        time.sleep(2)

        self.driver.touch(BY.text('更多'))
        time.sleep(2)

        def step1():


            self.driver.touch(BY.text('模拟导航'))
            time.sleep(10)


        self.execute_performance_step('高德地图-大雁塔北广场导航场景-step1模拟导航', 35, step1)


