import time

from hypium import BY

from hapray.core.perf_testcase import PerfTestCase


class ResourceUsage_PerformanceDynamic_zhifubao_0040(PerfTestCase):
    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(self.TAG, controllers)

        self._app_package = 'com.alipay.mobile.client'
        self._app_name = '支付宝'
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
            # 点击视频
            self.driver.touch(BY.type('Text').text('直播'))
            time.sleep(2)

            # 上滑5次，间隔5s
            self.swipes_up(swip_num=5, sleep=5)

        def step2():
            # 上滑5次，间隔3s
            self.swipes_up(swip_num=5, sleep=3)
            # 上滑5次，间隔3s
            self.swipes_down(swip_num=5, sleep=3)

        self.driver.start_app(self.app_package)
        self.driver.wait(5)

        # 点击视频
        self.driver.touch(BY.type('Text').text('视频'))
        time.sleep(2)

        self.execute_performance_step('支付宝-视频播放场景-step1视频直播滑动浏览', 35, step1)
        # 退出直播进入短剧
        self.touch_by_coordinates(671, 968, 1)
        self.driver.touch(BY.key('close-closeBtn'))
        time.sleep(3)
        self.swipes_right(1, 2)
        self.swipes_up(7, 2)
        self.swipes_down(7, 2)

        self.execute_performance_step('支付宝-视频播放场景-step2短剧页面浏览', 40, step2)
