# !/usr/bin/env python
# coding: utf-8

import os

from devicetest.core.test_case import Step

from hapray.core.common.common_utils import CommonUtils
from hapray.core.perf_testcase import PerfTestCase


class PerformanceDynamic_ComponentReusable_old(PerfTestCase):

    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(self.TAG, controllers)

        self._app_package = 'arkanalyzer.hapray.agent'
        self._app_name = 'HapRay'
        self._test_suite = 'test_suite'
        self._testCase = 'ComponentNoReusableTest'
        self._steps = [
            {
                "name": "step1",
                "description": "上滑5次，每次等待1s;下滑5次，每次等待1s"
            },
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
        # 创建所有必要的目录
        os.makedirs(os.path.join(self.report_path, 'hiperf'), exist_ok=True)
        os.makedirs(os.path.join(self.report_path, 'htrace'), exist_ok=True)

    def teardown(self):
        self.driver.stop_app(self.app_package)
        self.generate_reports()

    def process(self):
        def step1(driver):
            Step('1. 上滑5次，每次等待1s;下滑5次，每次等待1s')
            driver.start_app(package_name=self.app_package, page_name='ExecutorAbility',
                             params=f'--ps testSuite {self._test_suite} --ps testCase {self._testCase}')
            driver.wait(2)
            for _ in range(5):
                CommonUtils.swipes_up_load(driver, 1, 1, 300)

            for _ in range(5):
                CommonUtils.swipes_down_load(driver, 1, 1, 300)

        self.driver.swipe_to_home()
        self.driver.start_app(package_name=self.app_package)
        self.driver.wait(5)  # 增加启动等待时间

        self.execute_performance_step(1, step1, 20)
