# coding: utf-8
import os
import time

from devicetest.core.test_case import Step
from hypium import BY

from aw.PerfTestCase import PerfTestCase, Log
from aw.common.CommonUtils import CommonUtils


class ResourceUsage_PerformanceDynamic_xhs_0070(PerfTestCase):

    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(self.TAG, controllers)

        self._app_package = 'com.xingin.xhs_hos'
        self._app_name = '小红书'
        self._steps = [
            {
                "name": "step1",
                "description": "1. 动态图片启动退出"
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

        Step('启动被测应用')
        self.driver.start_app(self.app_package)
        self.driver.wait(5)

        # 拖拽显示隐藏tab栏
        CommonUtils.swipes_down_load(self.driver, swip_num=1, sleep=5)

        # 点击进入视频页
        self.driver.touch(BY.text('视频'))
        time.sleep(2)
        # 点击进入任意视频
        self.driver.touch((350, 1010))
        time.sleep(2)
        # 点击评论 输入框
        # self.driver.touch((1140, 2630))
        # self.driver.touch((1054, 2520)) # Mate70
        self.driver.touch((1124, 2552))  # Mate60Pro
        time.sleep(1)
        # 点击相册图标，调起图库picker
        # self.driver.touch((1180, 2620))
        # self.driver.touch((1088, 2506)) # Mate70
        self.driver.touch((1137, 2538))  # Mate60Pro
        time.sleep(1)

        # 点击任一动态图片，在动态图片大图界面，上滑退出小红书，再启动，操作5次
        def step1(driver):
            Step('1. 动态图片启动退出')
            time_start = time.time()

            # 点击第一排第四张（最后一张）动态图片
            # driver.touch((1198, 1093))
            driver.touch((1152, 1031)) # Mate70 Mate60Pro
            time.sleep(1)

            # 上滑退出小红书，再启动，操作5次，观察启动/退出动效是否流畅
            for i in range(5):
                driver.swipe_to_home()
                time.sleep(2)

                driver.touch(BY.key("AppIcon_Image_com.xingin.xhs_hosEntryAbilityredbook0_undefined"))
                time.sleep(2)
            time_end = time.time()
            if time_end - time_start < 30:
                time.sleep(30 - (time_end - time_start))

        self.execute_step_with_perf(1, step1, 30)

    def teardown(self):
        Log.info('teardown')
        self.driver.stop_app(self.app_package)
        self.make_reports()
