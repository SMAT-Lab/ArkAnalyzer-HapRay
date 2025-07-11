# coding: utf-8
import time

from hypium import BY

from hapray.core.perf_testcase import PerfTestCase


class ResourceUsage_PerformanceDynamic_xhs_0070(PerfTestCase):

    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(self.TAG, controllers)

        self._app_package = 'com.xingin.xhs_hos'
        self._app_name = '小红书'
        # 原始采集设备的屏幕尺寸（Mate 60 Pro）
        self.source_screen_width = 1260
        self.source_screen_height = 2720

    @property
    def app_package(self) -> str:
        return self._app_package

    @property
    def app_name(self) -> str:
        return self._app_name

    def process(self):
        self.start_app()
        self.touch_by_text('我', 2)
        self.touch_by_text('赞过', 2)

        video_tag = '女孩子一生一定要去的九个地方#旅行推荐官 #旅行大玩家 #旅行攻略 #旅行 #跟'
        self.find_by_text_up(video_tag, 10)
        self.touch_by_text(video_tag, 2)

        # 点击评论 输入框
        self.touch_by_coordinates(1124, 2552, 1)

        # 点击相册图标，调起图库picker
        self.touch_by_coordinates(1137, 2538, 1)

        # 点击任一动态图片，在动态图片大图界面，上滑退出小红书，再启动，操作5次
        def step1():
            # 点击第一排第四张（最后一张）动态图片
            self.touch_by_coordinates(1152, 1031, 1)

            # 上滑退出小红书，再启动，操作5次，观察启动/退出动效是否流畅
            for i in range(5):
                self.driver.swipe_to_home()
                time.sleep(2)

                self.driver.touch(BY.key("AppIcon_Image_com.xingin.xhs_hosEntryAbilityredbook0_undefined"))
                time.sleep(2)

        self.execute_performance_step("小红书-动态图片启动退出场景-step1动态图片启动退出", 30, step1)
