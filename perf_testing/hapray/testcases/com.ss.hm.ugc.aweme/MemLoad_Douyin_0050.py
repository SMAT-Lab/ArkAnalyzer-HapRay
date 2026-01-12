from hypium import BY

from hapray.core.perf_testcase import PerfTestCase


class MemLoad_Douyin_0050(PerfTestCase):
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
            # 2.进入抖音商城：点击商城（等待2s）
            self.driver.touch(BY.text('商城'), wait_time=2)

        def step3():
            # 3.商城页面浏览：先上滑10次（滑动间隔2s），再下滑5次（滑动间隔2s）
            self.swipes_up(3, 3)
            self.swipes_down(3, 3)

        def step4():
            # 4.搜索商品：点击搜索框（等待1s），输入“清风官方旗舰店”（等待1s），点击搜索（等待1s）
            self.driver.touch((321, 348), wait_time=1)
            self.driver.input_text((0.25, 0.07), '清风官方旗舰店')
            self.driver.touch(BY.text('搜索'), wait_time=1)

        def step5():
            # 5.进入商品页面：点击第一个商品（等待2s）
            self.driver.check_component_exist(BY.text('销量'), wait_time=1)
            self.driver.touch((326, 762), wait_time=2)

        def step6():
            # 6.商品详情浏览：上下滑动3次（滑动间隔2s）
            self.swipes_up(3, 2)
            self.swipes_down(3, 2)

        self.execute_performance_step('抖音-商品浏览场景-step1打开抖音', 10, step1, sample_all_processes=True)
        self.execute_performance_step('抖音-商品浏览场景-step2进入抖音商城：点击商城（等待2s）', 10, step2)
        self.execute_performance_step(
            '抖音-商品浏览场景-step3商城页面浏览：先上滑10次（滑动间隔2s），再下滑5次（滑动间隔2s）', 10, step3
        )
        self.execute_performance_step(
            '抖音-商品浏览场景-step4搜索商品：点击搜索框（等待1s），输入“清风官方旗舰店”（等待1s），点击搜索（等待1s）',
            10,
            step4,
        )
        self.execute_performance_step('抖音-商品浏览场景-step5进入商品页面：点击第一个商品（等待2s）', 10, step5)
        self.execute_performance_step('抖音-商品浏览场景-step6商品详情浏览：上下滑动3次', 10, step6)
