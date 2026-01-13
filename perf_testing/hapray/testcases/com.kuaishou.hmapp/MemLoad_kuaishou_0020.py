import time

from hypium import BY

from hapray.core.perf_testcase import PerfTestCase


class MemLoad_kuaishou_0020(PerfTestCase):
    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(self.TAG, controllers)

        self._app_package = 'com.kuaishou.hmapp'
        self._app_name = '快手'
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
        self.driver.swipe_to_home()

        def step1():
            # 1.启动快手（等待5s）
            self.driver.start_app(self.app_package)
            self.driver.wait(5)
            time.sleep(5)

        def step2():
            # 2.进入首页：点击底部首页tab
            self.driver.touch(BY.text('首页'), wait_time=2)

        def step3():
            # 3.进入关注页面：点击顶部关注tab（等待2s）
            self.driver.touch(BY.text('关注'), wait_time=2)

        def step4():
            # 4.页面浏览：上下滑动3次（滑动间隔2s）
            self.swipes_up(swip_num=3, sleep=2)
            self.swipes_down(swip_num=3, sleep=2)

        def step5():
            # 5.进入精选界面：点击底部朋友“精选”（等待3s）
            self.driver.touch(BY.text('精选'), wait_time=3)

        def step6():
            # 6.上下滑动3次浏览视频（滑动间隔3s）
            self.swipes_up(swip_num=3, sleep=3)
            self.swipes_down(swip_num=3, sleep=3)

        def step7():
            # 7.进入消息页面：点击底部消息tab（等待1s），点击互动消息（等待1s）
            self.driver.touch(BY.text('消息'), wait_time=1)
            self.driver.touch(BY.text('互动消息'), wait_time=1)

        self.execute_performance_step('快手-关注页浏览-step1启动快手（等待5s）', 10, step1, sample_all_processes=True)
        self.execute_performance_step('快手-关注页浏览-step2进入首页：点击底部首页tab', 10, step2)
        self.execute_performance_step('快手-关注页浏览-step3进入关注页面：点击顶部关注tab（等待2s）', 10, step3)
        self.execute_performance_step('快手-关注页浏览-step4页面浏览：上下滑动3次（滑动间隔2s）', 10, step4)
        self.execute_performance_step('快手-关注页浏览-step5进入精选界面：点击底部朋友“精选”（等待3s）', 10, step5)
        self.execute_performance_step('快手-关注页浏览-step6上下滑动3次浏览视频（滑动间隔3s）', 10, step6)
        self.execute_performance_step(
            '快手-关注页浏览-step7进入消息页面：点击底部消息tab（等待1s），点击互动消息（等待1s）', 10, step7
        )
