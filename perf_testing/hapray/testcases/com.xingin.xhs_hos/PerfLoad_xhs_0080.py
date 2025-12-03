import time
from hypium import BY
from hapray.core.perf_testcase import PerfTestCase


class PerfLoad_xhs_0080(PerfTestCase):
    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(self.TAG, controllers)

        self._app_package = 'com.xingin.xhs_hos'
        self._app_name = '小红书'
        # 原始采集设备的屏幕尺寸（Nova14）
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
        self.touch_by_text('我')
        self.touch_by_text('关注')
        self.touch_by_text('EDIFIER漫步者')

        def step1():
            # 点击进入直播间
            self.touch_by_text('直播', 30)
            self.touch_by_text('说点什么...', 2)
            component = self.driver.find_component(BY.text('发送')).getBoundsCenter()
            self.driver.input_text((component.x - 500, component.y), '好的谢谢')
            time.sleep(2)
            self.touch_by_text('发送', 2)

        def step2():
            # 直播间点击购物车，并在购物车商品列表页面上下滑动5次
            # 1. 点击直播间购物车图标，等待1s
            self.touch_by_coordinates(988, 2290, 1)

            # 直播间商品列表上滑下滑
            for _i in range(5):
                # 2. 直播间商品列表上滑，等待2s
                self.swipes_up(1, 2, 300)

                # 3. 直播间商品列表下滑，等待2s
                self.swipes_down(1, 2, 300)

        self.execute_performance_step('小红书-直播购物场景-step1观看直播、互动发送', 50, step1)

        self.touch_by_text('说点什么...', 2)
        self.driver.swipe_to_back()

        self.execute_performance_step('小红书-直播购物场景-step2直播间购物车商品列表页浏览', 35, step2)
