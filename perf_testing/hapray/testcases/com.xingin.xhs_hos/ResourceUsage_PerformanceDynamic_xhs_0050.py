# coding: utf-8
import os
import time

from devicetest.core.test_case import Step
from hypium import BY

from hapray.core.common.common_utils import CommonUtils
from hapray.core.common.coordinate_adapter import CoordinateAdapter
from hapray.core.perf_testcase import PerfTestCase, Log


class ResourceUsage_PerformanceDynamic_xhs_0050(PerfTestCase):

    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(self.TAG, controllers)

        self._app_package = 'com.xingin.xhs_hos'
        self._app_name = '小红书'
        self._steps = [
            {
                "name": "step1",
                "description": "1. 查看图片及发布笔记"
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
            Step('1. 查看图片及发布笔记')
            # 首页点击 ”+“
            driver.touch(CoordinateAdapter.convert_coordinate(
                driver,
                x=630,  # 原始x坐标
                y=2557,  # 原始y坐标
                source_width=self.source_screen_width,
                source_height=self.source_screen_height
            ))
            time.sleep(2)
            # 上滑3次，停留2s
            for i in range(3):
                CommonUtils.swipes_up_load(driver, 1, 2, 300)

            # 下滑3次，停留2s
            for i in range(3):
                CommonUtils.swipes_down_load(driver, 1, 2, 300)

            # 点击第一张照片大图查看
            driver.touch(CoordinateAdapter.convert_coordinate(
                driver,
                x=142,  # 原始x坐标
                y=900,  # 原始y坐标
                source_width=self.source_screen_width,
                source_height=self.source_screen_height
            ))

            time.sleep(2)

            # 左滑3次，停留2s
            for i in range(3):
                CommonUtils.swipes_left_load(driver, 1, 2, 300)

            # 右滑3次，停留2s
            for i in range(3):
                CommonUtils.swipes_right_load(driver, 1, 2, 300)

            # 选择图片
            driver.touch(CoordinateAdapter.convert_coordinate(
                driver,
                x=1162,  # 原始x坐标
                y=2302,  # 原始y坐标
                source_width=self.source_screen_width,
                source_height=self.source_screen_height
            ))
            time.sleep(1)
            # 点击 下一步
            # driver.touch((1019, 2420))
            component = driver.find_component(BY.type('Text').text('下一步（1)'))
            driver.touch(component)
            time.sleep(1)
            # 再次 点击 下一步
            # driver.touch((1102, 211))
            component = driver.find_component(BY.type('Text').text('下一步'))
            driver.touch(component)
            time.sleep(1)

        self.execute_performance_step(1, step1, 40)
        # 侧滑两次返回
        self.driver.swipe_to_back()
        time.sleep(1)
        self.driver.swipe_to_back()
        time.sleep(1)
        # 返回首页
        self.driver.swipe_to_back()
        time.sleep(1)
        self.driver.swipe_to_back()
        time.sleep(1)

    def teardown(self):
        Log.info('teardown')
        self.driver.stop_app(self.app_package)
        self.generate_reports()
