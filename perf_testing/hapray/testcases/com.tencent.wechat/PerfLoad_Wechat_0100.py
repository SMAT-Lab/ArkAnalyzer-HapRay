import time
from hypium import BY
from tensorflow import double

from hapray.core.perf_testcase import PerfTestCase


class PerfLoad_Wechat_0100(PerfTestCase):
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

        # 右上角+
        self.touch_by_coordinates(998, 176, 2)


        def step1():
            self.touch_by_text('收付款', 2)
            self.touch_by_text('二维码收款', 2)
            self.touch_by_text('设置金额', 2)
            
            # 2
            self.touch_by_coordinates(417, 1782, 1)   
            # 1
            self.touch_by_coordinates(172, 1774, 1)    
            # 5
            self.touch_by_coordinates(417, 1931, 1)    
            # 1
            self.touch_by_coordinates(172, 1774, 1)   
            # 9
            self.touch_by_coordinates(686, 2113, 1)    
            # .
            self.touch_by_coordinates(686, 2261, 1)    
            # 7
            self.touch_by_coordinates(172, 2120, 1)    
            # 1
            self.touch_by_coordinates(172, 1774, 1)
            time.sleep(3)     
            self.touch_by_text('确定', 2)        

        self.execute_performance_step('微信-二维码收款场景-step1二维码收款', 30, step1)

 




    
        





