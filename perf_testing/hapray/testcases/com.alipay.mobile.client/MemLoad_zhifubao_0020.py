import time

from hypium import BY

from hapray.core.perf_testcase import PerfTestCase


class MemLoad_zhifubao_0020(PerfTestCase):
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
            # 2. 进入扫一扫页面：点击扫一扫（等待2s）
            self.driver.touch(BY.text('扫一扫'))
            time.sleep(2)

        def step3():
            # 3. 等待扫码结束：等待2s
            time.sleep(2)
            if self.driver.wait_for_component(BY.text('安全提示')):
                self.driver.touch(BY.text('知道了'))
            else:
                self.driver.check_component_exist(BY.type('TextInput'))

        self.execute_performance_step('支付宝-扫码场景-step1应用冷启动', 10, step1, sample_all_processes=True)
        self.execute_performance_step('支付宝-扫码场景-step2扫一扫', 10, step2)
        self.execute_performance_step('支付宝-扫码场景-step3等待扫一扫结束', 10, step3)
