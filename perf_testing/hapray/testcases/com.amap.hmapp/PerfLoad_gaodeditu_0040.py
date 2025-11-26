import time
from typing import Optional

from hypium import BY

from hapray.core.perf_testcase import Log, PerfTestCase


class PerfLoad_gaodeditu_0040(PerfTestCase):
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

        def step1():

            self.driver.touch(BY.text('附近'))
            time.sleep(2)
            # 点击附近
            self.driver.touch(self.convert_coordinate(140, 197))
            time.sleep(2)

            # 搜索大雁塔北广场
            search_coords = self.convert_coordinate(475, 198)
            self.driver.input_text(search_coords, '西安市')
            time.sleep(2)

            self.driver.touch(BY.text('西安市'))
            time.sleep(2)

            self.driver.touch(BY.text('美食'))
            time.sleep(2)

            # Step('上滑操作')
            self.swipes_up(swip_num=5, sleep=2)
            # Step('下滑操作')
            self.swipes_down(swip_num=5, sleep=2)


        self.execute_performance_step('高德地图-附近美食、酒店页上下滑-step1美食页滑动浏览', 50, step1)

        self.dirver.swipe_to_back()

        def step2():
            self.driver.touch(BY.text('酒店'))
            time.sleep(2)
            # Step('上滑操作')
            self.swipes_up(swip_num=5, sleep=2)
            # Step('下滑操作')
            self.swipes_down(swip_num=5, sleep=2)

        self.execute_performance_step('高德地图-附近美食、酒店页上下滑-step2酒店页滑动浏览', 35, step2)

