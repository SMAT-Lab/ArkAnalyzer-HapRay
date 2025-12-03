import time

from hypium import BY

from hapray.core.perf_testcase import PerfTestCase


class PerfLoad_meituan_0040(PerfTestCase):
    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(self.TAG, controllers)

        self._app_package = 'com.sankuai.hmeituan'
        self._app_name = '美团'
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
        time.sleep(2)
        self.driver.touch(BY.text('外卖'))
        time.sleep(2)

        def step1():
            # Step('外卖页上滑操作')
            self.swipes_up(swip_num=5, sleep=2)
            # Step('外卖页下滑操作')
            self.swipes_down(swip_num=5, sleep=2)

        self.execute_performance_step('美团-外卖购物场景-step1外卖页浏览', 30, step1)

        # 点击搜索框
        self.driver.touch(self.convert_coordinate(455, 318))
        time.sleep(2)
        # 搜索蜜雪冰城
        search_coords = self.convert_coordinate(475, 198)
        self.driver.input_text(search_coords, '蜜雪冰城')
        self.driver.touch(BY.text('搜索'))
        time.sleep(2)

        # 点击第一家蜜雪冰城店
        self.driver.touch(self.convert_coordinate(518, 542))
        time.sleep(2)

        def step2():
            # Step('蜜雪冰城店内页上滑操作')
            self.swipes_up(swip_num=5, sleep=2)
            # Step('蜜雪冰城店内页下滑操作')
            self.swipes_down(swip_num=5, sleep=2)

        self.execute_performance_step('美团-外卖购物场景-step2店铺页浏览', 30, step2)

        # 点击放大镜
        self.driver.touch(self.convert_coordinate(516, 168))
        time.sleep(2)
        # 搜索棒打鲜橙
        search_coords = self.convert_coordinate(475, 198)
        self.driver.input_text(search_coords, '棒打鲜橙')
        self.driver.touch(BY.text('搜索'))
        time.sleep(2)

        def step3():
            self.driver.touch(BY.text('选规格'))
            time.sleep(2)
            self.driver.touch(BY.text('加入购物车'))
            time.sleep(2)
            # 点击空白退出
            self.driver.touch(self.convert_coordinate(773, 250))
            time.sleep(2)
            self.driver.touch(BY.text('去结算'))
            time.sleep(2)
            self.driver.touch(BY.text('提交订单'))
            time.sleep(2)

        self.execute_performance_step('美团-外卖购物场景-step3购物车结算', 30, step3)
