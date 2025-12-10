import time

from hapray.core.perf_testcase import PerfTestCase


class PerfLoad_Douyin_0050(PerfTestCase):
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
        self.start_app()
        time.sleep(5)

        def step1():
            # 点击+号
            self.touch_by_coordinates(543, 2275, 2)

        def step2():
            self.touch_by_text('滤镜', 2)
            self.touch_by_text('高清', 2)

        def step3():
            # 点击拍摄
            self.touch_by_coordinates(515, 1993, 2)

        self.execute_performance_step('抖音-发布抖音操作场景-step1点击+号', 30, step1)
        self.execute_performance_step('抖音-发布抖音操作场景-step2点击滤镜高清', 10, step2)
        # 点击空白返回上一个界面
        self.touch_by_coordinates(523, 1148, 2)
        self.execute_performance_step('抖音-发布抖音操作场景-step3点击拍摄', 20, step3)
