import time
from hypium import BY
from tensorflow import double

from hapray.core.perf_testcase import PerfTestCase


class PerfLoad_Wechat_0110(PerfTestCase):
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

        self.touch_by_text('测试账号', 2)


        def step1():
            
            # 点击+
            self.touch_by_coordinates(1023, 2259, 1)   
            
            self.touch_by_text('拍摄', 2)    
            self.touch_by_text('录像', 2)    
            # 开始录像
            self.touch_by_coordinates(560, 2046, 10)    
            # 停止录像
            self.touch_by_coordinates(560, 2046, 2)    
              
       
            
        self.execute_performance_step('微信-单聊录制和发送视频场景-step1录制视频', 30, step1)
        # 点击对号发送
        self.touch_by_coordinates(933, 2073, 1) 
        time.sleep(10)

 




    
        





