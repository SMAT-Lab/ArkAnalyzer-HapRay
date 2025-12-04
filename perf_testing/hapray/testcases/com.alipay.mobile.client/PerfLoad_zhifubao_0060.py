import time

from devicetest.core.test_case import Step
from hypium import BY

from hapray.core.perf_testcase import PerfTestCase


class PerfLoad_zhifubao_0060(PerfTestCase):
    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(self.TAG, controllers)

        self._app_package = 'com.alipay.mobile.client'
        self._app_name = '支付宝'
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

        Step('启动被测应用')
        self.driver.start_app(self.app_package)
        self.driver.wait(5)

        def step1():
            # 点击理财
            self.driver.touch(BY.type('Text').text('理财'))
            time.sleep(5)

            # 点击保险
            self.touch_by_coordinates(900, 600, 5)
            # 保险页上滑3次
            self.swipes_up(3, 2)

        # 点击“理财”
        self.driver.touch(BY.type('Text').text('理财'))
        time.sleep(2)

        # 点击“首页”
        self.driver.touch(BY.type('Text').text('首页'))
        time.sleep(2)

        self.execute_performance_step('支付宝-理财基金浏览场景-step1基金页面浏览', 20, step1)
