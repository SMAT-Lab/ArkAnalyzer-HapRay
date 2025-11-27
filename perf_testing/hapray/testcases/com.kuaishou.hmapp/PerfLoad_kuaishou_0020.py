import time

from hypium import BY

from hapray.core.perf_testcase import PerfTestCase


class PerfLoad_kuaishou_0020(PerfTestCase):
    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(self.TAG, controllers)

        self._app_package = 'com.kuaishou.hmapp'
        self._app_name = '快手'
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
        # 点击搜索框
        self.driver.touch(self.convert_coordinate(968, 186))
        time.sleep(2)
        # 搜索华为手机
        search_coords = self.convert_coordinate(475, 198)
        self.driver.input_text(search_coords, '华为手机')
        self.driver.touch(BY.text('搜索'))
        time.sleep(2)

        def step1():
            # Step('快手首页上滑操作')
            self.swipes_up(swip_num=5, sleep=2)
            # Step('快手首页下滑操作')
            self.swipes_down(swip_num=5, sleep=2)

        self.execute_performance_step('快手-搜索页-step1搜索结束页面滑动', 35, step1)

        self.driver.swipe_to_back()

        self.driver.touch(BY.text('直播榜'))
        time.sleep(2)

        def step2():
            self.swipes_up(swip_num=3, sleep=2)
            self.swipes_down(swip_num=3, sleep=2)

        self.execute_performance_step('快手-直播-step2直播榜滑动', 35, step2)
