# coding: utf-8
import os
import time

from devicetest.core.test_case import Step
from hypium import BY

from hapray.core.perf_testcase import PerfTestCase, Log
from hapray.core.common.coordinate_adapter import CoordinateAdapter


class ResourceUsage_PerformanceDynamic_Douyin_0110(PerfTestCase):

    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(self.TAG, controllers)

        self._app_package = 'com.ss.hm.ugc.aweme'
        self._app_name = '抖音'
        self._steps = [
            {
                "name": "step1",
                "description": "1. 点击评论区图片放大、侧滑缩小各5次，每次间隔1s"
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

            # 3. 点击私密
            driver.touch(BY.text('私密'))
            time.sleep(2)

            # 4. 点击第一个视频
            driver.touch(CoordinateAdapter.convert_coordinate(
                self.driver,
                x=222,  # 原始x坐标
                y=1877,  # 原始y坐标
                source_width=self.source_screen_width,
                source_height=self.source_screen_height))
            time.sleep(2)

            # 5. 点击评论区
            comment_component = CoordinateAdapter.convert_coordinate(
                self.driver,
                x=1187,  # 原始x坐标
                y=1750,  # 原始y坐标
                source_width=self.source_screen_width,
                source_height=self.source_screen_height)
            driver.touch(comment_component)
            time.sleep(2)

        def step1(driver):
            Step('1. 点击评论区图片放大、侧滑缩小各5次，每次间隔1s')
            for _ in range(5):
                driver.touch(CoordinateAdapter.convert_coordinate(
                    self.driver,
                    x=427,  # 原始x坐标
                    y=1465,  # 原始y坐标
                    source_width=self.source_screen_width,
                    source_height=self.source_screen_height))
                time.sleep(1)
                driver.swipe_to_back()
                time.sleep(1)

        def finish(driver):
            for _ in range(6):
                driver.swipe_to_back()
                time.sleep(1)
            driver.swipe_to_home()

        start(self.driver)
        self.execute_performance_step(1, step1, 20)
        finish(self.driver)

    def teardown(self):
        Log.info('teardown')
        self.driver.stop_app(self.app_package)
        self.generate_reports()
