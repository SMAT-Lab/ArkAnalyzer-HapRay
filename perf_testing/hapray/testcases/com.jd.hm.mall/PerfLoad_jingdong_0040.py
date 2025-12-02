import time

from hypium import BY

from hapray.core.perf_testcase import PerfTestCase


class PerfLoad_jingdong_0040(PerfTestCase):
    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(self.TAG, controllers)

        self._app_package = 'com.jd.hm.mall'
        self._app_name = '京东'
        # 原始采集设备的屏幕尺寸（Mate 60）
        self.source_screen_width = 1216
        self.source_screen_height = 2688

    @property
    def app_package(self) -> str:
        return self._app_package

    @property
    def app_name(self) -> str:
        return self._app_name

    def process(self):
        self.driver.swipe_to_home()

        # Step('启动京东应用')
        self.driver.start_app(self.app_package)
        self.driver.wait(5)
        time.sleep(3)

        def step1():
            # 点击搜索框
            self.driver.touch(self.convert_coordinate(608, 315))
            time.sleep(2)

            # 搜索华为手机
            search_coords = self.convert_coordinate(475, 198)
            self.driver.input_text(search_coords, '华为手机')
            self.driver.touch(BY.text('搜索'))
            time.sleep(2)

            # Step('搜索结果页浏览，上滑操作')
            self.swipes_up(swip_num=5, sleep=2)
            # Step('搜索结果页浏览，下滑操作')
            self.swipes_down(swip_num=5, sleep=2)

        self.execute_performance_step('京东-搜索商品购物，查看商品图片场景-step1搜索并上下滑动搜索页面', 30, step1)
