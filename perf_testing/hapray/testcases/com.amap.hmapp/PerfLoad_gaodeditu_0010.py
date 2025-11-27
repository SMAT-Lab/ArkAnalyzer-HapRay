import time

from hypium import BY

from hapray.core.perf_testcase import PerfTestCase


class PerfLoad_gaodeditu_0010(PerfTestCase):
    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(self.TAG, controllers)

        self._app_package = 'com.amap.hmapp'
        self._app_name = '高德地图'
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
        self.driver.start_app(self.app_package, page_name='EntryAbility')
        self.driver.wait(5)
        time.sleep(2)

        def step1():
            # 点击搜索框
            self.driver.touch(self.convert_coordinate(500, 1450))
            time.sleep(2)

            # 搜索西安钟楼
            search_coords = self.convert_coordinate(475, 198)
            self.driver.input_text(search_coords, '西安钟楼')
            self.driver.touch(BY.text('搜索'))
            time.sleep(2)
            self.driver.touch(BY.text('西安钟楼'))
            time.sleep(2)

            for _ in range(5):
                self.driver.pinch_out(BY.text('西安钟楼'))
            for _ in range(5):
                self.driver.pinch_in(BY.text('西安钟楼'))

        def step2():
            # Step('左滑操作')
            self.swipes_left(swip_num=5, sleep=2)
            # Step('右滑操作')
            self.swipes_right(swip_num=5, sleep=2)

        self.execute_performance_step('高德地图-首页放大缩小、左滑右滑场景-step1双指捏合放大缩小', 35, step1)

        self.execute_performance_step('高德地图-首页放大缩小、左滑右滑场景-step1首页左滑右滑', 30, step2)
