import time

from hypium import BY

from hapray.core.perf_testcase import PerfTestCase


class MemLoad_zhifubao_0050(PerfTestCase):
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
            # 2. 进入更多页面：点击更多（等待2s）
            self.driver.touch(BY.text('更多'))
            time.sleep(2)

        def step3():
            # 3. 进入医疗健康页面：点击‘医疗健康’（等待2s）
            self.driver.touch(BY.text('医疗健康'))
            time.sleep(2)

        def step4():
            # 4. 页面浏览：上下浏览1次（等待2s）
            self.swipes_up(swip_num=1, sleep=2, timeout=300)
            self.swipes_down(swip_num=1, sleep=2, timeout=300)

        def step5():
            # 5. 返回上一级：返回更多服务（等待2s）
            self.driver.swipe_to_back()
            time.sleep(2)

        def step6():
            # 6. 进入生活缴费页面：点击“生活缴费”（等待2s）
            self.driver.touch(BY.text('生活缴费'))
            time.sleep(2)

        def step7():
            # 7. 页面浏览：上下浏览1次（等待2s）
            self.swipes_up(swip_num=1, sleep=2, timeout=300)
            self.swipes_down(swip_num=1, sleep=2, timeout=300)

        def step8():
            # 8. 返回上一级：返回更多服务（等待2s）
            self.driver.swipe_to_back()
            time.sleep(2)

        def step9():
            # 9. 进入蚂蚁森林页面：点击“蚂蚁森林”（等待2s）

            for _i in range(6):
                if self.driver.find_component(BY.text('蚂蚁森林')):
                    break
                self.swipes_up(swip_num=2, sleep=2, timeout=300)

            self.driver.touch(BY.text('蚂蚁森林'))
            if self.driver.find_component(BY.text('蚂蚁森林')):
                x, y = self.driver.get_component_bound(BY.text('查看《蚂蚁森林用户须知》'))
                self.driver.touch((x, y - 140), wait_time=2)
            time.sleep(2)

        def step10():
            # 10. 页面浏览：上下浏览1次（等待2s）
            self.swipes_up(swip_num=1, sleep=2, timeout=300)
            self.swipes_down(swip_num=1, sleep=2, timeout=300)

        def step11():
            # 11. 返回上一级：返回更多服务（等待2s）
            self.driver.swipe_to_back()
            time.sleep(2)

        self.execute_performance_step('支付宝-收付款场景-step1应用冷启动', 10, step1, sample_all_processes=True)
        self.execute_performance_step('支付宝-收付款场景-step2进入更多页面：点击更多', 10, step2)
        self.execute_performance_step('支付宝-收付款场景-step3进入医疗健康页面：点击‘医疗健康’', 10, step3)
        self.execute_performance_step('支付宝-收付款场景-step4页面浏览：上下浏览1次', 10, step4)
        self.execute_performance_step('支付宝-收付款场景-step5返回上一级：返回更多服务', 10, step5)
        self.execute_performance_step('支付宝-收付款场景-step6进入生活缴费页面：点击“生活缴费”', 10, step6)
        self.execute_performance_step('支付宝-收付款场景-step7页面浏览：上下浏览1次', 10, step7)
        self.execute_performance_step('支付宝-收付款场景-step8返回上一级：返回更多服务', 10, step8)
        self.execute_performance_step('支付宝-收付款场景-step9进入蚂蚁森林页面：点击“蚂蚁森林”', 10, step9)
        self.execute_performance_step('支付宝-收付款场景-step10页面浏览：上下浏览1次', 10, step10)
        self.execute_performance_step('支付宝-收付款场景-step11返回上一级：返回更多服务', 10, step11)
