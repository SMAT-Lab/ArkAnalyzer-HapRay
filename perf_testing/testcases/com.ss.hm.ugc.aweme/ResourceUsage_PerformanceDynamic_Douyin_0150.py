# coding: utf-8
import os
import time

from devicetest.core.test_case import Step
from hypium import BY

from aw.PerfTestCase import PerfTestCase, Log
from aw.common.CommonUtils import CommonUtils


class ResourceUsage_PerformanceDynamic_Douyin_0150(PerfTestCase):

    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(self.TAG, controllers)

        self._app_package = 'com.ss.hm.ugc.aweme'
        self._app_name = '抖音'
        self._steps = [
            {
                "name": "step1",
                "description": "1. 搜索列表上滑10次，下滑10次，每次间隔1s"
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
        def start(driver):
            Step('启动被测应用')
            driver.wake_up_display()
            time.sleep(1)
            self.driver.swipe_to_home()
            time.sleep(1)
            # 1. 打开抖音，等待 5s
            self.driver.start_app(self.app_package)
            driver.wait(2)  # 等待应用启动
            time.sleep(3)

            # 2. 点击搜索框，输入【与辉同行】
            component_search = driver.find_component(BY.id('topTabsRightSlot'))
            if not component_search:
                component_search = (1228, 200)
            driver.touch(component_search)
            time.sleep(2)

            driver.input_text(BY.type('TextInput'), '与辉同行')
            time.sleep(2)
            driver.touch(BY.id('search_button'))

        def step1(driver):
            Step('1. 搜索列表上滑10次，每次间隔1s')

            # 上滑10次
            for _ in range(10):
                CommonUtils.swipes_up_load(driver, 1, 1, 300)

            # 下滑10次
            for _ in range(10):
                CommonUtils.swipes_down_load(driver, 1, 1, 300)

        def finish(driver):
            driver.swipe_to_home()
            time.sleep(1)

        start(self.driver)
        self.execute_step_with_perf(1, step1, 35)
        finish(self.driver)

    def teardown(self):
        Log.info('teardown')
        self.driver.stop_app(self.app_package)
        self.make_reports()
