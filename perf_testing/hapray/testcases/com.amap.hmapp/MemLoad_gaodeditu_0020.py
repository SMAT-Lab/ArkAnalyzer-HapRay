import time

from hypium import BY
from hypium.model.basic_data_type import MatchPattern

from hapray.core.perf_testcase import PerfTestCase


class MemLoad_gaodeditu_0020(PerfTestCase):
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
            # 3.点击第一个搜索结果，等待2s
            com = self.driver.find_component(BY.text('路线'))
            if com is None:
                com = self.driver.find_component(BY.text('公里'), MatchPattern.ENDS_WITH)
            self.driver.touch(com)
            time.sleep(2)

        def step4():
            # 4.切换到公交地铁，等待2s
            self.driver.touch(BY.text('公交地铁'))
            time.sleep(2)

        def step5():
            # 5.上滑3次，下滑4次，间隔1s
            self.swipes_up(3, 1)
            self.swipes_down(4, 1)

        def step6():
            # 6.点击第一条路线，上滑1次，下滑1次，间隔1s
            com = self.driver.find_component(BY.text('小时'), MatchPattern.CONTAINS)
            self.driver.touch(com)
            time.sleep(2)
            self.swipes_up(1, 1)
            self.swipes_down(1, 1)

        self.execute_performance_step('高德地图-公交地铁导航场景-打开高德地图', 10, step1, sample_all_processes=True)
        self.execute_performance_step('高德地图-公交地铁导航场景-点击搜索框，输入西安北站北进站口', 10, step2)
        self.execute_performance_step('高德地图-公交地铁导航场景-点击路线，点击驾车，点击开始导航', 10, step3)
        self.execute_performance_step('高德地图-公交地铁导航场景-导航停留10秒', 10, step4)
        self.execute_performance_step('高德地图-公交地铁导航场景-点击退出导航', 10, step5)
        self.execute_performance_step('高德地图-公交地铁导航场景-点击第一条路线', 10, step6)
