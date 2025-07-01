# coding: utf-8
import os
import time

from devicetest.core.test_case import Step
from hypium import BY

from hapray.core.common.common_utils import CommonUtils
from hapray.core.common.coordinate_adapter import CoordinateAdapter
from hapray.core.perf_testcase import PerfTestCase, Log


class ResourceUsage_PerformanceDynamic_bilibili_1000(PerfTestCase):

    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(self.TAG, controllers)

        self._app_package = 'com.ohos.sceneboard'
        self._start_app_package = 'yylx.danmaku.bili'
        self._app_icon_key = 'AppIcon_Image_yylx.danmaku.biliEntryAbilityentry0_undefined'
        self._app_name = '哔哩哔哩'
        self._steps = [
            {
                "name": "step1",
                "description": "1. 应用冷启动"
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

        self.set_device_redundant_mode()
        self.reboot_device()

    def process(self):
        # self.driver.swipe_to_home()
        self.driver.press_home()
        self.driver.stop_app(self._start_app_package)
        time.sleep(2)
        xhs_icon = self.driver.find_component(BY.key(self._app_icon_key))
        while not xhs_icon:
            CommonUtils.swipes_left_load(self.driver, swip_num=1, sleep=1)
            xhs_icon = self.driver.find_component(
                BY.key(self._app_icon_key))

        def step1(driver):
            Step('1. 应用冷启动')
            driver.touch(xhs_icon)
            time.sleep(5)
            driver.swipe_to_home()

        self.execute_performance_step(1, step1, 10, True)
        # 杀掉进程，等待5s
        self.driver.swipe_to_recent_task()
        time.sleep(1)
        self.driver.touch(CoordinateAdapter.convert_coordinate(
            self.driver,
            x=630,   # 原始x坐标
            y=2459,  # 原始y坐标
            source_width=self.source_screen_width,
            source_height=self.source_screen_height
        ))
        time.sleep(5)

    def teardown(self):
        Log.info('teardown')
        self._app_package = self._start_app_package
        self.generate_reports()
