# coding: utf-8
import os
import time

from devicetest.core.test_case import Step
from hypium import BY

from hapray.core.PerfTestCase import PerfTestCase, Log
from hapray.core.common.CommonUtils import CommonUtils


class ResourceUsage_PerformanceDynamic_xhs_0030(PerfTestCase):

    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(self.TAG, controllers)

        self._app_package = 'com.xingin.xhs_hos'
        self._app_name = '小红书'
        self._steps = [
            {
                "name": "step1",
                "description": "1. 浏览收藏图片左滑5次"
            },
            {
                "name": "step2",
                "description": "2. 点赞、取消点赞3次"
            },
            {
                "name": "step3",
                "description": "3. 双指捏合放大、缩小3次"
            },
            {
                "name": "step4",
                "description": "4. 查看评论，上下滑3次"
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
        # 点击收藏的图片链接“100件温暖幸福的小事（3）”
        # self.driver.touch(330, 2057)
        self.driver.touch((308, 1942))  # Mate70 Mate60Pro
        time.sleep(1)

        def step1(driver):
            Step('1. 浏览收藏图片左滑5次')
            # 左滑5次，停留2s
            for i in range(5):
                CommonUtils.swipes_left_load(driver, 1, 2, 300)

        def step2(driver):
            Step('2. 点赞、取消点赞3次')
            for i in range(5):
                # driver.touch((550, 2630))
                driver.touch((579, 2525)) # Mate60Pro  Mate70
                time.sleep(1)
                # driver.touch((550, 2630))
                driver.touch((579, 2525)) # Mate60Pro  Mate70
                time.sleep(1)

        def step3(driver):
            Step('3. 双指捏合放大、缩小2次')
            for i in range(2):
                driver._two_finger_swipe((820, 1040), (480, 1450), (1130, 720), (180, 1850))
                time.sleep(1)
                driver._two_finger_swipe((1130, 720), (180, 1850), (820, 1040), (480, 1450))
                time.sleep(1)

        def step4(driver):
            Step('4. 查看评论，上下滑3次')
            # 点击评论
            # driver.touch((1090, 2620))
            driver.touch((1071, 2538))  # Mate60Pro Mate70
            time.sleep(2)

            # 上滑3次，停留2s
            for i in range(3):
                CommonUtils.swipes_up_load(driver, 1, 2, 300)

            # 下滑3次，停留2s
            for i in range(3):
                CommonUtils.swipes_down_load(driver, 1, 2, 300)


        self.execute_step_with_perf_and_trace(1, step1, 10)
        self.execute_step_with_perf_and_trace(2, step2, 10)
        self.execute_step_with_perf_and_trace(3, step3, 10)
        self.execute_step_with_perf_and_trace(4, step4, 20)

    def teardown(self):
        Log.info('teardown')
        self.driver.stop_app(self.app_package)
        self.make_reports()
