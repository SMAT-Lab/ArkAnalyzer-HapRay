import time

from hapray.core.perf_testcase import PerfTestCase


class PerfLoad_Wechat_0170(PerfTestCase):
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
        self.start_app()
        time.sleep(2)

        # 右上角+
        self.touch_by_coordinates(998, 176, 2)
        self.touch_by_text('扫一扫', 3)
        self.swipe_to_back(2)

        # 右上角+
        self.touch_by_coordinates(998, 176, 2)

        def step1():
            self.touch_by_text('扫一扫', 3)

        self.execute_performance_step('微信-扫一扫场景-step1扫一扫调起小程序', 60, step1)
