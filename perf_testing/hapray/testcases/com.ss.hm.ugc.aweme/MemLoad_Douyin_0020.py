import time

from hypium import BY
from hypium.model.basic_data_type import UiParam

from hapray.core.perf_testcase import PerfTestCase


class MemLoad_Douyin_0020(PerfTestCase):
    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(self.TAG, controllers)

        self._app_package = 'com.ss.hm.ugc.aweme'
        self._app_name = '抖音'
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
            # 1. 打开抖音，等待 5s
            self.start_app()

        def step2():
            # 2.进入热点页面：点击顶部热点tab（等待2s）
            for _i in range(3):
                if self.driver.find_component(BY.text('热点')):
                    break
                self.driver.swipe(UiParam.RIGHT, distance=60, start_point=(0.16, 0.08))
                time.sleep(1)
            self.driver.touch(BY.text('热点'), wait_time=2)

        def step3():
            # 3.页面浏览：上下滑动3次（滑动间隔3s）
            self.swipes_up(3, 3)
            self.swipes_down(3, 3)

        def step4():
            # 4.进入关注页面：点击顶部关注tab（等待2s）
            for _i in range(3):
                if self.driver.find_component(BY.key('home-top-tab-text-homepage_follow')):
                    break
                self.driver.swipe(UiParam.LEFT, distance=60, start_point=(0.71, 0.08))
                time.sleep(1)
            self.driver.touch(BY.key('home-top-tab-text-homepage_follow'), wait_time=2)

        def step5():
            # 5.页面浏览：上下滑动3次（滑动间隔3s）
            self.swipes_up(3, 3)
            self.swipes_down(3, 3)

        def step6():
            # 6.进入朋友界面：点击底部朋友tab（等待3s）
            self.driver.swipe(BY.text('朋友'), swipe_time=3)
            self.driver.check_component_exist(BY.text('发现通讯录朋友'))

        def step7():
            # 7.进入消息页面：点击底部消息tab（等待3s）
            self.driver.touch(BY.text('消息'), wait_time=3)
            self.driver.check_component_exist(BY.text('互动消息'))

        self.execute_performance_step('抖音-热点浏览场景-step1打开抖音', 10, step1, sample_all_processes=True)
        self.execute_performance_step('抖音-热点浏览场景-step2进入热点页面：点击顶部热点tab', 10, step2)
        self.execute_performance_step('抖音-热点浏览场景-step3页面浏览：上下滑动3次', 10, step3)
        self.execute_performance_step('抖音-热点浏览场景-step4进入关注页面：点击顶部关注tab', 10, step4)
        self.execute_performance_step('抖音-热点浏览场景-step5页面浏览：上下滑动3次', 10, step5)
        self.execute_performance_step('抖音-热点浏览场景-step6进入朋友界面：点击底部朋友tab', 10, step6)
        self.execute_performance_step('抖音-热点浏览场景-step7进入消息页面：点击底部消息tab', 10, step7)
