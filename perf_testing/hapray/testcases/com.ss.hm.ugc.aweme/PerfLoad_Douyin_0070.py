from hapray.core.perf_testcase import PerfTestCase


class PerfLoad_Douyin_0070(PerfTestCase):
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

        def step1():
            # 小黄车商品列表浏览
            self.touch_by_coordinates(734, 2638, 3)
            self.swipes_up(5, 2, 300)
            self.swipes_down(5, 2, 300)

        def step2():
            # 点击进入第一个商品详情，详情页上下滑动5次，间隔2s')
            self.touch_by_coordinates(259, 1755, 3)
            self.swipes_up(5, 2, 300)
            self.swipes_down(5, 2, 300)

        def step3():
            # 购物车列表浏览
            self.touch_by_text('购物车', 3)
            self.swipes_up(5, 2, 300)
            self.swipes_down(5, 2, 300)

        # 1. 打开抖音，等待 5s
        self.start_app()

        # 2. 点击进入“关注”tab页
        self.touch_by_id('home-top-tab-text-homepage_follow', 3)

        # 3. 点击进入第一个直播间
        self.touch_by_text('东方甄选', 2)

        # Step1
        self.execute_performance_step('抖音直播页面-点击-页面切换-step1小黄车列表', 20, step1)
        # Step2： 点开第一个商品详情页
        self.execute_performance_step('抖音直播页面-商品详情页面-滑动-step2详情页滑动', 40, step2)

        self.swipe_to_back()
        # Step3: 点开购物车
        self.execute_performance_step('抖音购物车页-滑动-应用内操作-购物车页-step3购物车页上下滑动', 35, step3)

