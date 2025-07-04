# coding: utf-8
import time

from hapray.core.perf_testcase import PerfTestCase


class ResourceUsage_PerformanceDynamic_Douyin_0120(PerfTestCase):

    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(self.TAG, controllers)

        self._app_package = 'com.ss.hm.ugc.aweme'
        self._app_name = '抖音'
        self._steps = [
            {
                "name": "step1",
                "description": "1. 直播间观看/退出"
            },
            {
                "name": "step2",
                "description": "2. 直播间切换浏览"
            }
        ]
        # 原始采集设备的屏幕尺寸（Pura 70 Pro）
        self.source_screen_width = 1260
        self.source_screen_height = 2844

    @property
    def steps(self) -> list[dict[str, str]]:
        return self._steps

    @property
    def app_package(self) -> str:
        return self._app_package

    @property
    def app_name(self) -> str:
        return self._app_name

    def process(self):
        # 1. 打开抖音，等待 5s
        self.start_app()

        # 2. 点击进入“关注”tab页
        self.touch_by_id('home-top-tab-text-homepage_follow', 3)

        # 3. 点击进入第一个直播间
        self.touch_by_id('border_circle_container', 2)

        def step1():
            # 等待10s退出
            time.sleep(10)

        def step2():
            # 直播间上滑切换5次，间隔10s
            self.swipes_up(5, 10, 300)

        self.execute_performance_step(1, step1, 20)
        self.execute_performance_step(2, step2, 60)
