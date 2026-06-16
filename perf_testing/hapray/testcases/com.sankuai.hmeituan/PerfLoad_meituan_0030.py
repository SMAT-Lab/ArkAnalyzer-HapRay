import time

from hypium import BY
from hypium.model.basic_data_type import MatchPattern

from hapray.core.perf_testcase import PerfTestCase


class PerfLoad_meituan_0030(PerfTestCase):
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

        # 点击搜索框
        self.driver.touch(self.convert_coordinate(473, 300))
        time.sleep(2)

        def step1():
            # 搜索霸王茶姬
            search_coords = self.convert_coordinate(475, 198)
            self.driver.input_text(search_coords, '霸王茶姬')
            self.driver.touch(BY.text('搜索'))
            time.sleep(2)
            # Step('美团霸王茶姬页上滑操作')
            self.swipes_up(swip_num=5, sleep=2)
            # Step('美团霸王茶姬页下滑操作')
            self.swipes_down(swip_num=5, sleep=2)

        self.execute_performance_step('美团-霸王茶姬滑动浏览场景-step1霸王茶姬页上下滑动', 35, step1)

        # 点击第一家霸王茶姬奶茶店
        # self.driver.touch(self.convert_coordinate(521, 465))
        # time.sleep(2)
        com = self.driver.find_all_components(BY.text('霸王茶姬', MatchPattern.STARTS_WITH), 1)
        self.driver.touch(com, wait_time=2)

        def step2():
            # Step('霸王茶姬店内页上滑操作')
            self.swipes_up(swip_num=5, sleep=2)
            # Step('霸王茶姬店内页下滑操作')
            self.swipes_down(swip_num=5, sleep=2)

        self.execute_performance_step('美团-霸王茶姬滑动浏览场景-step2霸王茶姬店内页上下滑动', 30, step2)

        self.driver.touch(BY.text('评价'))
        time.sleep(2)
        # self.driver.touch(BY.text('更多评价'))
        # time.sleep(2)

        def step3():
            # Step('霸王茶姬评价页上滑操作')
            self.swipes_up(swip_num=5, sleep=2)
            # Step('霸王茶姬评价页下滑操作')
            self.swipes_down(swip_num=5, sleep=2)

        self.execute_performance_step('美团-霸王茶姬滑动浏览场景-step3霸王茶姬评价页上下滑动', 30, step3)
