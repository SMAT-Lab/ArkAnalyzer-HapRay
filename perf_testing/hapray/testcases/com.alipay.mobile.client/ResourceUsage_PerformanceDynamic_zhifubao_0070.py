# coding: utf-8
import os
import time

from devicetest.core.test_case import Step
from hypium import BY

from hapray.core.common.common_utils import CommonUtils
from hapray.core.perf_testcase import PerfTestCase, Log


class ResourceUsage_PerformanceDynamic_zhifubao_0070(PerfTestCase):

    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(self.TAG, controllers)

        self._app_package = 'com.alipay.mobile.client'
        self._app_name = '支付宝'
        self._steps = [
            {
                "name": "step1",
                "description": "1. 支付宝 点击视频播放，拖滑切换视频5次，每次间隔10s"
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
        self.driver.swipe_to_home()

        Step('启动被测应用')
        # 定义步骤1的动作函数：启动支付宝
        # TODO: 冷启动支付宝，**进入多任务界面**
        self.driver.start_app(self.app_package)
        self.driver.wait(5)

        def step1(driver):
            Step('1. 支付宝 点击视频播放，拖滑切换视频5次，每次间隔10s')
            time_start = time.time()
            component = driver.find_component(BY.type('Text').text('视频'))
            driver.touch(component)
            time.sleep(2)
            for _ in range(5):
                # driver.slide((604, 2020), (604, 930), slide_time=0.3)  # 从上往下滑   ## TODO swipe_OH()
                CommonUtils.swipes_up_load(driver, swip_num=1, sleep=10, timeout=300)
                # driver.wait(1)  # TODO driver.wait 和 sleep 有什么区别
                # driver.drag((604, 2020), (604, 930), drag_time=0.5) # TODO drag 和 slide 区别？
                time.sleep(10)
            time.sleep(3)
            time_end = time.time()
            if time_end - time_start < 65:
                time.sleep(65 - (time_end - time_start))

        def finish(driver):
            # 上滑返回桌面
            driver.swipe_to_home()
            time.sleep(1)
        self.execute_performance_step(1, step1, 65)
        finish(self.driver)

    def teardown(self):
        Log.info('teardown')
        self.driver.stop_app(self.app_package)
        self.generate_reports()
