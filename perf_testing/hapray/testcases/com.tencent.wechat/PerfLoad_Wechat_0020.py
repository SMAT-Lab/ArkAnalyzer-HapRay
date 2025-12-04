import time
from hypium import BY
from tensorflow import double

from hapray.core.perf_testcase import PerfTestCase


class PerfLoad_Wechat_0020(PerfTestCase):
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
        
        def step1():
            for _i in range(2):
                # 点击表情包，等待2秒
                self.driver.touch(self.convert_coordinate(892, 2263))
                self.driver.wait(0.5)
                time.sleep(2)
                # 选择前三个表情发送，等待2s
                for _i in range(3):
                    self.driver.touch(self.convert_coordinate(98, 1732))
                # 发送
                self.driver.touch(self.convert_coordinate(1000, 1247))
                self.driver.wait(0.5)
                self.driver.swipe_to_back()
                # 发送文字消息“Areyouok”给好友（2s，停留2s）
                send_input = self.convert_coordinate(490, 2250)
                self.driver.input_text(send_input, 'Areyouok')
                self.driver.touch(BY.text('发送'))
                self.driver.wait(0.5)
                self.driver.swipe_to_back()
        def step2():
            # 点击加号
            self.touch_by_coordinates(1026, 2263, 1)
            self.touch_by_text('照片', 1)
            self.touch_by_text('图片和视频', 1)
            self.touch_by_text('视频', 3)
            # 添加第一个视频
            self.touch_by_coordinates(210, 499, 1)
            self.touch_by_coordinates(210, 499, 1)
            self.touch_by_text('原图', 1)
            self.touch_by_text('发送(1)', 1)
            time.sleep(30)

        def step3():
            self.swipes_down(5, 1)
            self.swipes_up(5, 1)

    
        self.execute_performance_step('微信-微信群聊表情包文字消息发送合浏览-step1表情包文字发送', 55, step1)
        self.execute_performance_step('微信-微信群聊表情包文字消息发送合浏览-step2视频发送', 45, step2)
        self.execute_performance_step('微信-微信群聊表情包文字消息发送合浏览-step3聊天页浏览', 35, step3)




