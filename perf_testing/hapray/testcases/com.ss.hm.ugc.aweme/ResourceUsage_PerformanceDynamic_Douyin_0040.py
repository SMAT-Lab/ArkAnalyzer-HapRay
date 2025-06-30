# coding: utf-8
import os
import time

from devicetest.core.test_case import Step
from hypium import BY

from hapray.core.perf_testcase import PerfTestCase, Log
from hapray.core.common.common_utils import CommonUtils


class ResourceUsage_PerformanceDynamic_Douyin_0040(PerfTestCase):

    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(self.TAG, controllers)

        self._app_package = 'com.ss.hm.ugc.aweme'
        self._app_name = '抖音'
        self._steps = [
            {
                "name": "step1",
                "description": "1. 抖音点击直播页签"
            },
            {
                "name": "step2",
                "description": "2. 直播页签上滑5次，每次等待10s"
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
            Step('1. 抖音点击直播页签')
            component = driver.find_component(BY.text('直播'))
            driver.touch(component)
            time.sleep(2)

        def step2(driver):
            Step('2. 直播页签上滑5次，每次等待10s')
            for _ in range(5):
                CommonUtils.swipes_up_load(driver, 1, 10, 300)

        def finish(driver):
            driver.swipe_to_back()
            driver.swipe_to_home()

        start(self.driver)
        self.execute_performance_step(1, step1, 30)
        self.execute_performance_step(2, step2, 60)
        finish(self.driver)

    def teardown(self):
        Log.info('teardown')
        self.driver.stop_app(self.app_package)
        self.generate_reports()
