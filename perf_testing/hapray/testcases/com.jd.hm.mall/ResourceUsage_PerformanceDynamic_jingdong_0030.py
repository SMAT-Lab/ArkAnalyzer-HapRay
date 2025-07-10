# coding: utf-8

from hypium import BY

from hapray.core.perf_testcase import PerfTestCase


class ResourceUsage_PerformanceDynamic_jingdong_0030(PerfTestCase):

    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(self.TAG, controllers)

        self._app_package = 'com.jd.hm.mall'
        self._app_name = '京东'
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

        # Step('启动京东应用')
        self.driver.start_app(self.app_package)
        self.driver.wait(5)

        # 点击京东超市
        # 从(824, 922)滑动至(7, 1344)
        p1 = self.convert_coordinate(867, 538)
        p2 = self.convert_coordinate(7, 538)
        self.driver.slide(p1, p2)
        self.driver.wait(1)
        # 点击type为{Text}并且text为{全部频道}的控件
        self.driver.touch(BY.type('Text').text('全部频道'))
        self.driver.wait(2)

        self.swipes_up(swip_num=1, sleep=2)
        self.driver.touch(BY.text('京东超市'))
        self.driver.wait(1)
        self.swipe_to_back(1)

        def step1():
            self.driver.touch(BY.text('京东超市'))
            self.driver.wait(2)

            # 点击粮油调味
            self.driver.touch(BY.text('粮油调味'))
            self.driver.wait(2)

            # Step('粮油调味页上滑操作')
            self.swipes_up(swip_num=3, sleep=2)
            # Step('粮油调味页下滑操作')
            self.swipes_down(swip_num=5, sleep=2)

            # 加入第一个商品到购物车
            self.driver.touch(self.convert_coordinate(1002, 956))
            self.driver.wait(2)

        self.execute_performance_step("京东-超市购物场景-step1浏览商品后加购", 45, step1)

        # 从购物车移除第一个商品
        self.driver.touch(self.convert_coordinate(866, 956))
        self.driver.wait(2)
