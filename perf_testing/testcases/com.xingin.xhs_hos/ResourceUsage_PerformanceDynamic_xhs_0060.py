# coding: utf-8
import os
import time

from devicetest.core.test_case import Step
from devicetest.log.logger import DeviceTestLog as Log
from hypium.advance.perf.driver_perf.uiexplorer_perf import UiExplorerPerf
from hypium import BY

from aw.PerfTestCase import PerfTestCase
from aw.common.CommonUtils import CommonUtils


class ResourceUsage_PerformanceDynamic_xhs_0060(PerfTestCase):

    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(self.TAG, controllers)
        self.driver = UiExplorerPerf(self.device1)
        self._app_package = 'com.xingin.xhs_hos'
        self._app_name = '小红书'
        self._steps = [
            {
                "name": "step1",
                "description": "1. 点击进入、退出直播间操作5次"
            },
            {
                "name": "step2",
                "description": "2. 进入我的收藏，观看1个直播，直播观看30s"
            },
            {
                "name": "step3",
                "description": "3. 直播间点击购物车，并在购物车商品列表页面上下滑动5次"
            },
            {
                "name": "step4",
                "description": "4. 点击购物车跳转到购物车列表页面并上下滑动5次"
            },
            {
                "name": "step5",
                "description": "5. 点击购物车列表第一个商品，进入商品详情页面上下滑动5次"
            }

        ]

    @property
    def report_path(self) -> str:
        return self.get_case_report_path()

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

        Step('启动被测应用')
        self.driver.start_app(self.app_package)
        self.driver.wait(5)

        # 拖拽显示隐藏tab栏
        CommonUtils.swipes_down_load(self.driver, swip_num=1, sleep=5)

        def step1(driver):
            Step('点击进入、退出直播间操作5次')

            # 1. 点击顶部隐藏tab页进入直播页，等待2s
            driver.touch(BY.text('直播'))
            time.sleep(2)

            for i in range(5):
                # 2. 点击进入左上角第一个直播间，等待2s
                driver.touch((350, 1010))
                time.sleep(2)

                # 3. 左滑返回直播列表页面, 等待2s
                driver.swipe_to_back()
                time.sleep(2)

        def step2(driver):
            # 依赖提前关注 EDIFIER漫步者
            Step('进入我的收藏，观看1个直播，直播观看30s')

            driver.touch(BY.text('我'))
            time.sleep(1)

            driver.touch(BY.text('关注'))
            time.sleep(1)

            driver.touch(BY.text('EDIFIER漫步者'))
            time.sleep(1)

            # 1. 点击直播左上角第一个直播，等待30s
            driver.touch((197, 520))
            time.sleep(30)

        def step3(driver):
            Step('直播间点击购物车，并在购物车商品列表页面上下滑动5次')
            # 1. 点击直播间购物车图标，等待2s
            driver.touch((1187, 2685))
            time.sleep(1)

            # 直播间商品列表上滑下滑
            for i in range(5):
                # 2. 直播间商品列表上滑，等待2s
                CommonUtils.swipe(driver.device_sn, 630, 2520, 630, 1570, 300)
                time.sleep(2)

                # 3. 直播间商品列表下滑，等待2s
                CommonUtils.swipe(driver.device_sn, 630, 1570, 630, 2520, 300)
                time.sleep(2)

        def step4(driver):
            Step('点击购物车跳转到购物车列表页面并上下滑动5次')

            # 1. 点击直播间购物车图标，等待2s
            driver.touch((1060, 720))
            time.sleep(1)

            # 购物车商品列表上滑5次
            for i in range(5):
                # 2. 购物车商品列表上滑5次，等待2s
                CommonUtils.swipe(driver.device_sn, 630, 2520, 630, 1570, 300)
                time.sleep(2)

            # 购物车商品列表下滑5次
            for i in range(5):
                # 3. 购物车商品列表下滑5次，等待2s
                CommonUtils.swipe(driver.device_sn, 630, 1570, 630, 2520, 300)
                time.sleep(2)

        def step5(driver):
            Step('点击购物车列表第一个商品，进入商品详情页面上下滑动5次')
            # 1. 点击购物车列表第一个商品，进入商品详情，等待1s
            driver.touch((320, 630))
            time.sleep(1)

            # 购物车商品列表上滑5次
            for i in range(5):
                # 2. 购物车商品列表上滑5次，等待2s
                CommonUtils.swipe(driver.device_sn, 630, 2520, 630, 1570, 300)
                time.sleep(2)

            # 购物车商品列表下滑5次
            for i in range(5):
                # 3. 购物车商品列表下滑5次，等待2s
                CommonUtils.swipe(driver.device_sn, 630, 1570, 630, 2520, 300)
                time.sleep(2)

        self.execute_step_with_perf(1, step1, 10)
        self.execute_step_with_perf(2, step2, 30)
        self.execute_step_with_perf(3, step3, 40)
        self.execute_step_with_perf(4, step4, 40)
        self.execute_step_with_perf(5, step5, 40)

    def teardown(self):
        Log.info('teardown')
        self.driver.stop_app(self.app_package)
        self.make_reports()
