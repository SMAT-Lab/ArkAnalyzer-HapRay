# coding: utf-8

from hapray.core.perf_testcase import PerfTestCase


class ResourceUsage_PerformanceDynamic_xhs_0050(PerfTestCase):

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
            # 首页点击 ”+“
            self.touch_by_coordinates(630, 2557, 2)

            # 上滑3次，停留2s
            self.swipes_up(3, 2, 300)

            # 下滑3次，停留2s
            self.swipes_down(3, 2, 300)

            # 点击第一张照片大图查看
            self.touch_by_coordinates(142, 900, 2)

            # 左滑3次，停留2s
            self.swipes_left(3, 2, 300)

            # 右滑3次，停留2s
            self.swipes_right(3, 2, 300)

            # 选择图片
            self.touch_by_coordinates(1162, 2302, 1)

            # 点击 下一步
            self.touch_by_text('下一步（1)', 1)

            self.touch_by_text('下一步', 1)

        self.execute_performance_step("小红书-查看图片及发布笔记场景-step1图片浏览&发布笔记", 45, step1)
