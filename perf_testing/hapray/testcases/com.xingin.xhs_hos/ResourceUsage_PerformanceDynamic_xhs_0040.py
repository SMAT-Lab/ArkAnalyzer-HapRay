# coding: utf-8
import os
import time

from devicetest.core.test_case import Step
from hypium import BY

from hapray.core.PerfTestCase import PerfTestCase, Log


class ResourceUsage_PerformanceDynamic_xhs_0040(PerfTestCase):

    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(self.TAG, controllers)

        self._app_package = 'com.xingin.xhs_hos'
        self._app_name = '小红书'
        self._steps = [
            {
                "name": "step1",
                "description": "1. 观看长视频"
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
        os.makedirs(os.path.join(self.report_path, 'htrace'), exist_ok=True)

    def process(self):
        self.driver.swipe_to_home()

        Step('启动被测应用')
        self.driver.start_app(self.app_package)
        self.driver.wait(5)

        # 首页点击 ”我“
        self.driver.touch(BY.text('我'))
        time.sleep(1)
        # ”我“ 页面点击“收藏”
        self.driver.touch(BY.text('收藏'))
        time.sleep(1)

        def step1(driver):
            Step('点击收藏的视频链接“一口气看完历史上最荒唐的王朝北齐！”，观看30s')

            # 1. 点击顶部隐藏tab页进入直播页，等待2s
            # driver.touch((950, 2126))
            driver.touch((941, 1970)) # Mate70 Mate60Pro
            time.sleep(30)

        self.execute_step_with_perf_and_trace(1, step1, 30)
        self.driver.swipe_to_back()
        time.sleep(1)

    def teardown(self):
        Log.info('teardown')
        self.driver.stop_app(self.app_package)
        self.make_reports()
