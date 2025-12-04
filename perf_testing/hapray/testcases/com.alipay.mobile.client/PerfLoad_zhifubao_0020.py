import time

from hypium import BY

from hapray.core.perf_testcase import PerfTestCase


class PerfLoad_zhifubao_0020(PerfTestCase):
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

        # 启动被测应用
        self.driver.start_app(self.app_package)
        self.driver.wait(5)

        def step1():
            # 点击收付款
            self.driver.touch(BY.type('Text').text('收付款'))
            time.sleep(5)

            # 点击收钱
            self.touch_by_coordinates(210, 1752, 5)

        def without_perf_after_step1():
            time.sleep(10)
            self.swipe_to_back(1)
            self.swipe_to_back(1)

            # 点击扫一扫
            self.driver.touch(BY.type('Text').text('扫一扫'))
            time.sleep(5)

            # 点击相册
            self.driver.touch(BY.type('Text').text('相册'))
            time.sleep(5)
            self.swipe_to_back(1)
            self.swipe_to_back(1)

        def step2():
            # 点击扫一扫
            self.driver.touch(BY.type('Text').text('扫一扫'))
            time.sleep(5)
            # 点击相册
            self.driver.touch(BY.type('Text').text('相册'))
            time.sleep(5)
            # 选择第一张为支付宝收款码的图片
            self.touch_by_coordinates(483, 446, 5)
            # 点击完成
            self.driver.touch(BY.type('Text').text('完成'))
            time.sleep(5)

        def finish():
            # 上滑返回桌面
            self.driver.swipe_to_home()
            time.sleep(2)

        self.execute_performance_step('支付宝-扫一扫场景-step1首付款码展示', 15, step1)
        without_perf_after_step1()
        self.execute_performance_step('支付宝-扫一扫场景-step2扫一扫识别收款码', 25, step2)
        finish()
