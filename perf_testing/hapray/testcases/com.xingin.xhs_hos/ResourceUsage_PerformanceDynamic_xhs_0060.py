# coding: utf-8
import os
import time

from devicetest.core.test_case import Step
from hypium import BY

from hapray.core.common.common_utils import CommonUtils
from hapray.core.common.coordinate_adapter import CoordinateAdapter
from hapray.core.perf_testcase import PerfTestCase, Log


class ResourceUsage_PerformanceDynamic_xhs_0060(PerfTestCase):

    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(self.TAG, controllers)

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
        # 原始采集设备的屏幕尺寸（Mate 60 Pro）
        self.source_screen_width = 1260
        self.source_screen_height = 2720
        self.swipe_p1 = CoordinateAdapter.convert_coordinate(
            self.driver,
            x=630,  # 原始x坐标
            y=2320,  # 原始y坐标
            source_width=self.source_screen_width,
            source_height=self.source_screen_height
        )
        self.swipe_p2 = CoordinateAdapter.convert_coordinate(
            self.driver,
            x=630,  # 原始x坐标
            y=1370,  # 原始y坐标
            source_width=self.source_screen_width,
            source_height=self.source_screen_height
        )

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
                driver.touch(CoordinateAdapter.convert_coordinate(
                    driver,
                    x=350,  # 原始x坐标
                    y=1010,  # 原始y坐标
                    source_width=self.source_screen_width,
                    source_height=self.source_screen_height
                ))
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
            driver.touch(CoordinateAdapter.convert_coordinate(
                driver,
                x=197,  # 原始x坐标
                y=520,  # 原始y坐标
                source_width=self.source_screen_width,
                source_height=self.source_screen_height
            ))
            time.sleep(30)

        def step3(driver):
            Step('直播间点击购物车，并在购物车商品列表页面上下滑动5次')
            # 1. 点击直播间购物车图标，等待2s
            driver.touch(CoordinateAdapter.convert_coordinate(
                driver,
                x=1112,  # 原始x坐标
                y=2559,  # 原始y坐标
                source_width=self.source_screen_width,
                source_height=self.source_screen_height
            ))
            time.sleep(1)

            # 直播间商品列表上滑下滑
            for i in range(5):
                # 2. 直播间商品列表上滑，等待2s
                CommonUtils.swipe(driver.device_sn, self.swipe_p1[0], self.swipe_p1[1], self.swipe_p2[0],
                                  self.swipe_p2[1], 300)
                time.sleep(2)

                # 3. 直播间商品列表下滑，等待2s
                CommonUtils.swipe(driver.device_sn, self.swipe_p2[0], self.swipe_p2[1], self.swipe_p1[0],
                                  self.swipe_p1[1], 300)
                time.sleep(2)

        def step4(driver):
            Step('点击购物车跳转到购物车列表页面并上下滑动5次')

            # 1. 点击直播间购物车图标，等待2s
            driver.touch(CoordinateAdapter.convert_coordinate(
                driver,
                x=985,  # 原始x坐标
                y=702,  # 原始y坐标
                source_width=self.source_screen_width,
                source_height=self.source_screen_height
            ))
            time.sleep(1)

            # 购物车商品列表上滑5次
            for i in range(5):
                # 2. 购物车商品列表上滑5次，等待2s
                CommonUtils.swipe(driver.device_sn, self.swipe_p1[0], self.swipe_p1[1], self.swipe_p2[0],
                                  self.swipe_p2[1], 300)
                time.sleep(2)

            # 购物车商品列表下滑5次
            for i in range(5):
                # 3. 购物车商品列表下滑5次，等待2s
                CommonUtils.swipe(driver.device_sn, self.swipe_p2[0], self.swipe_p2[1], self.swipe_p1[0],
                                  self.swipe_p1[1], 300)
                time.sleep(2)

        def step5(driver):
            Step('点击购物车列表第一个商品，进入商品详情页面上下滑动5次')
            # 1. 点击购物车列表第一个商品，进入商品详情，等待1s
            driver.touch(CoordinateAdapter.convert_coordinate(
                driver,
                x=320,  # 原始x坐标
                y=420,  # 原始y坐标
                source_width=self.source_screen_width,
                source_height=self.source_screen_height
            ))
            time.sleep(1)

            # 购物车商品列表上滑5次
            for i in range(5):
                # 2. 购物车商品列表上滑5次，等待2s
                CommonUtils.swipe(driver.device_sn, self.swipe_p1[0], self.swipe_p1[1], self.swipe_p2[0],
                                  self.swipe_p2[1], 300)
                time.sleep(2)

            # 购物车商品列表下滑5次
            for i in range(5):
                # 3. 购物车商品列表下滑5次，等待2s
                CommonUtils.swipe(driver.device_sn, self.swipe_p2[0], self.swipe_p2[1], self.swipe_p1[0],
                                  self.swipe_p1[1], 300)
                time.sleep(2)

        self.execute_performance_step(1, step1, 10)
        self.execute_performance_step(2, step2, 30)
        self.execute_performance_step(3, step3, 40)
        self.execute_performance_step(4, step4, 40)
        self.execute_performance_step(5, step5, 40)

    def teardown(self):
        Log.info('teardown')
        self.driver.stop_app(self.app_package)
        self.generate_reports()
