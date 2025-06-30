# coding: utf-8
import os
import time

from devicetest.core.test_case import Step
from hypium import BY

from hapray.core.perf_testcase import PerfTestCase, Log
from hapray.core.common.common_utils import CommonUtils
from hapray.core.common.coordinate_adapter import CoordinateAdapter


class ResourceUsage_PerformanceDynamic_Douyin_0010(PerfTestCase):

    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(self.TAG, controllers)

        self._app_package = 'com.ss.hm.ugc.aweme'
        self._app_name = '抖音'
        self._steps = [
            {
                "name": "step1",
                "description": "1. 抖音“我”页面点击观看历史，等待2s"
            },
            {
                "name": "step2",
                "description": "2. 观看历史上滑5次，每次等待1s;观看历史下滑5次，每次等待1s"
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

            # 2. 抖音点击“我”，等待 2s
            driver.touch(BY.text('我'))
            time.sleep(2)

            # 3. 抖音“我”页面点击右上角选项，等待2s
            component_history = CoordinateAdapter.convert_coordinate(
                self.driver,
                x=1114,  # 原始x坐标
                y=180,  # 原始y坐标
                source_width=self.source_screen_width,
                source_height=self.source_screen_height)
            driver.touch(component_history)
            time.sleep(2)

        def step1(driver):
            Step('1. 抖音“我”页面点击观看历史，等待2s')
            component = driver.find_component(BY.text('观看历史'))
            if not component:
                component = CoordinateAdapter.convert_coordinate(
                    self.driver,
                    x=758,  # 原始x坐标
                    y=726,  # 原始y坐标
                    source_width=self.source_screen_width,
                    source_height=self.source_screen_height)
            driver.touch(component)
            time.sleep(2)

        def step2(driver):
            Step('2. 观看历史上滑5次，每次等待1s;观看历史下滑5次，每次等待1s')
            for _ in range(5):
                CommonUtils.swipes_up_load(driver, 1, 1, 300)

            for _ in range(5):
                CommonUtils.swipes_down_load(driver, 1, 1, 300)

        def finish(driver):
            for _ in range(6):
                driver.swipe_to_back()
                time.sleep(1)
            driver.swipe_to_home()

        start(self.driver)
        self.execute_performance_step(1, step1, 10)
        self.execute_performance_step(2, step2, 20)
        finish(self.driver)

    def teardown(self):
        Log.info('teardown')
        self.driver.stop_app(self.app_package)
        self.generate_reports()
