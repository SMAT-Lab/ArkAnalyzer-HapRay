from hapray.core.perf_testcase import PerfTestCase


class ResourceUsage_PerformanceDynamic_kugou_0010(PerfTestCase):
    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(self.TAG, controllers)
        self._app_package = 'com.kugou.hmmusic'
        self._app_name = '酷狗'
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
        self.driver.swipe_to_home()

        # Step('启动被测应用')
        self.driver.start_app(self.app_package)
        self.driver.wait(5)

        def step1():
            # 首页
            self.touch_by_coordinates(229, 2244, 2)
            # 上滑2次
            self.swipes_up(swip_num=1, sleep=2)
            # 我的
            self.touch_by_coordinates(854, 2244, 2)
            # 切换到首页
            self.touch_by_coordinates(229, 2244, 2)
            # 上滑2次
            self.swipes_down(swip_num=1, sleep=2)

        def step2():
            # 点击“每日推荐”
            # 1.0.3
            # self.touch_by_coordinates(239,496, 2)
            self.touch_by_coordinates(626, 619, 2)
            self.touch_by_coordinates(118, 1112, 2)

            # 1.0.3
            # self.swipes_up(swip_num=5, sleep=6)
            for _ in range(5):
                self.touch_by_coordinates(812, 2119, 6)

        self.execute_performance_step('酷狗-首页浏览场景-step1首页切换', 10, step1)
        self.execute_performance_step('酷狗-首页浏览场景-step2音乐浏览', 40, step2)
