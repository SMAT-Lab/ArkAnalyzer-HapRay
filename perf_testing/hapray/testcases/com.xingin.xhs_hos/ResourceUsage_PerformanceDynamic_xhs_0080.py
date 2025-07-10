# coding: utf-8

from hapray.core.perf_testcase import PerfTestCase


class ResourceUsage_PerformanceDynamic_xhs_0080(PerfTestCase):

    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(self.TAG, controllers)

        self._app_package = 'com.xingin.xhs_hos'
        self._app_name = '小红书'
        # 原始采集设备的屏幕尺寸（Nova14）
        self.source_screen_width = 1084
        self.source_screen_height = 2412

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

        video_tag = '女孩子一生一定要去的九个地方#旅行推荐官 #旅行大玩家 #旅游攻略 #旅行 #跟'
        self.find_by_text_up(video_tag, 10)

        def step1():
            # 点击进入视频，滑动切换视频上下各5次，点击取消点赞/点赞各1次
            self.touch_by_text(video_tag, 2)
            self.swipes_up(5, 2, 300)
            self.swipes_down(5, 2, 300)

            # 点击取消点赞/点赞各1次
            self.touch_by_coordinates(446, 2235, 1)
            self.touch_by_coordinates(446, 2235, 1)

        def step2():
            # 点击视频评论区
            self.touch_by_coordinates(884, 2257, 2)
            self.swipes_up(5, 2, 300)

        self.execute_performance_step("小红书-视频及评论浏览-step1视频切换浏览", 40, step1)
        self.swipes_up(1, 2)
        self.execute_performance_step("小红书-视频及评论浏览-step2评论区浏览", 20, step2)
