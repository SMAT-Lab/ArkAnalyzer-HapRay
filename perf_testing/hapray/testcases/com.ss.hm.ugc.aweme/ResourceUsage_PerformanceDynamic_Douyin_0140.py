# coding: utf-8
import os
import time

from devicetest.core.test_case import Step
from hypium import BY
from hypium.model import UiParam

from hapray.core.PerfTestCase import PerfTestCase, Log
from hapray.core.common.CommonUtils import CommonUtils


class ResourceUsage_PerformanceDynamic_Douyin_0140(PerfTestCase):

    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(self.TAG, controllers)

        self._app_package = 'com.ss.hm.ugc.aweme'
        self._app_name = '抖音'
        self._steps = [
            {
                "name": "step1",
                "description": "1. 点击底部热榜，左右拖滑切换tab页5次，每次间隔2s"
            },
            {
                "name": "step2",
                "description": "2. 点击下一个热榜跳转视频，每次间隔10s"
            }
        ]

    @property
    def steps(self) -> []:
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
        os.makedirs(os.path.join(self.report_path, 'report'), exist_ok=True)

    def process(self):
        def start(driver):
            Step('启动被测应用')
            driver.wake_up_display()
            time.sleep(1)
            self.driver.swipe_to_home()
            time.sleep(1)
            # 1. 打开抖音，等待 5s
            self.driver.start_app(self.app_package)
            driver.wait(2)  # 等待应用启动
            time.sleep(3)

            component_toptabs = self.driver.find_component(BY.id('HomePage_Top_Tabs_Tree_Container'))
            self.driver.swipe(UiParam.RIGHT, area=component_toptabs, distance=60, start_point=(0.4, 0.1),
                              swipe_time=0.4)
            time.sleep(2)
            component_hotspots = self.driver.find_component(BY.id('home-top-tab-text-homepage_pad_hot'))
            self.driver.touch(component_hotspots)
            time.sleep(5)

            # 2. 点击第一个抖音热榜进入视频页，点击进入第一个视频
            driver.touch((269, 520))
            time.sleep(2)

        def step1(driver):
            Step('1. 点击底部热榜，左右拖滑切换tab页5次，每次间隔2s')
            driver.touch((520, 2620))
            time.sleep(2)

            for _ in range(5):
                CommonUtils.swipes_left_load(driver, 1, 2, 300)

            for _ in range(5):
                CommonUtils.swipes_right_load(driver, 1, 2, 300)

        def step2(driver):
            Step('2. 点击下一个热榜跳转视频，每次间隔10s')
            for _ in range(5):
                driver.touch((1196, 2621))
                time.sleep(10)

        def finish(driver):
            driver.swipe_to_home()

        start(self.driver)
        self.execute_step_with_perf_and_trace(1, step1, 30)
        self.driver.swipe_to_back()
        time.sleep(5)
        self.execute_step_with_perf_and_trace(2, step2, 60)
        finish(self.driver)

    def teardown(self):
        Log.info('teardown')
        self.driver.stop_app(self.app_package)
        self.make_reports()
