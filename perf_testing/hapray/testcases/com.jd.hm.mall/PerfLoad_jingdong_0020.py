import time

from hypium import BY

from hapray.core.perf_testcase import PerfTestCase


class PerfLoad_jingdong_0020(PerfTestCase):
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

        # Step('启动京东应用')
        self.driver.start_app(self.app_package)
        self.driver.wait(5)

        # 点击我的
        self.driver.touch(BY.text('我的'))
        time.sleep(2)

        # 选择收藏商品
        self.driver.touch(BY.text('商品收藏'))
        time.sleep(2)

        # 点击收藏页第一个商品
        self.driver.touch(self.convert_coordinate(256, 980))
        time.sleep(2)

        def step1():
            # Step('京东收藏页上滑操作')
            self.swipes_up(swip_num=3, sleep=2)
            # Step('京东收藏页下滑操作')
            self.swipes_down(swip_num=3, sleep=2)
            self.driver.touch(BY.text('立即购买'))
            self.driver.wait(2)
            self.driver.touch(BY.text('确认'))
            time.sleep(5)

        self.execute_performance_step('京东-新品页滑动浏览场景-step2商品详情页上下滑动及结算', 10, step1)
