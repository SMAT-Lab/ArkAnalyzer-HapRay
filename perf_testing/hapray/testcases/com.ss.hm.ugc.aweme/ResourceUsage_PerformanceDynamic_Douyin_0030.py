# coding: utf-8
import os
import time

from devicetest.core.test_case import Step
from hypium import BY

from hapray.core.PerfTestCase import PerfTestCase, Log
from hapray.core.common.CommonUtils import CommonUtils


class ResourceUsage_PerformanceDynamic_Douyin_0030(PerfTestCase):

    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(self.TAG, controllers)

        self._app_package = 'com.ss.hm.ugc.aweme'
        self._app_name = '抖音'
        self._steps = [
            {
                "name": "step1",
                "description": "1. 点击评论图标，弹出评论界面"
            },
            {
                "name": "step2",
                "description": "2. 在评论界面开始上滑，每1s滑动一次，先下滑10次，再上滑10次，共20次"
            },
            {
                "name": "step3",
                "description": "3. 点击输入框，收起输入框，反复操作10次，每次间隔1s"
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
        comment_component = (1187, 1750)
        def start(driver):

            # 1. 打开抖音，等待 5s
            driver.start_app(self.app_package)
            time.sleep(5)

            # 2. 搜索“李点点简笔画”， 进入该主页
            component = driver.find_component(BY.id('topTabsRightSlot'))
            if not component:
                component = (1228, 200)
            driver.touch(component)
            time.sleep(1)
            driver.input_text(BY.type('TextInput'), '李点点简笔画')
            time.sleep(1)

            component = driver.find_component(BY.id('search_button'))
            if not component:
                component = (1196, 196)
            driver.touch(component)
            time.sleep(3)
            component = driver.find_component(BY.text('李点点'))
            if not component:
                component = (306, 411)
            driver.touch(component)
            time.sleep(5)

            # 3. 点开置顶的第一个视频（内容为画篮球，排球，足球，棒球);
            driver.touch((200, 2000))
            time.sleep(3)

        def step1(driver):
            Step('1. 点击评论图标，弹出评论界面')
            driver.touch(comment_component)
            time.sleep(2)

            # 点击空白处，收起评论界面
            driver.touch((630, 338))
            time.sleep(2)

        def step2(driver):
            Step('2. 在评论界面开始上滑，每1s滑动一次，先下滑10次，再上滑10次，共20次')
            for _ in range(10):
                CommonUtils.swipe(driver.device_sn, 630, 2500, 630, 1550, 300)
                time.sleep(1)

            for _ in range(10):
                CommonUtils.swipe(driver.device_sn, 630, 1550, 630, 2500, 300)
                time.sleep(1)

        def step3(driver):
            Step('3. 点击输入框，收起输入框，反复操作10次，每次间隔1s')
            component = driver.find_component(BY.text('善语结善缘，恶语伤人心'))
            if not component:
                component = (150, 2594)
            component2 = (630, 338)

            for _ in range(10):
                driver.touch(component)
                time.sleep(1)

                driver.touch(component2)
                time.sleep(1)

        def finish(driver):
            for _ in range(6):
                driver.swipe_to_back()
                time.sleep(1)
            driver.swipe_to_home()

        start(self.driver)
        self.execute_step_with_perf_and_trace(1, step1, 10)
        # 点击评论图标，弹出评论界面
        self.driver.touch(comment_component)
        time.sleep(1)
        self.execute_step_with_perf_and_trace(2, step2, 35)
        self.execute_step_with_perf_and_trace(3, step3, 30)
        finish(self.driver)

    def teardown(self):
        Log.info('teardown')
        self.driver.stop_app(self.app_package)
        self.make_reports()
