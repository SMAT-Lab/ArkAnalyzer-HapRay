import time

from hypium import BY

from hapray.core.perf_testcase import PerfTestCase


class MemLoad_Wechat_0050(PerfTestCase):
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
            # 2.进入好友聊天界面：点击微信（等待2s），点击“视频测试”（等待1s）
            self.touch_by_text('微信', 1)
            self.touch_by_text('视频测试', 1)

        def step3():
            # 3.打视频电话：手机1：点击+（等待2s），点击视频通话（等待2s），再次点击视频通话（等待2s）；等待10s，挂断电话（等待2s）
            self.driver.touch((0.94, 0.93), wait_time=2)
            self.touch_by_text('视频通话', 2)
            self.touch_by_text('视频通话', 2)
            comp = self.driver.find_component(BY.text('我知道了'))
            if comp:
                self.touch_by_text('我知道了', 2)

        def step4():
            # 4.删除消息：点击右上设置（等待1s），点击删除聊天记录（等待1s），点击删除聊天记录（等待4s）
            self.driver.touch(BY.key('right'), wait_time=1)
            self.touch_by_text('删除聊天记录', 1)
            self.driver.touch(self.driver.find_all_components(BY.text('删除聊天记录'), 1), wait_time=4)

        self.execute_performance_step('微信-视频通话场景-step1打开微信', 10, step1)
        self.execute_performance_step(
            '微信-视频通话场景-step2进入好友聊天界面：点击微信（等待2s），点击“视频测试”（等待1s）', 10, step2
        )
        self.execute_performance_step(
            '微信-视频通话场景-step3打视频电话：手机1：点击+（等待2s），点击视频通话（等待2s），再次点击视频通话（等待2s）；等待10s，挂断电话（等待2s）',
            20,
            step3,
        )
        self.execute_performance_step(
            '微信-视频通话场景-step4删除消息：点击右上设置（等待1s），点击删除聊天记录（等待1s），点击删除聊天记录（等待4s）',
            10,
            step4,
        )
