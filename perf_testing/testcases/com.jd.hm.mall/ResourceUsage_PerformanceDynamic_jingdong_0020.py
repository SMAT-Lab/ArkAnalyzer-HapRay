# coding: utf-8
import os
import time

from devicetest.core.test_case import Step
from hypium import BY

from aw.PerfTestCase import PerfTestCase, Log
from aw.common.CommonUtils import CommonUtils


class ResourceUsage_PerformanceDynamic_jingdong_0020(PerfTestCase):

    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(self.TAG, controllers)

        self._app_package = 'com.jd.hm.mall'
        self._app_name = '京东'
        self._steps = [
            {
                "name": "step1",
                "description": "1.京东新品页面-滑动10次，上滑5次，下滑5次"
            },
            {
                "name": "step2",
                "description": "2.京东商品详情页-向上滑动3次"
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
        # 通过相对位置点击控件
        self.driver.touch(BY.text('新品'))
        self.driver.wait(0.5)


        def step1(driver):
            Step('京东新品页上滑操作')
            CommonUtils.swipes_up_load(self.driver, swip_num=5, sleep=2)
            Step('京东新品页下滑操作')
            CommonUtils.swipes_down_load(self.driver, swip_num=5, sleep=2)

        self.execute_step_with_perf(1, step1, 30)

        # 返回首页
        self.driver.swipe_to_back()
        time.sleep(2)

        # 点击我的
        self.driver.touch(BY.text('我的'))
        time.sleep(2)

        # 选择收藏商品
        self.driver.touch(BY.text('商品收藏'))
        time.sleep(2)

        # 点击收藏页第一个商品
        self.driver.touch((256,980))
        time.sleep(2)


        def step2(driver):
            Step('京东新品页上滑操作')
            CommonUtils.swipes_up_load(self.driver, swip_num=3, sleep=2)

        self.execute_step_with_perf(2, step2, 10)


    def teardown(self):
        Log.info('teardown')
        self.driver.stop_app(self.app_package)
        self.make_reports()
