import time

from hypium import BY

from hapray.core.perf_testcase import PerfTestCase


class PerfLoad_Wechat_0140(PerfTestCase):
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
        time.sleep(2)

        self.touch_by_text('测试账号', 1)
        # 点击右上角。。。
        self.touch_by_coordinates(1000, 178, 1)
        self.swipes_up(1, 1)
        self.touch_by_text('删除聊天记录', 1)
        self.touch_by_coordinates(566, 1998, 1)
        self.swipe_to_back()
        # 点击加号，等待2s
        self.driver.touch(self.convert_coordinate(1008, 2254))
        self.driver.wait(0.5)
        time.sleep(2)
        # 点击视频通话，等待2s
        self.driver.touch(BY.isAfter(BY.text('拍摄')).isBefore(BY.text('视频通话')).type('Image'))
        self.driver.wait(0.5)
        time.sleep(2)
        # 点击语音通话，等待2s
        self.driver.touch(BY.text('语音通话'))
        self.driver.wait(0.5)
        time.sleep(2)
        # 点击取消，等待2s
        self.driver.touch(BY.text('取消'))
        self.driver.wait(0.5)
        time.sleep(2)

        def step1():
            self.touch_by_text('已取消', 1)

        self.execute_performance_step('微信-语音通话场景-step1语音通话', 30, step1)
        self.touch_by_text('取消', 1)
