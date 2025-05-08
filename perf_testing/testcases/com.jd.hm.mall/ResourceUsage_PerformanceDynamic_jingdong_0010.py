# coding: utf-8
import os

from devicetest.core.test_case import Step

from aw.PerfTestCase import PerfTestCase, Log
from aw.common.CommonUtils import CommonUtils


class ResourceUsage_PerformanceDynamic_jingdong_0010(PerfTestCase):

    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(self.TAG, controllers)

        self._app_package = 'com.jd.hm.mall'
        self._app_name = '京东'
        self._steps = [
            {
                "name": "step1",
                "description": "1.京东首页-滑动-应用内操作(同时收集perf和trace数据)"
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
        # 创建所有必要的目录
        os.makedirs(os.path.join(self.report_path, 'hiperf'), exist_ok=True)
        os.makedirs(os.path.join(self.report_path, 'htrace'), exist_ok=True)
        os.makedirs(os.path.join(self.report_path, 'report'), exist_ok=True)

    def process(self):
        self.driver.swipe_to_home()

        Step('启动被测应用')
        self.driver.start_app(self.app_package)
        self.driver.wait(5)

        def step1(driver):
            Step('京东首页上滑操作')
            CommonUtils.swipes_up_load(self.driver, swip_num=5, sleep=2)
            Step('京东首页下滑操作')
            CommonUtils.swipes_down_load(self.driver, swip_num=5, sleep=2)

        self.execute_step_with_perf_and_trace(1, step1, 30)

    def teardown(self):
        Log.info('teardown')
        self.driver.stop_app(self.app_package)
        self.make_reports()
