import time

from hypium import BY

from hapray.core.perf_testcase import PerfTestCase


class PerfLoad_Douyin_0110(PerfTestCase):
    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(self.TAG, controllers)

        self._app_package = 'com.ss.hm.ugc.aweme'
        self._app_name = '抖音'
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
        # 打开抖音，等待 5s
        self.start_app()
        time.sleep(5)

        # 点击+号
        self.touch_by_coordinates(543, 2275, 2)

        self.touch_by_text('开直播', 2)
        self.touch_by_text('开始视频直播', 2)

        def step1():
            time.sleep(30)

        self.execute_performance_step('抖音-直播场景-step1进入直播间，开始直播', 35, step1)

        # 右上角关闭直播
        self.touch_by_coordinates(995, 180, 2)

        # 点击确定
        self.touch_by_text('确定', 2)
        # self.touch_by_coordinates(700, 1372, 2)