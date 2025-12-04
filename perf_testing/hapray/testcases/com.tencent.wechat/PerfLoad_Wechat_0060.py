import time
from hypium import BY
from tensorflow import double

from hapray.core.perf_testcase import PerfTestCase


class PerfLoad_Wechat_0060(PerfTestCase):
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

        def step1():
            for _i in range(5):
                # 首页下滑进入小程序页面等待2s
                self.swipes_down(1, 2)
                # 点击下方微信栏收起小程序页面
                self.touch_by_coordinates(534, 2277, 1)


        def step2():
            self.swipes_up(5, 2, 300)
            self.swipes_down(5, 2, 300)

        self.execute_performance_step('微信-京东购物小程序浏览场景-step1小程序唤起/收起', 30, step1)
        # 首页下滑进入小程序页面等待2s
        self.swipes_down(1, 2)
        # 京东购物小程序显示不全，无法通过名称点击。。。
        # self.touch_by_text('京东购物', 1)
        # 点击京东购物小程序（在第一个位置）
        self.touch_by_coordinates(200, 933, 1)
        self.execute_performance_step('微信-京东购物小程序浏览场景-step2京东购物小程序浏览', 50, step2)
 




    
        





