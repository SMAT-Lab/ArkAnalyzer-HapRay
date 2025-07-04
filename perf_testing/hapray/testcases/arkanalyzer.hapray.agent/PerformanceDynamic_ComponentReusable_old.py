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

    def process(self):
        def step1():
            # 1. 上滑5次，每次等待1s;下滑5次，每次等待1s
            self.driver.start_app(package_name=self.app_package, page_name='ExecutorAbility',
                                  params=f'--ps testSuite {self._test_suite} --ps testCase {self._testCase}')
            self.driver.wait(2)
            self.swipes_up(5, 1, 300)
            self.swipes_down(5, 1, 300)

        self.start_app()
        self.execute_performance_step(1, step1, 20)
