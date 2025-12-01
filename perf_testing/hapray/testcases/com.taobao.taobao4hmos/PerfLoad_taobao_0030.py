import time

from hypium import BY

from hapray.core.perf_testcase import PerfTestCase


class PerfLoad_taobao_0030(PerfTestCase):
    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(self.TAG, controllers)

        self._app_package = 'com.taobao.taobao4hmos'
        self._app_name = '淘宝'
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
            self.driver.touch(BY.text('我的淘宝'))
            self.driver.wait(1)
            self.driver.touch(BY.text('收藏'))
            self.driver.wait(1)
            # 点击第一个商品
            self.driver.touch(self.convert_coordinate(821, 519))
            time.sleep(2)
            # Step('商品详情页浏览，上滑5次')
            self.swipes_up(swip_num=5, sleep=1)
            # Step('商品详情页浏览，下滑5次')
            self.swipes_down(swip_num=5, sleep=1)
            self.driver.touch(BY.text('查看全部'))
            self.driver.wait(1)
            time.sleep(2)
            # 查看全部评价，上滑5次，下滑5次
            self.swipes_up(swip_num=5, sleep=1)
            self.swipes_down(swip_num=5, sleep=1)

        self.execute_performance_step('淘宝-商品详情浏览场景-step1商品详情页滑动', 30, step1)
