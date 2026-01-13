import time

from hypium import BY
from hypium.model.basic_data_type import MatchPattern

from hapray.core.perf_testcase import PerfTestCase


class MemLoad_meituan_0040(PerfTestCase):
    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(self.TAG, controllers)

        self._app_package = 'com.sankuai.hmeituan'
        self._app_name = '美团'
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

        def step1():
            # 1.打开美团，等待5s
            self.driver.start_app(self.app_package)
            self.driver.wait(5)
            time.sleep(2)

        def step2():
            # 2.点击外卖，等待2s
            self.driver.touch(BY.text('外卖'), wait_time=2)

        def step3():
            # 3.外卖页上滑5次，下滑5次，每次间隔2s
            self.swipes_up(swip_num=5, sleep=2)
            self.swipes_down(swip_num=5, sleep=2)

        def step4():
            # 4.搜索“蜜雪冰城（未来科技城（华为）店）”，点击搜索，等待2s
            x, y = self.driver.get_component_pos(BY.text('搜索'))
            self.driver.touch((x - 299, y), wait_time=2)
            self.driver.input_text(BY.type('TextInput'), '蜜雪冰城')
            time.sleep(2)
            self.driver.touch(BY.text('搜索'), wait_time=2)

        def step5():
            # 5.点击进入店铺，等待2s
            com = self.driver.find_all_components(BY.text('蜜雪冰城', MatchPattern.STARTS_WITH), 2)
            self.driver.touch(com, wait_time=2)

        def step6():
            # 6.店铺内容上滑5次，下滑5次，每次间隔2s
            self.swipes_up(swip_num=5, sleep=2)
            self.swipes_down(swip_num=5, sleep=2)

        def step7():
            # 7.搜索“棒打鲜橙”，点击棒打鲜橙商品，等待2s
            self.driver.touch(BY.text('搜索'), wait_time=2)
            self.driver.input_text(BY.type('TextInput'), '棒打鲜橙')
            time.sleep(2)
            com = self.driver.find_all_components(BY.text('棒打鲜橙'), 1)
            self.driver.touch(com, wait_time=2)

        def step8():
            # 8.点击选规格（默认），加入购物车3杯
            comp = self.driver.find_all_components(BY.text('选规格'), -1)
            self.driver.touch(comp, wait_time=2)
            if self.driver.wait_for_component(BY.text('加入购物车')):
                self.driver.touch(BY.text('加入购物车'), wait_time=2)
                for _i in range(3):
                    comp = self.driver.find_component(BY.text('总计'))
                    x, y = self.driver.get_component_pos(comp)
                    self.driver.touch((x + 802, y - 10), wait_time=2)
            else:
                for _i in range(4):
                    comp = self.driver.find_all_components(BY.text('￥'), -1)
                    x, y = self.driver.get_component_pos(comp)
                    self.driver.touch((x + 1004, y), wait_time=2)

        def step9():
            # 9.点击购物车-点击空白处退出购物车，等待2s
            comp = self.driver.find_component(BY.text('总计'))
            x, y = self.driver.get_component_pos(comp)
            self.driver.touch((x + 439, y + 242), wait_time=2)

        def step10():
            # 10.点击去结算，等待2s
            self.driver.touch(BY.text('去结算'), wait_time=2)

        def step11():
            # 11.点击提交订单至付款界面，等待2s
            self.driver.touch(BY.text('提交订单'), wait_time=2)
            if self.driver.wait_for_component(BY.text('选择收货地址')):
                x, y = self.driver.get_component_pos(BY.text('选择收货地址'))
                self.driver.touch((x + 63, y + 201), wait_time=2)
                self.driver.touch(BY.text('提交订单'), wait_time=2)
            if self.driver.wait_for_component(BY.text('需要餐具')):
                self.driver.touch(BY.text('需要餐具'), wait_time=2)
                x, y = self.driver.get_component_pos(BY.text('后续该地址下单，都需要餐具'))
                self.driver.touch((x + 706, y), wait_time=2)
                self.driver.touch(BY.text('确认并提交订单'), wait_time=2)

        def step12():
            # 12.返回确认离开付款界面，点击取消订单，等待2s
            self.driver.swipe_to_back()
            time.sleep(2)
            self.driver.touch(BY.text('确认离开'), wait_time=2)
            self.driver.touch(BY.text('取消订单'), wait_time=2)
            if self.driver.find_all_components(BY.text('取消订单')):
                comp = self.driver.find_all_components(BY.text('取消订单'), -1)
                self.driver.touch(comp, wait_time=2)

        self.execute_performance_step('美团-外卖购买浏览场景-step1打开美团，等待5s', 10, step1)
        self.execute_performance_step('美团-外卖购买浏览场景-step2点击外卖，等待2s', 5, step2)
        self.execute_performance_step('美团-外卖购买浏览场景-step3外卖页上滑5次，下滑5次，每次间隔2s', 30, step3)
        self.execute_performance_step(
            '美团-外卖购买浏览场景-step4搜索“蜜雪冰城（未来科技城（华为）店）”，点击搜索，等待2s', 10, step4
        )
        self.execute_performance_step('美团-外卖购买浏览场景-step5点击进入店铺，等待2s', 5, step5)
        self.execute_performance_step('美团-外卖购买浏览场景-step6店铺内容上滑5次，下滑5次，每次间隔2s', 30, step6)
        self.execute_performance_step('美团-外卖购买浏览场景-step7搜索“棒打鲜橙”，点击棒打鲜橙商品，等待2s', 10, step7)
        self.execute_performance_step('美团-外卖购买浏览场景-step8点击选规格（默认），加入购物车3杯', 10, step8)
        self.execute_performance_step('美团-外卖购买浏览场景-step9点击购物车-点击空白处退出购物车，等待2s', 10, step9)
        self.execute_performance_step('美团-外卖购买浏览场景-step10点击去结算，等待2s', 10, step10)
        self.execute_performance_step('美团-外卖购买浏览场景-step11点击提交订单至付款界面，等待2s', 10, step11)
        self.execute_performance_step(
            '美团-外卖购买浏览场景-step12返回确认离开付款界面，点击取消订单，等待2s', 10, step12
        )
