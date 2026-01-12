import time

from hypium import BY

from hapray.core.perf_testcase import PerfTestCase


class MemLoad_Wechat_0030(PerfTestCase):
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
        def step1():
            # 1.打开微信（等待5s）
            self.start_app()
            time.sleep(5)

        def step2():
            # 2.进入朋友圈页面：点击发现（等待1s），点击朋友圈（等待2s）
            self.touch_by_text('微信', 1)
            self.touch_by_text('群聊1', 1)

        def step3():
            # 3.进入选择拍照页面：点击相册按钮（等待1s）
            self.driver.touch((0.94, 0.93), wait_time=1)
            self.touch_by_text('拍摄', 2)

        def step4():
            # 4.进行拍照：点击拍摄（等待2s），点击拍摄按钮（等待1s），点击对号（等待1s）
            self.driver.touch(BY.key('SHUTTER_BUTTON_NORMAL_OUT_BTN'), wait_time=2)
            self.driver.touch(BY.key('COMPONENT_ID_THIRDPARTYCALL_CONFIRM_1'), wait_time=2)

        def step5():
            # 5.发表朋友圈：点击发表（等待2s）
            self.touch_by_text('发送', 5)

        def step6():
            # 6.删除朋友圈：点击删除按钮（等待1s），点击删除（等待2s）
            self.driver.touch((0.94, 0.93), wait_time=1)
            self.touch_by_text('拍摄', 2)
            self.touch_by_text('录像', 2)

        self.execute_performance_step('微信-发朋友圈场景-step1打开微信', 10, step1)
        self.execute_performance_step(
            '微信-发朋友圈场景-step2进入朋友圈页面：点击发现（等待1s），点击朋友圈（等待2s）', 10, step2
        )
        self.execute_performance_step('微信-发朋友圈场景-step3进入选择拍照页面：点击相册按钮（等待1s）', 10, step3)
        self.execute_performance_step(
            '微信-发朋友圈场景-step4进行拍照：点击拍摄（等待2s），点击拍摄按钮（等待1s），点击对号（等待1s）', 10, step4
        )
        self.execute_performance_step('微信-发朋友圈场景-step5发表朋友圈：点击发表（等待2s）', 10, step5)
        self.execute_performance_step(
            '微信-发朋友圈场景-step6删除朋友圈：点击删除按钮（等待1s），点击删除（等待2s）', 10, step6
        )
