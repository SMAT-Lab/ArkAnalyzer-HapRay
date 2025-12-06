import time

from hypium import BY

from hapray.core.perf_testcase import PerfTestCase


class PerfLoad_Wechat_0040(PerfTestCase):
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

        self.touch_by_text('测试账号', 1)

        # 点击加号
        self.touch_by_coordinates(1026, 2263, 1)

        def step1():
            # 点击视频通话，等待2s
            self.driver.touch(BY.text('视频通话'))
            self.driver.wait(0.5)
            self.driver.touch(BY.text('视频通话'))
            self.driver.wait(0.5)
            time.sleep(30)
            # 点击挂断，等待2s
            self.driver.touch(self.convert_coordinate(562, 2069))
            self.driver.wait(0.5)

        def step2():
            self.touch_by_text('瑞幸咖啡', 1)
            time.sleep(35)

        self.execute_performance_step('微信-视频通话场景-step1视频通话30s', 30, step1)

        self.swipe_to_back()
        self.swipes_down(1, 1)

        self.execute_performance_step('微信-视频通话场景-step2小程序滑动', 35, step2)
