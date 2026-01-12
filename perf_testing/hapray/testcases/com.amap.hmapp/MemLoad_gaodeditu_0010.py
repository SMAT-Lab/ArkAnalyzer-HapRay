import time

from hypium import BY
from hypium.model.basic_data_type import MatchPattern, UiParam

from hapray.core.perf_testcase import PerfTestCase


class MemLoad_gaodeditu_0010(PerfTestCase):
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
            # 2.点击搜索框，输入西安北站北进站口，点击搜索，等待2s
            self.driver.touch(self.convert_coordinate(500, 1450))
            time.sleep(2)

            # 搜索西安北站北进站口
            search_coords = self.convert_coordinate(475, 198)
            self.driver.input_text(search_coords, '西安北站北进站口')
            self.driver.touch(BY.text('搜索'))
            time.sleep(2)

        def step3():
            # 3.点击路线，点击驾车，点击开始导航，等待2s
            com = self.driver.find_component(BY.text('路线'))
            if com is None:
                com = self.driver.find_component(BY.text('公里'), MatchPattern.ENDS_WITH)
            self.driver.touch(com)
            time.sleep(2)
            # 切换到驾车
            if self.driver.find_component(BY.text('驾车')) is None:
                self.driver.swipe(UiParam.RIGHT, area=BY.type('Scroll'))
                time.sleep(2)

            self.driver.touch(BY.text('驾车'))

            # 取消车辆信息添加
            if self.driver.find_component(BY.text('取消')):
                self.driver.touch(BY.text('取消'))
                time.sleep(2)
            self.driver.touch(BY.text('开始导航'))
            time.sleep(2)
            if self.driver.find_component(BY.text('同意')):
                self.driver.touch(BY.text('同意'))
                time.sleep(2)

        def step4():
            # 4.停留10秒
            time.sleep(10)

        def step5():
            # 5.点击退出导航
            self.driver.touch(BY.text('退出'))
            time.sleep(2)
            self.driver.touch(BY.text('退出导航'))
            time.sleep(2)

        self.execute_performance_step('高德地图-驾车导航场景-打开高德地图', 10, step1, sample_all_processes=True)
        self.execute_performance_step('高德地图-驾车导航场景-点击搜索框，输入西安北站北进站口', 10, step2)
        self.execute_performance_step('高德地图-驾车导航场景-点击路线，点击驾车，点击开始导航', 10, step3)
        self.execute_performance_step('高德地图-驾车导航场景-导航停留10秒', 10, step4)
        self.execute_performance_step('高德地图-驾车导航场景-点击退出导航', 10, step5)
