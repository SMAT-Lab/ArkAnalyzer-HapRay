from hypium import BY

from hapray.core.perf_testcase import PerfTestCase


class ResourceUsage_PerformanceDynamic_jingdong_0050(PerfTestCase):
    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(self.TAG, controllers)

        self._app_package = 'com.jd.hm.mall'
        self._app_name = '京东'
        # 原始采集设备的屏幕尺寸（Mate 60 Pro）
        self.source_screen_width = 1212
        self.source_screen_height = 2616

    @property
    def app_package(self) -> str:
        return self._app_package

    @property
    def app_name(self) -> str:
        return self._app_name

    def process(self):
        self.driver.swipe_to_home()

        # Step('启动京东应用')
        self.driver.start_app(self.app_package)
        self.driver.wait(3)
        # 点击逛
        self.driver.touch(BY.text('逛'))
        self.driver.wait(2)
        # 点击直播
        self.driver.touch(BY.text('直播'))
        self.driver.wait(3)

        def step1():
            # Step('京东直播上滑操作')
            self.swipes_up(swip_num=3, sleep=2)
            # Step('京东直播下滑操作')
            self.swipes_down(swip_num=3, sleep=2)

        self.execute_performance_step('京东-观看直播场景-step1直播页面上下滑动', 20, step1)
