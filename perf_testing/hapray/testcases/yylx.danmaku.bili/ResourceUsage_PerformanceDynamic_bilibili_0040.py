# coding: utf-8
import os
import time

from devicetest.core.test_case import Step
from hypium import BY

from hapray.core.common.common_utils import CommonUtils
from hapray.core.perf_testcase import PerfTestCase, Log


class ResourceUsage_PerformanceDynamic_bilibili_0040(PerfTestCase):

    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(self.TAG, controllers)
        self._activityName = 'EntryAbility'
        self._app_package = 'yylx.danmaku.bili'
        self._app_name = '哔哩哔哩'
        self._steps = [
            {
                "name": "step1",
                "description": "1. 搜索框输入“航拍中国“ （键盘输入15次，每0.5s点击一次，15s），并且点击”航拍中国“（1s），点击搜索（1s）"
            }
        ]

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
        def step1(driver):
            Step('1. 搜索框输入“航拍中国“ （键盘输入15次，每0.5s点击一次，15s），并且点击”航拍中国“（1s），点击搜索（1s）')

            # 点击H
            self.driver.touch((761, 2129))  # Mate60 Pro
            time.sleep(0.5)

            # 点击A
            self.driver.touch((148, 2125))  # Mate60 Pro
            time.sleep(0.5)

            # 点击N
            self.driver.touch((853, 2327))  # Mate60 Pro
            time.sleep(0.5)

            # 点击G
            self.driver.touch((636, 2144))  # Mate60 Pro
            time.sleep(0.5)

            # 点击P
            self.driver.touch((1192, 1950))  # Mate60 Pro
            time.sleep(0.5)

            # 点击A
            self.driver.touch((156, 2121))  # Mate60 Pro
            time.sleep(0.5)

            # 点击I
            self.driver.touch((918, 1954))  # Mate60 Pro
            time.sleep(0.5)

            # 点击Z
            self.driver.touch((270, 2293))  # Mate60 Pro
            time.sleep(0.5)

            # 点击H
            self.driver.touch((758, 2121))  # Mate60 Pro
            time.sleep(0.5)

            # 点击O
            self.driver.touch((1062, 1942))  # Mate60 Pro
            time.sleep(0.5)

            # 点击N
            self.driver.touch((864, 2316))  # Mate60 Pro
            time.sleep(0.5)

            # 点击G
            self.driver.touch((643, 2140))  # Mate60 Pro
            time.sleep(0.5)

            # 点击G
            self.driver.touch((628, 2137))  # Mate60 Pro
            time.sleep(0.5)

            # 点击U
            self.driver.touch((830, 1958))  # Mate60 Pro
            time.sleep(0.5)

            # 点击O
            self.driver.touch((1059, 1961))  # Mate60 Pro
            time.sleep(0.5)

            time.sleep(7.5)

            # 点击航拍中国
            self.driver.touch(BY.text('航拍中国'))
            time.sleep(1)

            # 点击搜索
            self.driver.touch(BY.text('搜索'))
            time.sleep(4)

        Step('启动被测应用')
        self.driver.start_app(self.app_package, self._activityName)
        self.driver.wait(5)
        # 点击搜索框，停留2s
        self.driver.touch((657, 185))  # Mate60 Pro
        self.driver.wait(0.5)
        time.sleep(2)

        # 搜索框输入“航拍中国“ （键盘输入15次，每0.5s点击一次，15s），并且点击”航拍中国“（1s），点击搜索（1s）
        self.execute_performance_step(1, step1, 20)

        Step('搜索结果页上滑3次：')
        CommonUtils.swipes_up_load(self.driver, swip_num=3, sleep=2)

        # 侧滑3次返回哔哩哔哩首页
        for i in range(3):
            self.driver.swipe_to_back()
            time.sleep(1)

    def teardown(self):
        Log.info('teardown')
        self.driver.stop_app(self.app_package)
        self.generate_reports()
