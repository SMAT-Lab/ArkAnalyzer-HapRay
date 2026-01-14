import time

from hypium import BY

from hapray.core.perf_testcase import PerfTestCase


class MemLoad_Wechat_0020(PerfTestCase):
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
            # 2.进入聊天窗口：点击微信（等待1s），群聊1（等待2s）
            self.touch_by_text('微信', 1)
            self.touch_by_text('群聊1', 1)

        def step3():
            # 3.进入拍照页面：点击+（等待1s），点击拍摄（等待2s）
            self.driver.touch((0.94, 0.93), wait_time=1)
            self.touch_by_text('拍摄', 2)

        def step4():
            # 4.进行拍照：点击拍照按钮（等待2s），点击对号（等待2s）
            self.driver.touch(BY.key('SHUTTER_BUTTON_NORMAL_OUT_BTN'), wait_time=2)
            self.driver.touch(BY.key('COMPONENT_ID_THIRDPARTYCALL_CONFIRM_1'), wait_time=2)

        def step5():
            # 5.发送消息：点击发送（等待5s）
            self.touch_by_text('发送', 5)

        def step6():
            # 6.进入录像页面：点击+（等待1s），点击拍摄（等待2s），点击录像（等待2s）
            self.driver.touch((0.94, 0.93), wait_time=1)
            self.touch_by_text('拍摄', 2)
            self.touch_by_text('录像', 2)

        def step7():
            # 7.录制视频：点击录制按钮（等待10s），点击停止按钮（等待2s），点击对号（等待2s）
            self.driver.touch(BY.key('COMPONENT_ID_SHUTTER_VIDEO_1'), wait_time=10)
            self.driver.touch(BY.key('SHUTTER_BUTTON_NORMAL_OUT_BTN'), wait_time=2)
            self.driver.touch(BY.key('COMPONENT_ID_THIRDPARTYCALL_CONFIRM_1'), wait_time=2)

        def step8():
            # 8.删除消息：点击右上设置（等待1s），向下滑一次（等待1s），点击删除聊天记录（等待1s），点击删除聊天记录（等待4s）
            self.driver.touch(BY.key('right'), wait_time=1)
            self.swipes_up(1, 1)
            self.driver.touch(BY.text('删除聊天记录'), wait_time=1)
            self.driver.touch(self.driver.find_all_components(BY.text('删除聊天记录', 1)), wait_time=4)

        self.execute_performance_step('微信-拍照和录像场景-step1打开微信', 10, step1)
        self.execute_performance_step(
            '微信-拍照和录像场景-step2进入聊天窗口：点击微信（等待1s），群聊1（等待2s）', 10, step2
        )
        self.execute_performance_step(
            '微信-拍照和录像场景-step3进入拍照页面：点击+（等待1s），点击拍摄（等待2s）', 10, step3
        )
        self.execute_performance_step(
            '微信-拍照和录像场景-step4进行拍照：点击拍照按钮（等待2s），点击对号（等待2s）', 10, step4
        )
        self.execute_performance_step('微信-拍照和录像场景-step5发送消息：点击发送（等待5s）', 10, step5)
        self.execute_performance_step(
            '微信-拍照和录像场景-step6进入录像页面：点击+（等待1s），点击拍摄（等待2s），点击录像（等待2s）', 10, step6
        )
        self.execute_performance_step(
            '微信-拍照和录像场景-step7录制视频：点击录制按钮（等待10s），点击停止按钮（等待2s），点击对号（等待2s）',
            20,
            step7,
        )
        self.execute_performance_step(
            '微信-拍照和录像场景-step8删除消息：点击右上设置（等待1s），向下滑一次（等待1s），点击删除聊天记录（等待1s），点击删除聊天记录（等待4s）',
            10,
            step8,
        )
