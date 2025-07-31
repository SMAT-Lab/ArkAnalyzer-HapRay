# coding: utf-8
from hypium import BY
from hapray.core.perf_testcase import PerfTestCase


class ResourceUsage_PerformanceDynamic_sina_0020(PerfTestCase):

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

        def step1():
            # 根据条件点击控件
            self.driver.touch(BY.text('北京强降雨已造成30人死亡 北方此轮降雨何时结束？最新情况→'))
            self.driver.wait(0.5)
            # 根据条件点击控件
            self.driver.touch(BY.text('北京强降雨已造成30人死亡 北方此轮降雨何时结束？最新情况→'))
            self.driver.wait(0.5)

            # 向上滑动
            self.swipes_up(swip_num=5, sleep=2)


        self.execute_performance_step("新浪新闻等待页面加载完成。", 30, step1)
