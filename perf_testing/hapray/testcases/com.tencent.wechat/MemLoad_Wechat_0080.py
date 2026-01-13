import time

from hypium import BY
from hypium.model.basic_data_type import MatchPattern

from hapray.core.perf_testcase import PerfTestCase


class MemLoad_Wechat_0080(PerfTestCase):
    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(self.TAG, controllers)

        self._app_package = 'com.tencent.wechat'
        self._app_name = '微信'
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
            # 1.打开微信（等待5s）
            self.start_app()
            time.sleep(5)

        def step2():
            # 2.进入扫一扫页面：点击右上角“+”（等待1s），点击扫一扫（等待5s）
            self.driver.touch(BY.key('right'), wait_time=1)
            self.touch_by_text('扫一扫', 5)

        def step3():
            # 3.进入具体相册：点击相册（等待2s），点击图片（等待2s），点击“微信收款码”
            self.driver.touch(BY.key('gallery_btn'), wait_time=2)
            self.touch_by_text('图片', 2)
            self.touch_by_text('微信收款码', 2)

        def step4():
            # 4.二维码识别：选择二维码（等待2s）
            self.driver.touch(BY.key('Selector', MatchPattern.CONTAINS), wait_time=2)
            self.driver.check_component_exist(BY.text('付款金额'))

        self.execute_performance_step('微信-扫一扫场景-step1打开微信', 10, step1)
        self.execute_performance_step(
            '微信-扫一扫场景-step2进入扫一扫页面：点击右上角“+”（等待1s），点击扫一扫（等待5s）', 10, step2
        )
        self.execute_performance_step(
            '微信-扫一扫场景-step3进入具体相册：点击相册（等待2s），点击图片（等待2s），点击“微信收款码”', 10, step3
        )
        self.execute_performance_step('微信-扫一扫场景-step4二维码识别：选择二维码（等待2s））', 10, step4)
