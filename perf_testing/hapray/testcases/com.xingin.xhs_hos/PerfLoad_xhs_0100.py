import time
from hypium import BY
from hapray.core.perf_testcase import PerfTestCase


class PerfLoad_xhs_0100(PerfTestCase):
    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(self.TAG, controllers)

        self._app_package = 'com.xingin.xhs_hos'
        self._app_name = '小红书'
        # 原始采集设备的屏幕尺寸（Nova14）
        self.source_screen_width = 1084
        self.source_screen_height = 2412

    @property
    def app_package(self) -> str:
        return self._app_package

    @property
    def app_name(self) -> str:
        return self._app_name

    def process(self):
        self.start_app()
        time.sleep(5)
        
        # 点击“+”号
        self.touch_by_coordinates(554, 2263, 2)

        self.driver.touch(BY.text('拍摄与直播'), wait_time=2)

        self.driver.touch(BY.text('翻转'), wait_time=2)

        self.driver.touch(BY.text('直播'), wait_time=2)

        # 点击封面
        self.touch_by_coordinates(258, 1461, 2)

        # 点击第一张图片
        self.touch_by_coordinates(408, 770, 2)

        self.driver.touch(BY.text('完成'), wait_time=2)

        self.driver.touch(BY.text('确定'), wait_time=2)

        time.sleep(3)

        self.driver.touch(BY.text('开始直播'), wait_time=2)

        def step1():
            time.sleep(30)

        self.execute_performance_step('小红书-直播场景-step1进入直播间，开始直播', 35, step1)

        # 点击右上角退出直播
        self.touch_by_coordinates(1015, 150, 2)

        self.driver.touch(BY.text('确定关播'), wait_time=2)

