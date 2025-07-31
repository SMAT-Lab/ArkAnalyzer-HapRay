# coding: utf-8

from hapray.core.perf_testcase import PerfTestCase

"""
@场景用例
大桌面滑动测试
@场景描述
模拟用户在大桌面环境下进行左右滑动操作，以测试桌面环境的滑动性能和资源占用。
该脚本结构模仿小红书性能测试用例，将主要操作封装在 execute_performance_step 中。
@用例步骤
1. 启动桌面应用（如果未运行）。
2. 执行多次左滑操作。
3. 执行多次右滑操作。
"""


class ResourceUsage_PerformanceDynamic_Launcher_0020(PerfTestCase):
    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(self.TAG, controllers)

        self._app_package = 'com.ohos.sceneboard'
        self._app_name = '桌面'

        self.source_screen_width = 1260
        self.source_screen_height = 2720

    @property
    def app_package(self) -> str:
        return self._app_package

    @property
    def app_name(self) -> str:
        return self._app_name

    def process(self):
        """
        主测试流程：启动桌面应用并执行滑动性能场景。
        """

        def desktop_swipe_action():
            # 1. 屏幕左滑 3 次
            self.swipes_left(3, 2, 300)

            # 右滑3次，停留2s
            self.swipes_right(3, 2, 300)

        self.execute_performance_step(
            "桌面-滑动场景",
            30,  # 性能数据采集将持续 30 秒
            desktop_swipe_action  # 实际执行滑动操作的函数
        )
