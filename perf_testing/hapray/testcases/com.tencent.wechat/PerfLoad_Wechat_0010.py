import time
from hypium import BY
from tensorflow import double

from hapray.core.perf_testcase import PerfTestCase


class PerfLoad_Wechat_0010(PerfTestCase):
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

        def step1():
            for _i in range(10):
                self.swipes_up(1, 1)
                self.swipes_down(1, 1)
        def step2():
            self.touch_by_text('测试账号', 1)
            # 点击加号
            self.touch_by_coordinates(1026, 2263, 1)
            self.touch_by_text('照片', 1)
            self.touch_by_text('图片和视频', 1)
            self.touch_by_text('图片', 3)
            # 添加5张图片
            self.touch_by_coordinates(226, 499, 1)
            self.touch_by_coordinates(226, 499, 1)
            self.touch_by_coordinates(485, 499, 1)
            self.touch_by_coordinates(768, 499, 1)
            self.touch_by_coordinates(1036, 499, 1)
            self.touch_by_coordinates(226, 760, 1)

            self.touch_by_text('原图', 1)
            self.touch_by_text('预览', 1)

            self.swipes_left(4, 1)

            self.touch_by_text('发送(5)', 1)

        def step3():
            self.swipes_down(10, 1)
            self.swipes_up(10, 1)

        def step4():
            # 查看聊天记录中的图片
            comps = self.driver.find_all_components(BY.type('Image'))
            self.driver.touch(comps[5])
            self.driver.wait(0.5)
            for _i in range(10):
                self.driver.touch(self.convert_coordinate(485, 499),double)
                time.sleep(2)
                self.driver.touch(self.convert_coordinate(485, 499), double)
                time.sleep(2)

        def step5():
            self.swipes_right(5, 1)
            self.swipes_left(5, 1)

        def step6():
            for _i in range(5):
                # 放大
                self.driver.pinch_out(BY.type('Image'))
                # 缩小
                self.driver.pinch_in(BY.type('Image'))

        self.execute_performance_step('微信-群聊图片消息发送和浏览场景-step1消息列表浏览', 40, step1)
        self.execute_performance_step('微信-群聊图片消息发送和浏览场景-step2照片消息发送', 30, step2)
        self.execute_performance_step('微信-群聊图片消息发送和浏览场景-step3聊天页浏览', 40, step3)
        self.execute_performance_step('微信-群聊图片消息发送和浏览场景-step4图片放大缩小', 55, step4)
        self.execute_performance_step('微信-群聊图片消息发送和浏览场景-step4图片滑动浏览', 40, step5)
        self.execute_performance_step('微信-群聊图片消息发送和浏览场景-step4图片双指放大/缩小', 30, step6)



