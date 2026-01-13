from hypium import BY

from hapray.core.perf_testcase import PerfTestCase


class MemLoad_jingdong_0010(PerfTestCase):
    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(self.TAG, controllers)

        self._app_package = 'com.jd.hm.mall'
        self._app_name = '京东'
        # 原始采集设备的屏幕尺寸（Mate 60 Pro）
        self.source_screen_width = 1260
        self.source_screen_height = 2720

    @property
    def app_package(self) -> str:
        return self._app_package

    @property
    def app_name(self) -> str:
        return self._app_name

    def process(self):
        self.driver.swipe_to_home()

        def step1():
            # 1.启动京东（等待5s）
            self.driver.start_app(self.app_package)
            self.driver.wait(5)

        def step2():
            # 2.首页浏览：点击首页（等待2s），上下滑动5次（间隔2s）
            self.driver.touch(BY.type('NodeContainer'), wait_time=2)
            self.swipes_up(swip_num=5, sleep=2)
            self.swipes_down(swip_num=5, sleep=2)

        self.execute_performance_step('京东-首页浏览场景-step1启动京东（等待5s）', 10, step1, sample_all_processes=True)
        self.execute_performance_step(
            '京东-首页浏览场景-step2首页浏览：点击首页（等待2s），上下滑动5次（间隔2s）', 30, step2
        )
