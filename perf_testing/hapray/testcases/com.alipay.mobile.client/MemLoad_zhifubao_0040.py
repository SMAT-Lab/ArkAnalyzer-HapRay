import time

from hypium import BY

from hapray.core.perf_testcase import PerfTestCase


class MemLoad_zhifubao_0040(PerfTestCase):
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
        def step1():
            # 1. 启动支付宝(启动5s，停留2s)
            self.start_app(wait_time=5)
            time.sleep(2)

        def step2():
            # 2. 进入我的页面：点击我的（等待2s）
            self.driver.touch(BY.text('我的'))
            time.sleep(2)

        def step3():
            # 3. 我的页面浏览：上下滑动1次（等待2s）
            self.swipes_up(swip_num=1, sleep=2, timeout=300)
            self.swipes_down(swip_num=1, sleep=2, timeout=300)

        self.execute_performance_step('支付宝-收付款场景-step1应用冷启动', 10, step1, sample_all_processes=True)
        self.execute_performance_step('支付宝-收付款场景-step2进入我的页面：点击我的', 10, step2)
        self.execute_performance_step('支付宝-收付款场景-step3我的页面浏览：上下滑动1次', 10, step3)
