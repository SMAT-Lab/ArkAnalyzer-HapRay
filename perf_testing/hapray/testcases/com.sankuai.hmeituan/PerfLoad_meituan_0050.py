import time
from typing import Optional

from hypium import BY

from hapray.core.perf_testcase import Log, PerfTestCase


class PerfLoad_meituan_0050(PerfTestCase):
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


        def step1():
            self.driver.touch(BY.text('团购'))
            time.sleep(2)
            # Step('团购页上滑操作')
            self.swipes_up(swip_num=5, sleep=2)
            # Step('团购页下滑操作')
            self.swipes_down(swip_num=5, sleep=2)

        self.execute_performance_step('美团-团购购物场景-step1团购页滑动浏览', 50, step1)

        # 点击搜索框
        self.driver.touch(self.convert_coordinate(423, 309))
        time.sleep(2)
        # 搜索蜜雪冰城
        search_coords = self.convert_coordinate(475, 198)
        self.driver.input_text(search_coords, '蜜雪冰城（樱花街店）四季春茶')
        self.driver.touch(BY.text('搜索'))
        time.sleep(2)
        # 到这里点击报错了，点不出来新客价？后面的步骤无法操作。
        # 点击第一家蜜雪冰城店
        # self.driver.touch(self.convert_coordinate(518, 542))
        # time.sleep(2)
        #
        # def step2():
        #     # Step('蜜雪冰城店内页上滑操作')
        #     self.swipes_up(swip_num=5, sleep=2)
        #     # Step('蜜雪冰城店内页下滑操作')
        #     self.swipes_down(swip_num=5, sleep=2)
        #
        # self.execute_performance_step('美团-团购购物场景-step2团购商品结算', 30, step2)


