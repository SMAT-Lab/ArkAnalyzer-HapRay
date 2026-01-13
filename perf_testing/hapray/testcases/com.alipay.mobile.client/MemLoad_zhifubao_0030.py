import time

from hypium import BY

from hapray.core.perf_testcase import PerfTestCase


class MemLoad_zhifubao_0030(PerfTestCase):
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
            # 2. 进入收付款页面：点击收付款（等待2s）
            self.driver.touch(BY.text('收付款'))
            time.sleep(2)

        def step3():
            # 3. 进入转账页面：点击‘转账’按钮（等待2s）
            self.touch_by_coordinates(212, 2198, 2)

        def step4():
            self.driver.touch(BY.text('转到银行卡'))
            time.sleep(2)

        def step5():
            self.driver.swipe_to_back()
            time.sleep(2)

        def step6():
            self.driver.touch(BY.text('转到支付宝'))
            time.sleep(2)

        self.execute_performance_step('支付宝-收付款场景-step1应用冷启动', 5, step1, sample_all_processes=True)
        self.execute_performance_step('支付宝-收付款场景-step2进入收付款页面：点击收付款', 5, step2)
        self.execute_performance_step('支付宝-收付款场景-step3进入转账页面：点击“转账”按钮', 5, step3)
        self.execute_performance_step('支付宝-收付款场景-step4进行银行卡转账：点击“转到银行卡”', 5, step4)
        self.execute_performance_step('支付宝-收付款场景-step5返回上一级：滑动返回', 5, step5)
        self.execute_performance_step('支付宝-收付款场景-step6进行支付账户转账：点击“转到支付宝”', 5, step6)
