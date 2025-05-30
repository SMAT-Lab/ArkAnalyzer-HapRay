# coding: utf-8
import os

from devicetest.core.test_case import Step
from hypium import BY

from hapray.core.PerfTestCase import PerfTestCase, Log
from hapray.core.common.CommonUtils import CommonUtils
from hapray.core.common.CoordinateAdapter import CoordinateAdapter


class ResourceUsage_PerformanceDynamic_jingdong_0030(PerfTestCase):

    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(self.TAG, controllers)

        self._app_package = 'com.jd.hm.mall'
        self._app_name = '京东'
        self._steps = [
            {
                "name": "step1",
                "description": "1.京东超市购物-点击3次，滑动8次"
            }
        ]
        
        # 原始采集设备的屏幕尺寸（Mate 60）
        self.source_screen_width = 1216
        self.source_screen_height = 2688


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
        os.makedirs(os.path.join(self.report_path, 'htrace'), exist_ok=True)
        os.makedirs(os.path.join(self.report_path, 'report'), exist_ok=True)

    def process(self):
        self.driver.swipe_to_home()

        # Step('启动京东应用')
        self.driver.start_app(self.app_package)
        self.driver.wait(5)

        # 点击京东超市
        # 从(824, 922)滑动至(7, 1344)
        p1 = CoordinateAdapter.convert_coordinate(
            self.driver,
            x=824,  # 原始x坐标
            y=922,  # 原始y坐标
            source_width=self.source_screen_width,
            source_height=self.source_screen_height
        )
        p2 = CoordinateAdapter.convert_coordinate(
            self.driver,
            x=7,  # 原始x坐标
            y=1344,  # 原始y坐标
            source_width=self.source_screen_width,
            source_height=self.source_screen_height
        )
        self.driver.slide(p1, p2)
        self.driver.wait(1)
        # 点击type为{Text}并且text为{全部频道}的控件
        self.driver.touch(BY.type('Text').text('全部频道'))
        self.driver.wait(2)

        CommonUtils.swipes_up_load(self.driver, swip_num=1, sleep=2)

        def step1(driver):
            self.driver.touch(BY.text('京东超市'))
            self.driver.wait(2)

            # 点击粮油调味
            self.driver.touch(BY.text('粮油调味'))
            self.driver.wait(2)

            # Step('粮油调味页上滑操作')
            CommonUtils.swipes_up_load(self.driver, swip_num=2, sleep=2)
            # Step('粮油调味页下滑操作')
            CommonUtils.swipes_down_load(self.driver, swip_num=6, sleep=2)

            # 加入第一个商品到购物车
            self.driver.touch(CoordinateAdapter.convert_coordinate(
                self.driver,
                x=1124,  # 原始x坐标
                y=1116,  # 原始y坐标
                source_width=self.source_screen_width,
                source_height=self.source_screen_height
            ))
            self.driver.wait(2)

        self.execute_step_with_perf_and_trace(1, step1, 40, sample_all=True)

        # 从购物车移除第一个商品
        self.driver.touch(CoordinateAdapter.convert_coordinate(
            self.driver,
            x=972,  # 原始x坐标
            y=1116,  # 原始y坐标
            source_width=self.source_screen_width,
            source_height=self.source_screen_height
        ))
        self.driver.wait(2)

    def teardown(self):
        Log.info('teardown')
        self.driver.stop_app(self.app_package)
        self.make_reports()
