import time
from hypium import BY
from tensorflow import double

from hapray.core.perf_testcase import PerfTestCase


class PerfLoad_Wechat_0150(PerfTestCase):
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


        self.touch_by_text('性能测试群', 1)
        # 点击右上角。。。
        self.touch_by_coordinates(1000, 178, 1)
        self.swipes_up(1,1)
        self.touch_by_text('删除聊天记录', 1)
        self.touch_by_coordinates(566, 1998, 1)
        self.swipe_to_back()
        # 点击加号，等待2s
        self.driver.touch(self.convert_coordinate(1008, 2254))
        self.driver.wait(0.5)
        time.sleep(2)

        def step1():
            self.touch_by_text('红包', 1)
            # 设置红包个数
            self.touch_by_coordinates(830, 430, 1)
            # 1
            self.touch_by_coordinates(177, 1755, 1)
            self.touch_by_text('确定', 1)
            # 设置红包金额
            self.touch_by_coordinates(927, 685, 1)
            # 0.01
            self.touch_by_coordinates(287, 2268, 1)
            self.touch_by_coordinates(689, 2268, 1)
            self.touch_by_coordinates(287, 2268, 1)
            self.touch_by_coordinates(177, 1755, 1)
            self.touch_by_text('确定', 1)
            self.touch_by_text('塞钱进红包', 1)
            # 输入密码199267
            self.touch_by_coordinates(208, 1746, 1)
            self.touch_by_coordinates(933, 2089, 1)
            self.touch_by_coordinates(933, 2089, 1)
            self.touch_by_coordinates(551, 1769, 1)
            self.touch_by_coordinates(919, 1919, 1)
            self.touch_by_coordinates(180, 2100, 1)

            self.touch_by_text('微信红包', 1)
            #self.touch_by_text('開', 1)
            self.touch_by_coordinates(538, 1567, 1)

        self.execute_performance_step('微信-群聊发送收红包场景-step1群聊发送&收红包', 30, step1)
        



        

 




    
        





