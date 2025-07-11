# coding: utf-8
import time

from hapray.core.perf_testcase import PerfTestCase


class ResourceUsage_PerformanceDynamic_xhs_0020(PerfTestCase):

    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(self.TAG, controllers)

        self._app_package = 'com.xingin.xhs_hos'
        self._app_name = '小红书'
        # 原始采集设备的屏幕尺寸（Mate 60 Pro）
        self.source_screen_width = 1260
        self.source_screen_height = 2720

    @property
    def app_package(self) -> str:
        return self._app_package

    @property
    def app_name(self) -> str:
        return self._app_name

    def process(self):
        # 启动被测应用
        self.start_app()

        def step1():
            # 搜索 穿搭图片

            # 点击右上角搜索，停留1s
            self.touch_by_coordinates(1169, 195, 1)

            for i in range(3):
                self.driver.input_text(self.convert_coordinate(
                    x=300,  # 原始x坐标
                    y=200  # 原始y坐标
                ), '穿搭图片')
                time.sleep(1)

                self.touch_by_text('搜索', 2)
                self.swipe_to_back(2)

        def step2():
            # 在搜索结果页面上滑3次，下滑3次
            self.swipes_up(3, 3, 300)
            self.swipes_down(3, 3, 300)

        self.execute_performance_step("小红书-搜索操作场景-step1搜索/返回", 30, step1)

        self.driver.input_text(self.convert_coordinate(
            x=300,  # 原始x坐标
            y=200  # 原始y坐标
        ), '穿搭图片')
        time.sleep(1)
        self.touch_by_text('搜索', 1)

        self.execute_performance_step("小红书-搜索操作场景-step2搜索结果页浏览", 25, step2)
