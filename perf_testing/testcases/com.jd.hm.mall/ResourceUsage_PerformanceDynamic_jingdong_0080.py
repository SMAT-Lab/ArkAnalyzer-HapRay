# coding: utf-8
import os
import time

from devicetest.core.test_case import Step
from hypium import BY

from aw.PerfTestCase import PerfTestCase, Log
from aw.common.CommonUtils import CommonUtils


class ResourceUsage_PerformanceDynamic_jingdong_0080(PerfTestCase):

    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(self.TAG, controllers)

        self._app_package = 'com.jd.hm.mall'
        self._app_name = '京东'
        self._steps = [
            {
                "name": "step1",
                "description": "1.京东-搜索商品购物"
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

    def process(self):
        self.driver.swipe_to_home()

        Step('启动京东应用')
        self.driver.start_app(self.app_package)
        self.driver.wait(5)
        time.sleep(3)



        def step1(driver):
            # 点击搜索框
            self.driver.touch((494, 314))
            time.sleep(2)

            # 搜索华为手机
            self.driver.input_text((525, 198),'华为手机')
            self.driver.touch(BY.text('搜索'))
            time.sleep(2)


            Step('搜索结果页浏览，上滑操作')
            CommonUtils.swipes_up_load(self.driver, swip_num=3, sleep=2)
            Step('搜索结果页浏览，下滑操作')
            CommonUtils.swipes_down_load(self.driver, swip_num=5, sleep=2)


        self.execute_step_with_perf(1, step1, 30)



    def teardown(self):
        Log.info('teardown')
        self.driver.stop_app(self.app_package)
        self.make_reports()
