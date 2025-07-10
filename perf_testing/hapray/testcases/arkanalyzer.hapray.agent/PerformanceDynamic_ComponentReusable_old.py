# !/usr/bin/env python
# coding: utf-8

from hapray.core.perf_testcase import PerfTestCase


class PerformanceDynamic_ComponentReusable_old(PerfTestCase):

    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(self.TAG, controllers)

        self._app_package = 'arkanalyzer.hapray.agent'
        self._app_name = 'HapRay'
        self._test_suite = 'test_suite'
        self._testCase = 'ComponentNoReusableTest'

    @property
    def app_package(self) -> str:
        return self._app_package

    @property
    def app_name(self) -> str:
        return self._app_name

    def process(self):
        def step1():
            # 1. 上滑5次，每次等待1s;下滑5次，每次等待1s
            self.driver.start_app(package_name=self.app_package, page_name='ExecutorAbility',
                                  params=f'--ps testSuite {self._test_suite} --ps testCase {self._testCase}')
            self.driver.wait(2)
            for _ in range(5):
                self.driver.swipe("UP")
                self.driver.wait(2)
            for _ in range(5):
                self.driver.swipe("DOWN")
                self.driver.wait(2)

        self.driver.start_app(self.app_package)
        self.driver.wait(5)
        for _ in range(5):
            self.driver.swipe("UP")
            self.driver.wait(2)
        for _ in range(5):
            self.driver.swipe("DOWN")
            self.driver.wait(2)
        self.execute_performance_step("组件未复用-list上滑/下滑", 20, step1)
