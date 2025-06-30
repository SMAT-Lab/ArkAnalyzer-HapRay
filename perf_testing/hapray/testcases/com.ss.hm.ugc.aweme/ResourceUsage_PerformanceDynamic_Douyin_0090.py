# coding: utf-8
import os
import time

from devicetest.core.test_case import Step
from hypium import BY

from hapray.core.perf_testcase import PerfTestCase, Log
from hapray.core.common.coordinate_adapter import CoordinateAdapter


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
                component = CoordinateAdapter.convert_coordinate(
                    self.driver,
                    x=1218,  # 原始x坐标
                    y=1417,  # 原始y坐标
                    source_width=self.source_screen_width,
                    source_height=self.source_screen_height)
            driver.touch(component)
            time.sleep(4)

            component = driver.find_component(BY.text('高清'))
            if component:
                point = component.getBoundsCenter()
                component = (point.x, point.y - 200)
            else:
                component = CoordinateAdapter.convert_coordinate(
                    self.driver,
                    x=156,  # 原始x坐标
                    y=2511,  # 原始y坐标
                    source_width=self.source_screen_width,
                    source_height=self.source_screen_height)
            driver.touch(component)
            time.sleep(3)

        def step3(driver):
            Step('3. 点击开始拍摄，拍摄15s')
            component = driver.find_component(BY.id('shoot'))
            if not component:
                component = CoordinateAdapter.convert_coordinate(
                    self.driver,
                    x=658,  # 原始x坐标
                    y=2307,  # 原始y坐标
                    source_width=self.source_screen_width,
                    source_height=self.source_screen_height)
            driver.touch(component)
            time.sleep(15)

        def finish(driver):
            driver.swipe_to_back()
            time.sleep(2)
            driver.swipe_to_home()
            time.sleep(1)

        start(self.driver)
        self.execute_performance_step(1, step1, 10)
        self.execute_performance_step(2, step2, 10)
        self.driver.touch(CoordinateAdapter.convert_coordinate(
            self.driver,
            x=600,  # 原始x坐标
            y=600,  # 原始y坐标
            source_width=self.source_screen_width,
            source_height=self.source_screen_height))
        time.sleep(2)
        self.execute_performance_step(3, step3, 20)

        self.driver.touch(CoordinateAdapter.convert_coordinate(
            self.driver,
            x=600,  # 原始x坐标
            y=600,  # 原始y坐标
            source_width=self.source_screen_width,
            source_height=self.source_screen_height))
        finish(self.driver)

    def teardown(self):
        Log.info('teardown')
        self.driver.stop_app(self.app_package)
        self.generate_reports()
