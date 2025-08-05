# coding: utf-8
import time

from hypium.model import UiParam
from hypium import BY

from hapray.core.perf_testcase import PerfTestCase


class ResourceUsage_PerformanceDynamic_sina_0010(PerfTestCase):

    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(self.TAG, controllers)

        self._app_package = 'com.sina.news.hm.next'
        self._app_name = '新浪新闻'
        # 原始采集设备的屏幕尺寸（Mate 60 Pro）
        self.source_screen_width = 1260
        self.source_screen_height = 2720

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
        self.touch_by_text('跳过', 2)

        def step1():
            self.touch_by_text('热榜', 2)
            self.touch_by_text('体育', 2)
            xpath = '//root/Column/Tabs/Swiper/TabContent/Column/Column/Column/__Common__/Column/Tabs/TabBar'
            tabs = self.driver.find_component(BY.xpath(xpath))
            for _ in range(2):
                self.driver.swipe(UiParam.RIGHT, area=tabs, distance=60, start_point=(0.4, 0.1),
                                  swipe_time=0.4)
                time.sleep(1)
            self.touch_by_text('要闻', 2)

        def step2():
            self.touch_by_text('专题', 2)

            # 向上滑动
            self.swipes_up(swip_num=5, sleep=2)
            self.driver.swipe_to_back()
            time.sleep(1)

            self.swipes_up(swip_num=1, sleep=2)
            self.touch_by_text('专题', 2)
            # 向上滑动
            self.swipes_up(swip_num=5, sleep=2)

        self.execute_performance_step("新浪新闻-新闻浏览场景-step1栏目切换", 10, step1)
        self.execute_performance_step("新浪新闻-新闻浏览场景-step2新闻专题浏览", 30, step2)
