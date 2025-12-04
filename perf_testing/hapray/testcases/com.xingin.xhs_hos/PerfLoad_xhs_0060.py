import time

from hapray.core.perf_testcase import PerfTestCase


class PerfLoad_xhs_0060(PerfTestCase):
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
        self.start_app()

        # 拖拽显示隐藏tab栏
        self.swipes_down(swip_num=1, sleep=5)

        def step1():
            # 点击进入、退出直播间操作5次

            # 1. 点击顶部隐藏tab页进入直播页，等待2s
            self.touch_by_text('直播', 2)

            self.swipes_up(3, 2, 300)
            self.swipes_down(3, 2, 300)

        self.execute_performance_step('小红书-浏览直播场景-step1直播间观看/退出', 30, step1)
