# coding: utf-8
import os
import time

from devicetest.core.test_case import Step
from hypium import BY

from hapray.core.common.common_utils import CommonUtils
from hapray.core.perf_testcase import PerfTestCase, Log


class ResourceUsage_PerformanceDynamic_bilibili_0020(PerfTestCase):

    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(self.TAG, controllers)
        self._activityName = 'EntryAbility'
        self._app_package = 'yylx.danmaku.bili'
        self._app_name = '哔哩哔哩'
        self._steps = [
            {
                "name": "step1",
                "description": "1. 视频播放30s"
            },
            {
                "name": "step2",
                "description": "2. 视频区评论，上滑10次，下滑10次"
            },
            {
                "name": "step3",
                "description": "3. 全屏播放30s"
            },
            {
                "name": "step4",
                "description": "4. 关闭弹幕，全屏播放30s"
            },
            {
                "name": "step5",
                "description": "5. 长按视频中间，倍速播放30s"
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
            Step('1. 视频播放30s')
            time.sleep(30)

        def step2(driver):
            # 依赖提前关注 EDIFIER漫步者
            Step('2. 视频区评论')
            time_start = time.time()
            # 评论区上滑10次
            for i in range(10):
                # CommonUtils.swipe(driver.device_sn, 703, 2471, 703, 1471)
                CommonUtils.swipe(driver.device_sn, 703, 2271, 703, 1271)  # Mate70 Mate60Pro
                time.sleep(2)

            # 评论区下滑10次
            for i in range(10):
                # CommonUtils.swipe(driver.device_sn, 703, 1471, 703, 2471)
                CommonUtils.swipe(driver.device_sn, 703, 2271, 703, 1271)  # Mate70 Mate60Pro
                time.sleep(2)
            time_end = time.time()
            if time_end - time_start < 60:
                time.sleep(60 - (time_end - time_start))

        def step3(driver):
            Step('3. 全屏播放30s')
            # 1. 点击视频中间，等待1s
            driver.touch((600, 500))
            time.sleep(1)

            # 2. 点击全屏按钮，等待1s
            # driver.touch((1232, 770))
            driver.touch((1144, 709))  # Mate70 Mate60Pro
            time.sleep(1)

            # 3. 全屏播放30s
            time.sleep(30)

        def step4(driver):
            Step('4. 关闭弹幕，全屏播放30s')

            # 1. 点击视频中间，等待1s
            driver.touch((1416, 680))
            time.sleep(1)

            # 2. 点击关闭弹幕，等待1s
            # driver.touch((557, 1210))
            driver.touch((526, 1125))  # Mate70 Mate60Pro
            time.sleep(1)

            # 3. 全屏播放30s
            time.sleep(30)

        def step5(driver):
            Step('5. 长按视频中间，倍速播放30s')
            time_start = time.time()
            # 1. 长按视频中间
            driver.long_click((1416, 680), press_time=30)
            time.sleep(1)
            time_end = time.time()
            if time_end - time_start < 30:
                time.sleep(30 - (time_end - time_start))

        Step('启动被测应用')
        self.driver.start_app(self.app_package, self._activityName)
        self.driver.wait(5)

        # 点击“我的”页面
        self.driver.touch(BY.text('我的'))
        time.sleep(2)

        # 点击“我的收藏”
        self.driver.touch(BY.text('我的收藏'))
        time.sleep(2)

        # 点击播放”航拍中国第一季“
        self.driver.touch(BY.text('航拍中国 第一季'))
        time.sleep(2)

        # 暂停播放
        self.driver.touch((600, 500))
        time.sleep(1)
        # self.driver.touch((68, 776))
        self.driver.touch((71, 709))  # Mate70 Mate60Pro
        time.sleep(1)

        # 点击到视频00分00秒
        # self.driver.touch((182, 781))
        # self.driver.touch((169, 709)) # Mate70
        self.driver.touch((169, 747))  # Mate60Pro
        time.sleep(1)

        # 点击视频播放
        # self.driver.touch((68, 776))
        self.driver.touch((71, 709))  # Mate70 Mate60Pro
        time.sleep(1)

        # 视频播放30s
        self.execute_performance_step(1, step1, 30)
        # 点击评论
        self.driver.touch(BY.text('评论'))
        time.sleep(3)
        self.execute_performance_step(2, step2, 60)
        self.execute_performance_step(3, step3, 40)
        self.execute_performance_step(4, step4, 40)
        self.execute_performance_step(5, step5, 30)

    def teardown(self):
        Log.info('teardown')
        self.driver.stop_app(self.app_package)
        self.generate_reports()
