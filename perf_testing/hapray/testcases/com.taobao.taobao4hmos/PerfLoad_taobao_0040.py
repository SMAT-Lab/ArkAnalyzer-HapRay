import time
from typing import Optional

from hypium import BY

from hapray.core.perf_testcase import Log, PerfTestCase


class PerfLoad_taobao_0040(PerfTestCase):
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
            self.driver.touch(BY.text('购物车'))
            self.driver.wait(1)
            # Step('购物车，上滑5次')
            self.swipes_up(swip_num=5, sleep=2)
            # Step('购物车，下滑5次')
            self.swipes_down(swip_num=5, sleep=2)


        def step2():
            self.driver.touch(BY.text('视频'))
            self.driver.wait(1)
            self.driver.touch(BY.text('逛逛'))
            self.driver.wait(1)
            # Step('逛逛，上滑5次')
            self.swipes_up(swip_num=5, sleep=2)
            # Step('逛逛，下滑5次')
            self.swipes_down(swip_num=5, sleep=2)

        def step3():
            self.driver.touch(BY.text('我的淘宝'))
            self.driver.wait(1)
            # Step('逛逛，上滑5次')
            self.swipes_up(swip_num=5, sleep=2)
            # Step('逛逛，下滑5次')
            self.swipes_down(swip_num=5, sleep=2)

        self.execute_performance_step('淘宝-页签切换浏览场景-step1购物车滑动', 30, step1)
        self.execute_performance_step('淘宝-页签切换浏览场景-step2逛逛页面滑动', 30, step2)
        self.execute_performance_step('淘宝-页签切换浏览场景-step2我的淘宝页面滑动', 35, step3)
