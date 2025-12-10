import time

from hapray.core.perf_testcase import PerfTestCase


class PerfLoad_Wechat_0080(PerfTestCase):
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
        time.sleep(5)

        # self.touch_by_text('发现', 2)
        # self.driver.touch(BY.text('发现'))
        # time.sleep(2)
        # 点击发现
        self.touch_by_coordinates(690, 2228, 1)
        self.touch_by_text('视频号', 2)
        # 点击右上角图标
        self.touch_by_coordinates(1006, 180, 1)
        self.touch_by_text('赞和收藏', 1)
        # 点击第一个视频
        self.touch_by_coordinates(180, 600, 1)

        def step1():
            self.swipes_up(10, 2)

        def step2():
            # 点击第一个直播
            self.touch_by_coordinates(281, 983, 1)
            self.swipes_up(6, 1)
            time.sleep(4)

        self.execute_performance_step('微信-浏览视频号、直播间、购物、游戏、电影场景-step1视频号视频浏览', 30, step1)
        # 返回发现页面，等2s
        for _i in range(4):
            self.swipe_to_back(1)
        time.sleep(2)
        self.touch_by_text('直播', 2)
        self.execute_performance_step('微信-浏览视频号、直播间、购物、游戏、电影场景-step2直播间切换', 35, step2)
        # 返回发现页面，等2s
        for _i in range(2):
            self.swipe_to_back()
        time.sleep(2)
