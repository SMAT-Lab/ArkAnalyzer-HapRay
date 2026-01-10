import time

from hypium import BY
from hypium.model.basic_data_type import UiParam

from hapray.core.perf_testcase import PerfTestCase


class MemLoad_gaodeditu_0040(PerfTestCase):
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
            # 2.点击“酒店/地名/品牌”，输入“亚朵”
            if self.driver.find_component(BY.text('订酒店')) is None:
                self.driver.swipe(UiParam.UP, distance=10, start_point=(0.5, 0.88), swipe_time=0.2)
                time.sleep(2)
            self.driver.touch(BY.text('订酒店'), wait_time=2)
            if self.driver.find_component(BY.text('免费领取')) or self.driver.find_component(BY.text('登录领取')):
                self.driver.touch((0.50, 0.69), wait_time=1)
            self.driver.touch(BY.text('酒店/地名/品牌'), wait_time=2)
            com = self.driver.find_component(BY.type('TextInput'))
            if com is None:
                self.driver.swipe_to_back()
                time.sleep(2)
                self.driver.touch(BY.text('订酒店'), wait_time=2)
                if self.driver.find_component(BY.text('立即领取')):
                    self.driver.touch((0.50, 0.69), wait_time=1)
                    time.sleep(2)

                self.driver.touch(BY.text('酒店/地名/品牌'), wait_time=2)
            self.driver.input_text(BY.type('TextInput'), '亚朵')
            time.sleep(1)

        def step3():
            # 3.点击'搜索'，等待2s
            self.driver.touch(BY.text('搜索'), wait_time=2)
            time.sleep(2)

        def step4():
            # 4.向上滑动浏览3次，每次间隔2s
            self.swipes_up(3, 2)

        def step5():
            # 5.向下滑动浏览3次，每次间隔2s
            self.swipes_down(3, 2)

        self.execute_performance_step('高德地图-订酒店场景-打开高德地图', 10, step1, sample_all_processes=True)
        self.execute_performance_step('高德地图-订酒店场景-点击“酒店/地名/品牌”，输入“亚朵”', 10, step2)
        self.execute_performance_step('高德地图-订酒店场景-点击”搜索“', 10, step3)
        self.execute_performance_step('高德地图-订酒店场景-向上滑动浏览3次，每次间隔2s', 10, step4)
        self.execute_performance_step('高德地图-订酒店场景-向下滑动浏览3次，每次间隔2s', 10, step5)
