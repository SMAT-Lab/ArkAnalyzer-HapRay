import time
from typing import Optional

from hypium import BY

from hapray.core.perf_testcase import Log, PerfTestCase


class PerfLoad_taobao_0020(PerfTestCase):
    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(self.TAG, controllers)

        self._app_package = 'com.taobao.taobao4hmos'
        self._app_name = '淘宝'
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

        def step1():
            # 点击搜索框
            self.driver.touch(self.convert_coordinate(473, 300))
            time.sleep(2)

            # 搜索华为手机官方旗舰店
            search_coords = self.convert_coordinate(475, 198)
            self.driver.input_text(search_coords, '华为手机官方旗舰店')
            self.driver.touch(BY.text('搜索'))
            time.sleep(2)

            # Step('搜索结果页浏览，上滑5次')
            self.swipes_up(swip_num=5, sleep=2)
            # Step('搜索结果页浏览，下滑5次')
            self.swipes_down(swip_num=5, sleep=2)

        self.execute_performance_step('淘宝-搜索浏览场景-step1内容搜索，搜索结果滑动', 35, step1)
