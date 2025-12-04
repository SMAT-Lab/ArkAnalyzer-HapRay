from hapray.core.perf_testcase import PerfTestCase


class PerfLoad_Douyin_0080(PerfTestCase):
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
        self.touch_by_id('home-top-tab-text-homepage_follow', 3)

        # 上滑一次去掉关注账户的直播中状态
        self.swipes_up(1, 1, 100)
        # 预加载
        self.swipes_up(10, 2, 100)
        self.swipes_down(10, 2, 100)

        def step1():
            self.swipes_up(10, 2, 100)
            self.swipes_down(10, 2, 100)

        self.execute_performance_step('抖音-关注页面浏览场景-step1关注页浏览', 50, step1)
