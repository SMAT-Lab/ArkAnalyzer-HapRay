import time

from hypium import BY

from hapray.core.perf_testcase import PerfTestCase


class MemLoad_Wechat_0070(PerfTestCase):
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
            # 2.进入公众号页面：点击通讯录（等待2s），点击公众号（等待2s）
            self.driver.touch((0.38, 0.92), wait_time=2)
            if self.driver.find_component(BY.text('公众号')):
                self.touch_by_text('公众号', 2)
            else:
                self.driver.touch((0.26, 0.45), 2)

        def step3():
            # 3.进入具体公众号：点击xx，点击左上角设置（等待2s）
            self.touch_by_text('Alice ShiningDays', 2)
            self.driver.touch(BY.key('right'), wait_time=2)

        def step4():
            # 4.公众号消息浏览：上下滑动2次（滑动间隔2s）
            self.driver.check_component_exist(BY.text('已关注公众号'))
            self.swipes_up(2, 2)
            self.swipes_down(2, 2)

        self.execute_performance_step('微信-视频通话场景-step1打开微信', 10, step1)
        self.execute_performance_step(
            '微信-视频通话场景-step2进入公众号页面：点击通讯录（等待2s），点击公众号（等待2s）', 10, step2
        )
        self.execute_performance_step(
            '微信-视频通话场景-step3进入具体公众号：点击xx，点击左上角设置（等待2s）', 10, step3
        )
        self.execute_performance_step('微信-视频通话场景-step4公众号消息浏览：上下滑动2次（滑动间隔2s）', 10, step4)
