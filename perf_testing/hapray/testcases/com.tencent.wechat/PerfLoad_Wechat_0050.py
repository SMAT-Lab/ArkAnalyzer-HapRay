import time
from hypium import BY
from tensorflow import double

from hapray.core.perf_testcase import PerfTestCase


class PerfLoad_Wechat_0050(PerfTestCase):
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
        time.sleep(5)
        # 通过相对位置点击控件
        self.driver.touch(BY.isAfter(BY.text('通讯录')).isBefore(BY.text('发现')).type('Image'))
        self.driver.wait(0.5)



        def step1():
            self.touch_by_text('朋友圈', 1)
            # self.swipes_up(5, 1)
            # self.swipes_down(5, 1)

        def step2():
            # 点击朋友圈图片
            comps = self.driver.find_all_components(BY.type('Image'))
            self.driver.touch(comps[5])
            self.driver.wait(0.5)
            self.swipes_left(8, 1)
            self.swipes_right(8, 1)
        def step3():
            # 通过相对位置点击控件
            comps = self.driver.find_all_components(BY.type('View'))
            self.driver.touch(comps[0])
            self.driver.wait(0.5)

        def step4():
            self.touch_by_text('从相册选择', 1)

            self.touch_by_text('图片和视频', 1)
            # 点击图片
            self.touch_by_coordinates(512, 569, 1)
            for _i in range(3):
                self.swipes_up(1, 1)
                # 添加3张图片
                self.touch_by_coordinates(226, 499, 1)
                self.touch_by_coordinates(485, 499, 1)
                self.touch_by_coordinates(768, 499, 1)
            self.touch_by_text('预览', 2)

            self.swipes_left(2, 2)
            self.touch_by_text('完成(3)', 2)
            self.touch_by_text('发表', 2)


            
        self.execute_performance_step('微信-朋友圈播放视频场景-step1朋友圈浏览', 5, step1)
        # self.execute_performance_step('微信-朋友圈播放视频场景-step2朋友圈图片查看', 20, step2)
        # self.swipe_to_back()
        # self.execute_performance_step('微信-朋友圈播放视频场景-step3朋友圈视频播放', 20, step3)
        # self.swipe_to_back()
        # 点击右上角相机图片
        self.touch_by_coordinates(983, 188, 2)
        self.execute_performance_step('微信-朋友圈播放视频场景-step4朋友圈发布&删除', 20, step4)
        # 点击type为{Button}并且text为{删除}的控件
        self.driver.touch(BY.type('Button').text('删除'))
        self.driver.wait(0.5)
        # 删除
        self.touch_by_coordinates(752, 1384, 2)
        self.driver.wait(0.5)




    
        





