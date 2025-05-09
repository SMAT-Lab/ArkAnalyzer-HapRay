# coding: utf-8
import os
import time

from devicetest.core.test_case import Step
from hypium import BY
from hypium.model import UiParam

from aw.PerfTestCase import PerfTestCase, Log
from aw.common.CommonUtils import CommonUtils


class ResourceUsage_PerformanceDynamic_Douyin_0060(PerfTestCase):

    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(self.TAG, controllers)

        self._app_package = 'com.ss.hm.ugc.aweme'
        self._app_name = '抖音'
        self._steps = [
            {
                "name": "step1",
                "description": "1. 抖音-热点、关注、朋友tab页切换场景"
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

        Step('启动被测应用')
        self.driver.wake_up_display()
        time.sleep(1)
        self.driver.swipe_to_home()
        time.sleep(1)
        # 1. 打开抖音，等待 5s
        self.driver.start_app(self.app_package)
        self.driver.wait(2)  # 等待应用启动
        time.sleep(3)

        Step('1. 抖音-热点、关注、朋友tab页切换场景')
        self.driver.swipe(UiParam.RIGHT, distance=60, start_point=(0.4, 0.1), swipe_time=0.4)
        time.sleep(2)
        component_hotspots = self.driver.find_component(BY.text('热点'))
        if not component_hotspots:
            self.driver.swipe(UiParam.RIGHT, distance=60, start_point=(0.4, 0.1), swipe_time=0.4)
            time.sleep(2)
            component_hotspots = self.driver.find_component(BY.text('热点'))
        if not component_hotspots:
            component_hotspots = (420, 205)
        component_follow = self.driver.find_component(BY.text('关注'))
        if not component_follow:
            component_follow = (1050, 205)
        component_friend = self.driver.find_component(BY.id('main-bottom-tab-text-homepage_familiar'))
        if not component_friend:
            component_friend = self.driver.find_component(BY.text('朋友'))
            if not component_friend:
                component_friend = (400, 2640)


        def step1(driver):
            # 1. 点击热点
            driver.touch(component_hotspots)
            time.sleep(2)

            # 2. 热点页面上滑3次
            for _ in range(3):
                CommonUtils.swipes_up_load(driver, 1, 2, 300)

            # 3. 点击关注
            driver.touch(component_follow)
            time.sleep(2)

            # 4. 关注页面上滑3次
            for _ in range(3):
                CommonUtils.swipes_up_load(driver, 1, 2, 300)

            # 5. 点击朋友
            driver.touch(component_friend)
            time.sleep(2)

            # 6. 朋友页面上滑3次，间隔2秒
            for _ in range(3):
                CommonUtils.swipes_up_load(driver, 1, 2, 300)


        def finish(driver):
            for _ in range(6):
                driver.swipe_to_back()
                time.sleep(1)
            driver.swipe_to_home()

        self.execute_step_with_perf_and_trace(1, step1, 35)
        finish(self.driver)

    def teardown(self):
        Log.info('teardown')
        self.driver.stop_app(self.app_package)
        self.make_reports()
