# coding: utf-8
import os
import time

from devicetest.core.test_case import Step
from hypium import BY

from aw.PerfTestCase import PerfTestCase, Log
from aw.common.CommonUtils import CommonUtils


class ResourceUsage_PerformanceDynamic_zhifubao_0080(PerfTestCase):

    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(self.TAG, controllers)

        self._app_package = 'com.alipay.mobile.client'
        self._app_name = '支付宝'
        self._steps = [
            {
                "name": "step1",
                "description": "1. 领饲料，上下拖滑3次，间隔2s"
            },
            {
                "name": "step2",
                "description": "2. 去捐蛋，上下拖滑1次，间隔2s"
            },
            {
                "name": "step3",
                "description": "3. 芭芭农场，领肥料，上下拖滑3次，间隔2s"
            },
            {
                "name": "step4",
                "description": "4. 跳转至蚂蚁森林，点击奖励，上下拖滑3次，间隔2s"
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
        # 搜索 蚂蚁庄园 ，进入该小程序
        self.driver.touch((599, 245))
        time.sleep(3)
        self.driver.input_text((BY.type('SearchField')), '蚂蚁庄园')
        time.sleep(3)
        self.driver.touch(BY.type('Button').text('搜索'))
        time.sleep(5)
        self.driver.touch((387, 628))
        time.sleep(5)

        def step1(driver):
            Step('1. 领饲料，上下拖滑3次，间隔2s')
            # 领饲料
            # self.driver.touch(BY.text('领饲料')) 点不到
            # self.driver.touch((337, 2619))
            self.driver.touch((337, 2500))  # Mate60Pro
            time.sleep(2)
            for i in range(3):
                CommonUtils.swipe(driver.device_sn, 625, 2500, 625, 2100, 300)
                time.sleep(2)
            for i in range(3):
                CommonUtils.swipe(driver.device_sn, 625, 2100, 625, 2500, 300)
                time.sleep(2)
            time.sleep(3)

        def step2(driver):
            Step('2. 去捐蛋，上下拖滑1次，间隔2s')
            # self.driver.touch(BY.text('去捐蛋'))
            # self.driver.touch((780, 2619))
            self.driver.touch((780, 2500)) # Mate60Pro
            time.sleep(2)
            CommonUtils.swipe(driver.device_sn, 625, 2500, 625, 1550, 300)
            time.sleep(2)
            CommonUtils.swipe(driver.device_sn, 625, 1550, 625, 2500, 300)
            time.sleep(2)


        def step3(driver):
            Step('3. 芭芭农场，领肥料，上下拖滑3次，间隔2s')
            # 点左边树苗
            self.driver.touch((56, 1515))
            time.sleep(5)
            # self.driver.touch(BY.text('领肥料'))
            # self.driver.touch((1125, 2369))
            self.driver.touch((1125, 2200))  # Mate60Pro
            time.sleep(5)
            for i in range(3):
                CommonUtils.swipe(driver.device_sn, 625, 2500, 625, 2100, 300)
                time.sleep(2)
            for i in range(3):
                CommonUtils.swipe(driver.device_sn, 625, 2100, 625, 2500, 300)
                time.sleep(2)

        def step4(driver):
            Step('4. 跳转至蚂蚁森林，点击奖励，上下拖滑3次，间隔2s')
            # 点击右侧树苗
            driver.touch((910, 1198))
            time.sleep(3)
            # self.driver.touch(BY.text('奖励'))
            # driver.touch((502, 1898))
            driver.touch((520, 1820)) # Mate60Pro
            time.sleep(3)
            for i in range(3):
                CommonUtils.swipe(driver.device_sn, 625, 2500, 625, 2100, 300)
                time.sleep(2)
            for i in range(3):
                CommonUtils.swipe(driver.device_sn, 625, 2100, 625, 2500, 300)
                time.sleep(2)

        self.execute_step_with_perf_and_trace(1, step1, 20)
        time.sleep(10)
        # 点击 x 图标返回上一页
        self.driver.touch((1198, 903))
        time.sleep(2)

        self.execute_step_with_perf_and_trace(2, step2, 10)
        # 点击 x 图标返回上一页
        self.driver.touch((1198, 903))
        time.sleep(2)

        self.execute_step_with_perf_and_trace(3, step3, 30)
        time.sleep(10)
        # 点击右上角
        self.driver.touch((1184, 213))
        time.sleep(2)
        # 点击左上角返回蚂蚁庄园
        self.driver.touch((387, 628))
        time.sleep(2)

        self.execute_step_with_perf_and_trace(4, step4, 30)
        # 上滑返回桌面
        self.driver.swipe_to_home()

    def teardown(self):
        Log.info('teardown')
        self.driver.stop_app(self.app_package)
        self.make_reports()
