import time

from hypium import BY

from hapray.core.perf_testcase import PerfTestCase


class MemLoad_zhifubao_0010(PerfTestCase):
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
            # 1. 启动支付宝(启动5s，停留2s)
            self.start_app(wait_time=5)
            time.sleep(2)

        def step2():
            # 2. 进入出现页面：点击出行(停留2s)
            self.driver.touch(BY.type('Text').text('出行'))
            time.sleep(2)

            # 3. 切换到地铁码页面：点击公交地铁(停留2s)
            self.touch_by_coordinates(120, 338, 2)

            # 4. 进入地铁码页面：点击地铁（等待2s），点击公交（等待2s）
            self.touch_by_coordinates(542, 554, 2)
            self.touch_by_coordinates(216, 554, 2)

            # 5. 切换到车页面：点击打车页面(停留2s)
            self.touch_by_coordinates(542, 338, 2)
            time.sleep(2)

            # 6. 打车页面浏览：上下滑动1次，间隔2s
            self.swipes_up(1, 2)
            self.swipes_down(1, 2)

        def step3():
            # 7. 返回应用首页
            for _i in range(5):
                if self.driver.find_component(BY.text('出行')) and self.driver.find_component(BY.text('扫一扫')):
                    break
                self.swipe_to_back()

        def step4():
            # 8. 退后台
            self.swipe_to_home(5)

        self.execute_performance_step('支付宝-出行场景-step1应用冷启动', 10, step1, sample_all_processes=True)
        self.execute_performance_step('支付宝-出行场景-step2出行页浏览', 30, step2)
        self.execute_performance_step('支付宝-出行场景-step3返回应用首页', 10, step3)
        self.execute_performance_step('支付宝-出行场景-step4应用退后台', 10, step4)
