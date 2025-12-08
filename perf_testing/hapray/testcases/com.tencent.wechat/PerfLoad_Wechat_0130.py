import time

from hapray.core.perf_testcase import PerfTestCase


class PerfLoad_Wechat_0130(PerfTestCase):
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

        def step1():
            for _i in range(6):
                # 点击输入框
                self.touch_by_coordinates(533, 2235, 2)
                # 点击空白背景
                self.touch_by_coordinates(463, 1123, 2)

        def step2():
            self.touch_by_text('测试账号', 1)
            # 点击输入框
            self.touch_by_coordinates(533, 2235, 2)
            for _i in range(2):
                for _i in range(30):
                    # 点击输入g
                    self.touch_by_coordinates(542, 1884, 0.5)
                # 点击发送
                self.touch_by_text('发送', 1)

        self.execute_performance_step('微信-单聊场景-step1输入法弹出收起', 35, step1)
        self.swipe_to_back()
        self.touch_by_text('测试账号', 1)
        # 点击输入框
        self.touch_by_coordinates(533, 2235, 2)
        # 切换到英文
        self.touch_by_coordinates(237, 2210, 2)
        self.swipe_to_back()
        self.swipe_to_back()
        self.execute_performance_step('微信-单聊场景-step1连续输入字母', 70, step2)
        # 切换到中文
        self.touch_by_coordinates(237, 2210, 2)
        self.swipe_to_back()
        self.swipe_to_back()
        # self.execute_performance_step('微信-单聊场景-step1图片消息转发', 40, step3)
        # self.execute_performance_step('微信-单聊场景-step1语音消息发送', 40, step4)
