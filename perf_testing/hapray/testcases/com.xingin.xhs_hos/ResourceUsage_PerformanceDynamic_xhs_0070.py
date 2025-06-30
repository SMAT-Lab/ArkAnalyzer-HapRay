# coding: utf-8
import os
import time

from devicetest.core.test_case import Step
from hypium import BY

from hapray.core.common.common_utils import CommonUtils
from hapray.core.common.coordinate_adapter import CoordinateAdapter
from hapray.core.perf_testcase import PerfTestCase, Log


class ResourceUsage_PerformanceDynamic_xhs_0070(PerfTestCase):

    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(self.TAG, controllers)

        self._app_package = 'com.xingin.xhs_hos'
        self._app_name = '小红书'
        self._steps = [
            {
                "name": "step1",
                "description": "1. 动态图片启动退出"
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

        # 拖拽显示隐藏tab栏
        CommonUtils.swipes_down_load(self.driver, swip_num=1, sleep=5)

        # 点击进入视频页
        self.driver.touch(BY.text('视频'))
        time.sleep(2)
        # 点击进入任意视频
        self.driver.touch(CoordinateAdapter.convert_coordinate(
            self.driver,
            x=350,  # 原始x坐标
            y=1010,  # 原始y坐标
            source_width=self.source_screen_width,
            source_height=self.source_screen_height
        ))
        time.sleep(2)
        # 点击评论 输入框
        self.driver.touch(CoordinateAdapter.convert_coordinate(
            self.driver,
            x=1124,  # 原始x坐标
            y=2552,  # 原始y坐标
            source_width=self.source_screen_width,
            source_height=self.source_screen_height
        ))
        time.sleep(1)
        # 点击相册图标，调起图库picker
        self.driver.touch(CoordinateAdapter.convert_coordinate(
            self.driver,
            x=1137,  # 原始x坐标
            y=2538,  # 原始y坐标
            source_width=self.source_screen_width,
            source_height=self.source_screen_height
        ))
        time.sleep(1)

        # 点击任一动态图片，在动态图片大图界面，上滑退出小红书，再启动，操作5次
        def step1(driver):
            Step('1. 动态图片启动退出')
            time_start = time.time()

            # 点击第一排第四张（最后一张）动态图片
            self.driver.touch(CoordinateAdapter.convert_coordinate(
                self.driver,
                x=1152,  # 原始x坐标
                y=1031,  # 原始y坐标
                source_width=self.source_screen_width,
                source_height=self.source_screen_height
            ))
            time.sleep(1)

            # 上滑退出小红书，再启动，操作5次，观察启动/退出动效是否流畅
            for i in range(5):
                driver.swipe_to_home()
                time.sleep(2)

                driver.touch(BY.key("AppIcon_Image_com.xingin.xhs_hosEntryAbilityredbook0_undefined"))
                time.sleep(2)
            time_end = time.time()
            if time_end - time_start < 30:
                time.sleep(30 - (time_end - time_start))

        self.execute_performance_step(1, step1, 30)

    def teardown(self):
        Log.info('teardown')
        self.driver.stop_app(self.app_package)
        self.generate_reports()
