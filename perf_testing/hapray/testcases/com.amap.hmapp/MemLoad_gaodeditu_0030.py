import time

from hypium import BY

from hapray.core.perf_testcase import PerfTestCase


class MemLoad_gaodeditu_0030(PerfTestCase):
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
        def step1():
            # 1. 打开高德地图(等待5秒)
            self.driver.start_app(self.app_package, page_name='EntryAbility')
            self.driver.wait(5)
            time.sleep(5)

        def step2():
            # 2.点击搜索框，输入西安北站，点击搜索，等待2s
            self.driver.touch(BY.text('查找地点、公交、地铁'))
            time.sleep(2)
            self.driver.input_text(BY.type('TextInput'), '西安北站')
            time.sleep(1)
            self.driver.touch(BY.text('搜索'))
            time.sleep(2)

        def step3():
            # 3.双指捏合缩小地图
            self.driver.pinch_in(area=BY.type('RelativeContainer'))
            time.sleep(1)

        def step4():
            # 4.双指捏合放大地图
            self.driver.pinch_out(area=BY.type('RelativeContainer'))
            time.sleep(1)

        self.execute_performance_step('高德地图-放大缩小地图场景-打开高德地图', 10, step1, sample_all_processes=True)
        self.execute_performance_step('高德地图-放大缩小地图场景-点击搜索框，输入西安北站北进站口', 10, step2)
        self.execute_performance_step('高德地图-放大缩小地图场景-双指捏合缩小地图', 10, step3)
        self.execute_performance_step('高德地图-放大缩小地图场景-双指捏合放大地图', 10, step4)
