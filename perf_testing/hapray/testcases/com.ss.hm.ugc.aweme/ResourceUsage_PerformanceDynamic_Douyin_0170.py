from hapray.core.perf_testcase import PerfTestCase


class ResourceUsage_PerformanceDynamic_Douyin_0170(PerfTestCase):
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
            # 点击直播间礼物，礼物界面滑动5次，间隔2s
            self.touch_by_coordinates(1031, 2638, 3)
            self.swipes_up(5, 2, 300)

        def step2():
            # 人气榜/小时榜，列表上滑5次，间隔2s
            self.touch_by_coordinates(364, 793, 3)
            self.swipes_up(5, 2, 300)
            self.touch_by_coordinates(121, 793, 3)
            self.swipes_up(5, 2, 300)

        def step3():
            # 小黄车商品列表浏览
            self.touch_by_coordinates(734, 2638, 3)
            self.swipes_up(5, 2, 300)
            self.swipes_down(5, 2, 300)

        def step4():
            # 点击进入第一个商品详情，详情页上下滑动5次，间隔2s')
            self.touch_by_coordinates(259, 1755, 3)
            self.swipes_up(5, 2, 300)
            self.swipes_down(5, 2, 300)

        def step5():
            # 购物车列表浏览
            self.touch_by_text('购物车', 3)
            self.swipes_up(5, 2, 300)
            self.swipes_down(5, 2, 300)

        # 1. 打开抖音，等待 5s
        self.start_app()

        # 2. 点击进入“关注”tab页
        self.touch_by_id('home-top-tab-text-homepage_follow', 3)

        # 3. 点击进入第一个直播间
        self.touch_by_text('EDIFIER漫步者官方旗舰店', 2)

        # Step1
        self.execute_performance_step('抖音-直播间操作场景-step1直播间礼物浏览', 20, step1)
        # 收起礼物界面
        self.touch_by_coordinates(500, 700, 2)

        # Step2: 点开小时榜
        self.touch_by_coordinates(173, 341, 2)
        self.execute_performance_step('抖音-直播间操作场景-step2人气榜/小时榜浏览', 40, step2)
        # 关闭小时榜
        self.touch_by_coordinates(173, 341, 2)

        # Step3: 点开小黄车
        self.execute_performance_step('抖音-直播间操作场景-step3小黄车商品列表浏览', 35, step3)

        # Step4: 商品详情浏览
        self.execute_performance_step('抖音-直播间操作场景-step4商品详情页浏览', 35, step4)
        self.swipe_to_back()

        # Step5: 购物车浏览
        self.execute_performance_step('抖音-直播间操作场景-step5购物车列表浏览', 35, step5)
