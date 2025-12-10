import time

from hapray.core.perf_testcase import PerfTestCase


class PerfLoad_Wechat_0160(PerfTestCase):
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
        time.sleep(2)

        # 首页下滑进入小程序页面等待2s
        self.swipes_down(1, 2)
        # 滴滴出行小程序显示不全，无法通过名称点击。。。
        # self.touch_by_text('滴滴出行', 1)
        # 点击滴滴出行小程序（在第一个位置）
        self.touch_by_coordinates(200, 933, 1)

        def step1():
            time.sleep(30)

        def step2():
            # self.touch_by_text('您想去哪儿？', 1)
            self.touch_by_coordinates(364, 1236, 2)
            # self.touch_by_text('完成', 1)
            self.touch_by_coordinates(980, 2208, 1)
            self.touch_by_text('西安钟楼', 1)
            time.sleep(25)

        self.execute_performance_step('微信-小程序-滴滴出行场景-step1滴滴出行主页静置', 30, step1)
        self.execute_performance_step('微信-小程序-滴滴出行场景-step2目的地选择', 30, step2)
