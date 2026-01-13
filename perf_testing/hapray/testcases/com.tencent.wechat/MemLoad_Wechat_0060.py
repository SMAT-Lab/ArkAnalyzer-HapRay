import time

from hypium import BY

from hapray.core.perf_testcase import PerfTestCase


class MemLoad_Wechat_0060(PerfTestCase):
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
        def step1():
            # 1.打开微信（等待5s）
            self.start_app()
            time.sleep(5)

        def step2():
            # 2.进入视频号设置页面：点击发现（等待1s），点击视频号（等待1s），点击右上角设置（等待1s）
            self.driver.touch((0.93, 0.92), wait_time=1)
            self.touch_by_text('视频号', 1)
            self.driver.touch((0.91, 0.08), wait_time=1)

        def step3():
            # 3.赞和收藏浏览：点击赞和收藏（等待2s）
            self.driver.touch((0.21, 0.19), wait_time=2)

        def step4():
            # 4.视频浏览：点击第一个视频（等待1s），上下滑动2次（等待2s）
            self.driver.touch((0.17, 0.26), wait_time=1)
            self.swipes_up(2, 2)
            self.swipes_down(2, 2)

        def step5():
            # 5.视频播放：等待10s，返回（等待2s）
            time.sleep(10)

            for _i in range(4):
                self.driver.swipe_to_back()
                time.sleep(2)
            self.driver.check_component_exist(BY.text('视频号'))

        self.execute_performance_step('微信-视频号赞和收藏场景-step1打开微信', 10, step1)
        self.execute_performance_step(
            '微信-视频号赞和收藏场景-step2进入视频号设置页面：点击发现（等待1s），点击视频号（等待1s），点击右上角设置（等待1s）',
            10,
            step2,
        )
        self.execute_performance_step('微信-视频号赞和收藏场景-step3赞和收藏浏览：点击赞和收藏（等待2s）', 10, step3)
        self.execute_performance_step(
            '微信-视频号赞和收藏场景-step4视频浏览：点击第一个视频（等待1s），上下滑动2次（等待2s）', 20, step4
        )
        self.execute_performance_step('微信-视频号赞和收藏场景-step5视频播放：等待10s，返回（等待2s）', 30, step5)
