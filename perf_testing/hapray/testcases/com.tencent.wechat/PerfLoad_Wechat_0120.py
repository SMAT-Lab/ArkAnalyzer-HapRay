import time
from hypium import BY
from tensorflow import double

from hapray.core.perf_testcase import PerfTestCase


class PerfLoad_Wechat_0120(PerfTestCase):
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

        #self.touch_by_text('通讯录', 1)
        self.touch_by_coordinates(407, 2241, 2)   
        self.touch_by_text('公众号', 1)
        self.touch_by_text('T', 1)
        self.touch_by_text('腾讯新闻', 1)


        def step1():
            
            self.touch_by_text('早报晚报', 2)
            # 点击早报
            self.touch_by_coordinates(544, 1922, 2)   
            
            self.swipes_up(3, 2)
            self.swipes_down(3, 2)
              
       
            
        self.execute_performance_step('微信-点击早报晚报滑动场景-step1早报浏览', 30, step1)
        

 




    
        





