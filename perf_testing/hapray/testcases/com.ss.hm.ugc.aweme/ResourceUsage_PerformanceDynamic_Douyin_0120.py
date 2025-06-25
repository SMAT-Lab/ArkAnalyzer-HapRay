# coding: utf-8
import os
import time

from devicetest.core.test_case import Step
from hypium import BY

from hapray.core.perf_testcase import PerfTestCase, Log
from hapray.core.common.common_utils import CommonUtils
from hapray.core.common.coordinate_adapter import CoordinateAdapter


class ResourceUsage_PerformanceDynamic_Douyin_0120(PerfTestCase):

    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(self.TAG, controllers)

        self._app_package = 'com.ss.hm.ugc.aweme'
        self._app_name = '抖音'
        self._steps = [
            {
                "name": "step1",
                "description": "1. 点击进入'与辉同行'直播间，等待10s退出"
            },
            {
                "name": "step2",
                "description": "2. 直播间上滑切换5次，间隔10s"
            },
            {
                "name": "step3",
                "description": "3. 直播间下滑切换5次，间隔10s"
            },
            {
                "name": "step4",
                "description": "4. 点击直播间礼物，礼物界面滑动5次，间隔2s"
            },
            {
                "name": "step5",
                "description": "5. 点击直播间右上角在线观众，列表滑动5次，间隔2s"
            },
            {
                "name": "step6",
                "description": "6. 点击直播间小黄车展开，商品列表上滑下滑10次，间隔2s"
            },
            {
                "name": "step7",
                "description": "7. 点击进入任意商品详情，详情页上下滑动10次，间隔2s"
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
        Step('启动被测应用')
        self.driver.wake_up_display()
        time.sleep(1)
        self.driver.swipe_to_home()
        time.sleep(1)
        # 1. 打开抖音，等待 5s
        self.driver.start_app(self.app_package)
        self.driver.wait(2)  # 等待应用启动
        time.sleep(3)
        # 2. 点击进入“关注”tab页
        component_follow = self.driver.find_component(BY.id('home-top-tab-text-homepage_follow'))
        self.driver.touch(component_follow)
        time.sleep(3)

        component = self.driver.find_component(BY.text('与辉同行'))

        def step1(driver):
            Step('1. 点击进入"与辉同行"直播间，等待10s退出')
            driver.touch(component)
            time.sleep(10)

            driver.swipe_to_back()
            time.sleep(5)

        def step2(driver):
            Step('2. 直播间上滑切换5次，间隔10s')
            driver.touch(component)
            time.sleep(2)

            for _ in range(5):
                CommonUtils.swipe(driver.device_sn, 630, 2300, 630, 1350, 300)
                time.sleep(10)

        def step3(driver):
            Step('3. 直播间下滑切换5次，间隔10s')
            for _ in range(5):
                CommonUtils.swipe(driver.device_sn, 630, 1500, 630, 2450, 300)
                time.sleep(10)

        def step4(driver):
            Step('4. 点击直播间礼物，礼物界面滑动5次，间隔2s')
            driver.touch(CoordinateAdapter.convert_coordinate(
                self.driver,
                x=1038,  # 原始x坐标
                y=2634,  # 原始y坐标
                source_width=self.source_screen_width,
                source_height=self.source_screen_height))
            time.sleep(3)

            for _ in range(5):
                CommonUtils.swipe(driver.device_sn, 630, 2300, 630, 1350, 300)
                time.sleep(2)

        def step5(driver):
            Step('5. 点击直播间右上角在线观众，列表滑动5次，间隔2s')
            driver.touch(CoordinateAdapter.convert_coordinate(
                self.driver,
                x=1095,  # 原始x坐标
                y=220,  # 原始y坐标
                source_width=self.source_screen_width,
                source_height=self.source_screen_height))
            time.sleep(3)

            for _ in range(5):
                CommonUtils.swipe(driver.device_sn, 630, 2300, 630, 1350, 300)
                time.sleep(2)

        def step6(driver):
            Step('6. 点击直播间小黄车展开，商品列表上滑下滑10次，间隔2s')
            driver.touch(CoordinateAdapter.convert_coordinate(
                self.driver,
                x=730,  # 原始x坐标
                y=2634,  # 原始y坐标
                source_width=self.source_screen_width,
                source_height=self.source_screen_height))
            time.sleep(3)

            for _ in range(10):
                CommonUtils.swipes_up_load(driver, 1, 2, 300)

            for _ in range(10):
                CommonUtils.swipes_down_load(driver, 1, 2, 300)

        def step7(driver):
            Step('7. 点击进入任意商品详情，详情页上下滑动10次，间隔2s')
            driver.touch(CoordinateAdapter.convert_coordinate(
                self.driver,
                x=259,  # 原始x坐标
                y=1755,  # 原始y坐标
                source_width=self.source_screen_width,
                source_height=self.source_screen_height))
            time.sleep(3)

            for _ in range(10):
                CommonUtils.swipes_up_load(driver, 1, 2, 300)

            for _ in range(10):
                CommonUtils.swipes_down_load(driver, 1, 2, 300)

        def finish(driver):
            driver.swipe_to_home()

        self.execute_performance_step(1, step1, 60)
        self.execute_performance_step(2, step2, 60)
        self.execute_performance_step(3, step3, 60)
        self.execute_performance_step(4, step4, 20)
        self.driver.touch(CoordinateAdapter.convert_coordinate(
            self.driver,
            x=500,  # 原始x坐标
            y=700,  # 原始y坐标
            source_width=self.source_screen_width,
            source_height=self.source_screen_height))
        time.sleep(1)
        self.execute_performance_step(5, step5, 20)
        self.driver.touch(CoordinateAdapter.convert_coordinate(
            self.driver,
            x=500,  # 原始x坐标
            y=700,  # 原始y坐标
            source_width=self.source_screen_width,
            source_height=self.source_screen_height))
        time.sleep(1)
        self.execute_performance_step(6, step6, 30)
        self.execute_performance_step(7, step7, 30)

        time.sleep(2)
        finish(self.driver)

    def teardown(self):
        Log.info('teardown')
        self.driver.stop_app(self.app_package)
        self.generate_reports()
