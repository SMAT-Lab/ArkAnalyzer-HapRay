# coding: utf-8
import os
import time

from devicetest.core.test_case import Step
from hypium import BY
from hypium.model import UiParam

from hapray.core.perf_testcase import PerfTestCase, Log
from hapray.core.common.common_utils import CommonUtils
from hapray.core.common.coordinate_adapter import CoordinateAdapter


class ResourceUsage_PerformanceDynamic_Douyin_0060(PerfTestCase):

    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(self.TAG, controllers)

        self._app_package = 'com.ss.hm.ugc.aweme'
        self._app_name = '抖音'
        self._steps = [
            {
                "name": "step1",
                "description": "1. 抖音-热点、关注、朋友tab页切换场景"
            }
        ]
        # 原始采集设备的屏幕尺寸（Pura 70 Pro）
        self.source_screen_width = 1260
        self.source_screen_height = 2844

    @property
    def steps(self) -> list[dict[str, str]]:
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
        Step('启动被测应用')
        self.driver.wake_up_display()
        time.sleep(1)
        self.driver.swipe_to_home()
        time.sleep(1)
        # 1. 打开抖音，等待 5s
        self.driver.start_app(self.app_package)
        self.driver.wait(2)  # 等待应用启动
        time.sleep(3)

        Step('1. 抖音-热点、关注、朋友tab页切换场景')
        component_toptabs = self.driver.find_component(BY.id('HomePage_Top_Tabs_Tree_Container'))
        for _ in range(3):
            self.driver.swipe(UiParam.RIGHT, area=component_toptabs, distance=60, start_point=(0.4, 0.1),
                              swipe_time=0.4)
            time.sleep(2)
            component_hotspots = self.driver.find_component(BY.id('home-top-tab-text-homepage_pad_hot'))
            if component_hotspots:
                break
        component_follow = self.driver.find_component(BY.id('home-top-tab-text-homepage_follow'))
        if not component_follow:
            component_follow = self.driver.find_component(BY.text('关注'))
        if not component_follow:
            component_follow = CoordinateAdapter.convert_coordinate(
                self.driver,
                x=1050,  # 原始x坐标
                y=205,  # 原始y坐标
                source_width=self.source_screen_width,
                source_height=self.source_screen_height)

        component_friend = self.driver.find_component(BY.id('main-bottom-tab-text-homepage_familiar'))
        if not component_friend:
            component_friend = self.driver.find_component(BY.text('朋友'))
            if not component_friend:
                component_friend = CoordinateAdapter.convert_coordinate(
                    self.driver,
                    x=400,  # 原始x坐标
                    y=2640,  # 原始y坐标
                    source_width=self.source_screen_width,
                    source_height=self.source_screen_height)

        def step1(driver):
            # 1. 点击热点
            driver.touch(component_hotspots)
            time.sleep(2)

            # 2. 热点页面上滑3次
            for _ in range(3):
                CommonUtils.swipes_up_load(driver, 1, 2, 300)

            # 3. 点击关注
            driver.touch(component_follow)
            time.sleep(2)

            # 4. 关注页面上滑3次
            for _ in range(3):
                CommonUtils.swipes_up_load(driver, 1, 2, 300)

            # 5. 点击朋友
            driver.touch(component_friend)
            time.sleep(2)

            # 6. 朋友页面上滑3次，间隔2秒
            for _ in range(3):
                CommonUtils.swipes_up_load(driver, 1, 2, 300)

        def finish(driver):
            driver.swipe_to_back()
            driver.swipe_to_home()

        self.execute_performance_step(1, step1, 35)
        finish(self.driver)

    def teardown(self):
        Log.info('teardown')
        self.driver.stop_app(self.app_package)
        self.generate_reports()
