# coding: utf-8
import os
import time

from devicetest.core.test_case import Step
from hypium import BY

from hapray.core.common.common_utils import CommonUtils
from hapray.core.common.coordinate_adapter import CoordinateAdapter
from hapray.core.perf_testcase import PerfTestCase, Log


class ResourceUsage_PerformanceDynamic_xhs_0010(PerfTestCase):

    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(self.TAG, controllers)

        self._app_package = 'com.xingin.xhs_hos'
        self._app_name = '小红书'
        self._steps = [
            {
                "name": "step1",
                "description": "1. 首页上滑5次、下滑5次，停留2s"
            },
            {
                "name": "step2",
                "description": "2. 点击第一个视频，滑动切换视频上5次下5次，点击取消点赞/点赞各一次"
            },
            {
                "name": "step3",
                "description": "3. 点击评论区，上滑5次"
            }
        ]
        # 原始采集设备的屏幕尺寸（Mate 60 Pro）
        self.source_screen_width = 1260
        self.source_screen_height = 2720

    @property
    def steps(self) -> list:
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
        self.driver.swipe_to_home()

        Step('启动被测应用')
        self.driver.start_app(self.app_package)
        self.driver.wait(5)

        def step1(driver):
            Step('1. 首页上滑5次、下滑5次，停留2s')
            # 上滑5次
            for i in range(5):
                CommonUtils.swipes_up_load(driver, 1, 1, 300)
                time.sleep(2)

            # 上滑5次
            for i in range(5):
                CommonUtils.swipes_down_load(driver, 1, 1, 300)
                time.sleep(2)

        def after_step1():
            time.sleep(10)
            self.driver.touch(BY.text('我'))
            time.sleep(3)
            self.driver.touch(BY.text('赞过'))
            time.sleep(1)
            # 拖拽显示隐藏文字
            start = CoordinateAdapter.convert_coordinate(
                self.driver,
                x=630,   # 原始x坐标
                y=2370,  # 原始y坐标
                source_width=self.source_screen_width,
                source_height=self.source_screen_height
            )
            end = CoordinateAdapter.convert_coordinate(
                self.driver,
                x=630,   # 原始x坐标
                y=1977,  # 原始y坐标
                source_width=self.source_screen_width,
                source_height=self.source_screen_height
            )
            CommonUtils.swipe(self.driver.device_sn, start[0], start[1], end[0], end[1], 500)
            time.sleep(1)

        def step2(driver):
            Step('2. 点击第一个视频，滑动切换视频上5次下5次，点击取消点赞/点赞各一次')
            # 点击进入任意视频
            driver.touch(CoordinateAdapter.convert_coordinate(
                self.driver,
                x=300,   # 原始x坐标
                y=1500,  # 原始y坐标
                source_width=self.source_screen_width,
                source_height=self.source_screen_height
            ))
            time.sleep(2)
            # 点赞过的视频，上滑5次
            for i in range(5):
                CommonUtils.swipes_up_load(self.driver, 1, 2)
            # 点赞过的视频，下滑5次
            for i in range(5):
                CommonUtils.swipes_down_load(self.driver, 1, 2)
            # 取消点赞、点赞
            self.driver.touch(CoordinateAdapter.convert_coordinate(
                self.driver,
                x=621,   # 原始x坐标
                y=2551,  # 原始y坐标
                source_width=self.source_screen_width,
                source_height=self.source_screen_height
            ))  # TODO 这里有坑，不同视屏，点赞/收藏/评论数不同，坐标会便宜
            time.sleep(1)
            self.driver.touch(CoordinateAdapter.convert_coordinate(
                self.driver,
                x=621,   # 原始x坐标
                y=2551,  # 原始y坐标
                source_width=self.source_screen_width,
                source_height=self.source_screen_height
            ))
            time.sleep(1)

        def after_step2():
            time.sleep(5)
            CommonUtils.swipes_up_load(self.driver, 1, 2)

        def step3(driver):
            Step('3. 点击评论区，上滑5次')
            time.sleep(1)
            # 点击弹出视频评论区
            driver.touch(CoordinateAdapter.convert_coordinate(
                self.driver,
                x=1047,  # 原始x坐标
                y=2552,  # 原始y坐标
                source_width=self.source_screen_width,
                source_height=self.source_screen_height
            ))  # Mate60Pro
            time.sleep(2)

            # 上滑5次
            for i in range(5):
                CommonUtils.swipes_up_load(self.driver, 1, 2)

        def after_step3():
            self.driver.touch(CoordinateAdapter.convert_coordinate(
                self.driver,
                x=650,  # 原始x坐标
                y=360,  # 原始y坐标
                source_width=self.source_screen_width,
                source_height=self.source_screen_height
            ))
            time.sleep(1)
            self.driver.swipe_to_back()
            time.sleep(1)

        self.execute_performance_step(1, step1, 30)
        after_step1()
        self.execute_performance_step(2, step2, 30)
        after_step2()
        self.execute_performance_step(3, step3, 20)
        after_step3()

    def teardown(self):
        Log.info('teardown')
        self.driver.stop_app(self.app_package)
        self.generate_reports()
