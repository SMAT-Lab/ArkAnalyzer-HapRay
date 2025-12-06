import time

from hapray.core.perf_testcase import PerfTestCase


class PerfLoad_xhs_0070(PerfTestCase):
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
        time.sleep(2)
        self.touch_by_text('我', 2)
        self.touch_by_text('赞过', 2)

        def step1():
            # 点击第一个视频
            self.touch_by_coordinates(279, 1745, 1)

            self.swipes_up(5, 2, 300)
            self.swipes_down(5, 2, 300)

            # 取消点赞
            self.touch_by_coordinates(520, 2570, 1)
            time.sleep(2)
            # 点赞
            self.touch_by_coordinates(520, 2570, 1)
            time.sleep(2)

        self.execute_performance_step('小红书-视频及评论浏览-step1视频切换浏览', 30, step1)
