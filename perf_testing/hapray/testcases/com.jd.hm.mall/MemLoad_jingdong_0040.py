import time

from hypium import BY
from hypium.model.basic_data_type import MatchPattern

from hapray.core.perf_testcase import PerfTestCase


class MemLoad_jingdong_0040(PerfTestCase):
    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(self.TAG, controllers)

        self._app_package = 'com.jd.hm.mall'
        self._app_name = '京东'
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

        def step1():
            # 1.启动京东（等待5s）
            self.driver.start_app(self.app_package)
            self.driver.wait(5)

        def step2():
            # 2.进入购物车：点击购物车（等待2s）
            self.driver.touch(BY.text('购物车'), wait_time=2)

        def step3():
            # 3.商品详情浏览：点击“HUAWEI Mate 70 Pro”（等待2s），上滑3次，下滑4次（间隔2s）
            self.driver.touch(BY.text('HUAWEI Mate 70 Pro', MatchPattern.STARTS_WITH), wait_time=2)
            self.swipes_up(swip_num=3, sleep=2)
            self.swipes_down(swip_num=4, sleep=2)

        def step4():
            # 4.商品图片浏览：点击商品图片（等待2s），左右滑动3次（间隔2s）
            x, y = self.driver.get_component_pos(BY.type('Swiper'))
            self.driver.touch((x + 120, y), wait_time=2)
            self.swipes_left(swip_num=3, sleep=2)
            self.swipes_right(swip_num=3, sleep=2)

        def step5():
            # 5.返回商品详情页：返回（等待2s）
            self.driver.swipe_to_back()
            time.sleep(2)

        def step6():
            # 6.进入全部评价页面：向上滑动一次（等待2s），点击评价（等待2s），点击买家评价（等待2s）
            self.swipes_up(swip_num=1, sleep=2)
            self.driver.touch(BY.text('大家评'), wait_time=2)
            self.driver.touch(BY.text('买家评价', MatchPattern.STARTS_WITH), wait_time=2)

        def step7():
            # 7.评价页面浏览：上下滑动5次（间隔2s）
            self.driver.check_component_exist(BY.text('回头客', MatchPattern.STARTS_WITH))
            self.swipes_up(swip_num=5, sleep=2)
            self.swipes_down(swip_num=5, sleep=2)

        self.execute_performance_step('京东-购物车场景-step1启动京东（等待5s）', 10, step1, sample_all_processes=True)
        self.execute_performance_step('京东-购物车场景-step2进入购物车：点击购物车（等待2s）', 10, step2)
        self.execute_performance_step(
            '京东-购物车场景-step3商品详情浏览：点击“HUAWEI Mate 70 Pro”（等待2s），上滑3次，下滑4次（间隔2s）',
            30,
            step3,
        )
        self.execute_performance_step(
            '京东-购物车场景-step4商品图片浏览：点击商品图片（等待2s），左右滑动3次（间隔2s）', 20, step4
        )
        self.execute_performance_step('京东-购物车场景-step5返回商品详情页：返回（等待2s）', 10, step5)
        self.execute_performance_step(
            '京东-购物车场景-step6进入全部评价页面：向上滑动一次（等待2s），点击评价（等待2s），点击买家评价（等待2s）',
            10,
            step6,
        )
        self.execute_performance_step('京东-购物车场景-step7评价页面浏览：上下滑动5次（间隔2s）', 30, step7)
