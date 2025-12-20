import time

from hypium import BY

from hapray.core.perf_testcase import PerfTestCase


class PerfLoad_kuaishou_0010(PerfTestCase):
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

        # Step('启动被测应用')
        self.driver.start_app(self.app_package)
        self.driver.wait(5)
        time.sleep(2)

        def step1():
            # Step('快手首页上滑操作')
            self.swipes_up(swip_num=5, sleep=2)
            # Step('快手首页下滑操作')
            self.swipes_down(swip_num=5, sleep=2)

        self.execute_performance_step('快手-首页、评论区浏览-step1首页上下滑', 35, step1)

        self.driver.touch(BY.text('我'))
        time.sleep(2)

        self.driver.touch(BY.text('收藏'))
        time.sleep(2)

        # 点击收藏的第一个视频
        self.driver.touch(self.convert_coordinate(195, 1767))
        time.sleep(2)
        # 点击收藏的第一个视频
        self.driver.touch(self.convert_coordinate(997, 1468))
        time.sleep(2)

        def step2():
            self.swipes_up(swip_num=5, sleep=2)
            self.swipes_down(swip_num=5, sleep=2)

        self.execute_performance_step('快手-首页、评论区浏览-step2评论区上下滑', 35, step2)

        # 点击空白处退出评论区
        self.driver.touch(self.convert_coordinate(571, 364))
        time.sleep(2)

        def step3():
            self.swipes_up(swip_num=5, sleep=2)
            self.swipes_down(swip_num=5, sleep=2)

        self.execute_performance_step('快手-首页、评论区浏览-step3收藏视频浏览', 35, step3)
