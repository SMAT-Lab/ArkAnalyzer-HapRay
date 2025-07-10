# coding: utf-8
import time

from hapray.core.perf_testcase import PerfTestCase


class ResourceUsage_PerformanceDynamic_Douyin_0090(PerfTestCase):

    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(self.TAG, controllers)

        self._app_package = 'com.ss.hm.ugc.aweme'
        self._app_name = '抖音'
        # 原始采集设备的屏幕尺寸（Pura 70 Pro）
        self.source_screen_width = 1260
        self.source_screen_height = 2844

    @property
    def app_package(self) -> str:
        return self._app_package

    @property
    def app_name(self) -> str:
        return self._app_name

    def process(self):
        def step1():
            # 1. 点击+号，停留30s，相机预览
            self.touch_by_id('camera_entrance_plus_icon')

        def step2():
            # 2. 点击滤镜图标、点击底部第一个滤镜高清
            ret = self.touch_by_text('滤镜', 4)
            if not ret:
                self.touch_by_coordinates(1218, 1417, 4)

            self.touch_by_text('高清', 3)
            time.sleep(3)

        def step3():
            # 3. 点击开始拍摄，拍摄15s
            ret = self.touch_by_id('shoot', 15)
            if not ret:
                self.touch_by_coordinates(658, 2307, 15)

        self.start_app()
        self.execute_performance_step("抖音-发布抖音操作场景-step1点击+号", 10, step1)
        self.execute_performance_step("抖音-发布抖音操作场景-step2点击滤镜高清", 10, step2)
        self.touch_by_coordinates(600, 600, 2)
        self.execute_performance_step("抖音-发布抖音操作场景-step3点击拍摄", 20, step3)
        self.touch_by_coordinates(600, 600, 2)
        self.swipe_to_back()
