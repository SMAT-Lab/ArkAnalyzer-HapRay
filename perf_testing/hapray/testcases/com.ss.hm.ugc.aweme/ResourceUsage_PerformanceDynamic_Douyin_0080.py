# coding: utf-8
import os
import time

from devicetest.core.test_case import Step
from hypium import BY
from hypium.model import UiParam

from hapray.core.perf_testcase import PerfTestCase, Log
from hapray.core.common.common_utils import CommonUtils


class ResourceUsage_PerformanceDynamic_Douyin_0080(PerfTestCase):

    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(self.TAG, controllers)

        self._app_package = 'com.ss.hm.ugc.aweme'
        self._app_name = '抖音'
        self._steps = [
            {
                "name": "step1",
                "description": "1. 点击查看热榜，等待2s"
            },
            {
                "name": "step2",
                "description": "2. 抖音热榜左滑5次，右滑5次，每次等待1s"
            },
            {
                "name": "step3",
                "description": "3. 侧滑返回热点，等待2s"
            },
            {
                "name": "step4",
                "description": "4. 点击长视频"
            }
        ]
        # 原始采集设备的屏幕尺寸（Pura 70 Pro）
        self.source_screen_width = 1260
        self.source_screen_height = 2844

    @property
    def steps(self) -> list[dict[str, str]]:
        return self._steps

    @property
    def app_package(self) -> str:
        return self._app_package

    @property
    def app_name(self) -> str:
        return self._app_name

    def setup(self):
        Log.info('setup')
        os.makedirs(os.path.join(self.report_path, 'hiperf'), exist_ok=True)
        os.makedirs(os.path.join(self.report_path, 'htrace'), exist_ok=True)

    def process(self):
        Step('启动被测应用')
        self.driver.wake_up_display()
        time.sleep(1)
        self.driver.swipe_to_home()
        time.sleep(1)
        # 1. 打开抖音，等待 5s
        self.driver.start_app(self.app_package)
        self.driver.wait(2)  # 等待应用启动
        time.sleep(3)

        # 2. 点击热点，等待5s
        component_toptabs = self.driver.find_component(BY.id('HomePage_Top_Tabs_Tree_Container'))
        self.driver.swipe(UiParam.RIGHT, area=component_toptabs, distance=60, start_point=(0.4, 0.1),
                          swipe_time=0.4)
        time.sleep(2)
        component_hotspots = self.driver.find_component(BY.id('home-top-tab-text-homepage_pad_hot'))
        self.driver.touch(component_hotspots)
        time.sleep(5)
        component_all_hotspots = self.driver.find_component(BY.text('完整热榜'))

        def step1(driver):
            Step('1. 点击查看热榜，等待2s')
            driver.touch(component_all_hotspots)
            time.sleep(2)

        def step2(driver):
            Step('2. 抖音热榜左滑5次，右滑5次，每次等待1s')
            for _ in range(5):
                CommonUtils.swipes_left_load(driver, 1, 1, 300)

            for _ in range(5):
                CommonUtils.swipes_right_load(driver, 1, 1, 300)

        def step3(driver):
            Step('3. 侧滑返回热点，等待2s')
            driver.swipe_to_back()
            time.sleep(2)

        def step4(driver):
            Step('4. 点击长视频')
            component = driver.find_component(BY.id('home-top-tab-text-homepage_mediumvideo'))
            driver.touch(component)
            time.sleep(2)

        def finish(driver):
            for _ in range(6):
                driver.swipe_to_back()
                time.sleep(1)
            driver.swipe_to_home()

        self.execute_performance_step(1, step1, 10)
        self.execute_performance_step(2, step2, 20)
        self.execute_performance_step(3, step3, 10)
        self.execute_performance_step(4, step4, 30)
        finish(self.driver)

    def teardown(self):
        Log.info('teardown')
        self.driver.stop_app(self.app_package)
        self.generate_reports()
