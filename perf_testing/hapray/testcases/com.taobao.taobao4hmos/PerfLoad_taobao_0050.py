import time
from typing import Optional

from hypium import BY

from hapray.core.perf_testcase import Log, PerfTestCase


class PerfLoad_taobao_0050(PerfTestCase):
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
            self.driver.touch(BY.text('淘宝直播'))
            self.driver.wait(1)
            # Step('直播页，上滑5次')
            self.swipes_up(swip_num=5, sleep=2)
            # Step('直播页，下滑5次')
            self.swipes_down(swip_num=5, sleep=2)


        def step2():
            # 点击第一个直播间
            self.driver.touch(self.convert_coordinate(280, 1328))
            time.sleep(2)
            # Step('直播间切换，上滑5次')
            self.swipes_up(swip_num=5, sleep=2)
            # Step('直播间切换，下滑5次')
            self.swipes_down(swip_num=5, sleep=2)


        self.execute_performance_step('淘宝-首页-step1直播页滑动', 40, step1)
        self.execute_performance_step('淘宝-首页-step2直播间上下滑动', 30, step2)
