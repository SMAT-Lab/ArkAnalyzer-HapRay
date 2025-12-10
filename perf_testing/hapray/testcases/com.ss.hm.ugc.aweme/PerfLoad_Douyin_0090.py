import time

from hypium import BY

from hapray.core.perf_testcase import PerfTestCase


class PerfLoad_Douyin_0090(PerfTestCase):
    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(self.TAG, controllers)

        self._app_package = 'com.ss.hm.ugc.aweme'
        self._app_name = '抖音'
        # 原始采集设备的屏幕尺寸（Pura 70 Pro）
        self.source_screen_width = 1260
        self.source_screen_height = 2844

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
        self.touch_by_id('home-top-tab-text-homepage_mall', 3)

        # 3. 预先下滑预加载20次，再上滑15次
        self.swipes_up(20, 1, 300)
        self.swipes_down(15, 1, 300)

        def step1():
            # 上滑10次/下滑10次，等待1s
            self.swipes_up(10, 1, 300)
            self.swipes_down(10, 1, 300)

        def step2():
            # 商品详情页上滑5次，间隔2s
            self.swipes_up(5, 2, 300)

        self.execute_performance_step('抖音-商城浏览场景-step1商城页浏览', 35, step1)

        # 点击搜索按钮，输入“华为P80PRO官方旗舰店”，点击搜索，选择第一个商品
        self.touch_by_coordinates(450, 286)
        self.driver.input_text(BY.type('TextInput'), '华为P80PRO官方旗舰店')
        time.sleep(1)
        self.touch_by_text('搜索', 3)
        self.touch_by_coordinates(858, 681, 1)
        self.execute_performance_step('抖音-商城浏览场景-step2商品详情页浏览', 30, step2)
