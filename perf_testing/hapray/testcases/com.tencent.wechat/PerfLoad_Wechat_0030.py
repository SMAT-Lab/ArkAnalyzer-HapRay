import time

from hypium import BY

from hapray.core.perf_testcase import PerfTestCase


class PerfLoad_Wechat_0030(PerfTestCase):
    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(self.TAG, controllers)

        self._app_package = 'com.tencent.wechat'
        self._app_name = '微信'
        # 原始采集设备的屏幕尺寸（Nova 14）
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

        self.touch_by_text('性能测试群', 1)

        # 点击右上角。。。
        self.touch_by_coordinates(1000, 178, 1)
        self.swipes_up(1, 1)
        self.touch_by_text('删除聊天记录', 1)
        self.touch_by_coordinates(566, 1998, 1)
        self.swipe_to_back()

        # 点击加号
        self.touch_by_coordinates(1026, 2263, 1)
        self.touch_by_text('照片', 1)
        self.touch_by_text('图片和视频', 1)
        self.touch_by_coordinates(487, 757, 3)
        # 添加第一个视频
        self.touch_by_coordinates(210, 499, 1)
        self.touch_by_text('原图', 1)
        self.touch_by_text('发送(1)', 1)
        time.sleep(30)

        def step1():
            # 查看聊天记录中的视频
            comps = self.driver.find_all_components(BY.type('Image'))
            self.driver.touch(comps[0])
            self.driver.wait(0.5)

            time.sleep(30)

        self.execute_performance_step('微信-群聊页面播放视频场景-step1视频消息播放', 30, step1)

        self.swipe_to_back()
        self.swipe_to_back()
