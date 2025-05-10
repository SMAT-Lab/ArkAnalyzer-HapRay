# coding: utf-8
import os
import time

from devicetest.core.test_case import Step
from hypium import BY

from hapray.core.PerfTestCase import PerfTestCase, Log


class ResourceUsage_PerformanceDynamic_Douyin_0090(PerfTestCase):

    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(self.TAG, controllers)

        self._app_package = 'com.ss.hm.ugc.aweme'
        self._app_name = '抖音'
        self._steps = [
            {
                "name": "step1",
                "description": "1. 点击+号，停留30s，相机预览"
            },
            {
                "name": "step2",
                "description": "2. 点击滤镜图标、点击底部第一个滤镜高清"
            },
            {
                "name": "step3",
                "description": "3. 点击开始拍摄，拍摄15s"
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

        def step1(driver):
            Step('1. 点击+号，停留30s，相机预览')
            camera_component = driver.find_component(BY.id('camera_entrance_plus_icon'))
            driver.touch(camera_component)
            time.sleep(2)

        def step2(driver):
            Step('2. 点击滤镜图标、点击底部第一个滤镜高清')
            component = driver.find_component(BY.text('滤镜'))
            if not component:
                component = (1218, 1417)
            driver.touch(component)
            time.sleep(4)

            component = driver.find_component(BY.text('高清'))
            if component:
                point = component.getBoundsCenter()
                component = (point.x, point.y - 200)
            else:
                component = (156, 2511)
            driver.touch(component)
            time.sleep(3)

        def step3(driver):
            Step('3. 点击开始拍摄，拍摄15s')
            component = driver.find_component(BY.id('shoot'))
            if not component:
                component = (658, 2307)
            driver.touch(component)
            time.sleep(15)

        def finish(driver):
            driver.swipe_to_back()
            time.sleep(2)
            driver.swipe_to_home()
            time.sleep(1)

        start(self.driver)
        self.execute_step_with_perf_and_trace(1, step1, 10)
        self.execute_step_with_perf_and_trace(2, step2, 10)
        self.driver.touch((600, 600))
        time.sleep(2)
        self.execute_step_with_perf_and_trace(3, step3, 20)

        self.driver.touch((600, 600))
        finish(self.driver)

    def teardown(self):
        Log.info('teardown')
        self.driver.stop_app(self.app_package)
        self.make_reports()
