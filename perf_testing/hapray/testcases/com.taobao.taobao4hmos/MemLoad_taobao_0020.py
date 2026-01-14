import time

from hypium import BY
from hypium.model.basic_data_type import MatchPattern

from hapray.core.perf_testcase import PerfTestCase


class MemLoad_taobao_0020(PerfTestCase):
    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(self.TAG, controllers)

        self._app_package = 'com.taobao.taobao4hmos'
        self._app_name = '淘宝'
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
            # 1.启动淘宝（等待5s）
            self.driver.start_app(self.app_package)
            self.driver.wait(5)
            image_path = r'resource/com_taobao_taobao4hmos/cancel.jpeg'
            cancel_button = self.driver.find_image(image_path, mode='template', similarity=0.7)
            if cancel_button:
                self.driver.touch(cancel_button, wait_time=2)

        def step2():
            # 2.点击闪购，进入闪购页面（等待2s）
            self.driver.touch(BY.text('闪购'), wait_time=2)
            image_path = r'resource/com_taobao_taobao4hmos/cancel.jpeg'
            cancel_button = self.driver.find_image(image_path, mode='template', similarity=0.7)
            if cancel_button:
                self.driver.touch(cancel_button, wait_time=2)

        def step3():
            # 3.定位选择“武汉未来智汇城”（等待2s）
            dingwei = self.driver.find_all_components(BY.type('button'), 0)
            if dingwei is None:
                dingwei = (321, 472)
            self.driver.touch(dingwei, wait_time=2)
            com = self.driver.find_components(BY.text('未来智汇城', MatchPattern.CONTAINS))
            if com is None:
                self.driver.touch(BY.text('当前收货地址', MatchPattern.CONTAINS), wait_time=2)
            self.driver.touch(BY.text('未来智汇城', MatchPattern.CONTAINS), wait_time=2)

        def step4():
            # 4.搜索“蜜雪冰城（未来科技城（华为）店）”（等待3s）
            x, y = self.driver.get_component_pos(BY.text('搜索'))
            self.driver.touch((x - 566, y), wait_time=2)

            self.driver.input_text(BY.type('TextInput'), '蜜雪冰城（未来科技城（华为）店）')
            time.sleep(2)
            x, y = self.driver.get_component_pos(BY.text('TextInput'))
            self.driver.touch((x + 601, y), wait_time=3)

        def step5():
            # 5.店铺内搜索“冰鲜柠檬水”，点击进入该商品（等待2s）
            comp = self.driver.find_all_components(BY.text('蜜雪冰城（未来科技城（华为）店）'), -1)
            self.driver.touch(comp, wait_time=2)

            x, y = self.driver.get_component_pos(BY.text('收藏'))
            self.driver.touch((x - 313, y), wait_time=2)

            self.driver.input_text(BY.type('textField'), '冰鲜柠檬水')
            time.sleep(2)
            self.driver.touch(BY.text('搜索'), wait_time=3)
            self.driver.touch(BY.text('选规格'), wait_time=2)

        def step6():
            # 6.加入购物车4杯
            self.swipes_up(swip_num=2, sleep=2)

            x, y = self.driver.get_component_pos(BY.text('1'))
            for _i in range(3):
                self.driver.touch((x + 120, y), wait_time=2)

            self.driver.touch(BY.text('加入购物车'), wait_time=2)

        def step7():
            # 7.点击去结算（等待2s）
            self.driver.touch(BY.text('去结算'), wait_time=2)

        def step8():
            # 8.地址默认“武汉未来智汇城A10栋”，点击提交订单（需要餐具，商家依据餐量提供）
            dizhi = self.driver.find_component(BY.text('请选择收货地址'))
            if dizhi:
                self.driver.touch(dizhi, wait_time=2)

            peisong = self.driver.find_component(BY.text('外卖配送'))
            if peisong:
                x, y = self.driver.get_component_pos(BY.text('外卖配送'))
                self.driver.touch((x, y + 137), wait_time=2)

            x, y = self.driver.get_component_pos(BY.text('选择收货地址'))
            self.driver.touch((x, y + 200), wait_time=2)

            self.driver.touch(BY.text('提交订单'), wait_time=2)

            comp = self.driver.find_all_components(BY.text('需要餐具，商家依据餐量提供'), -1)
            self.driver.touch(comp, wait_time=2)

        def step9():
            # 9.退出该页面，取消订单
            self.driver.swipe_to_back()
            if self.driver.find_component(BY.text('放弃')):
                self.driver.touch(BY.text('放弃'), wait_time=2)
            self.driver.touch(BY.text('取消订单'), wait_time=2)
            self.driver.touch(BY.text('仍要取消'), wait_time=2)

        self.execute_performance_step('淘宝-闪购场景-step1启动淘宝（等待5s）', 10, step1)
        self.execute_performance_step('淘宝-闪购场景-step2点击闪购，进入闪购页面（等待2s）', 10, step2)
        self.execute_performance_step('淘宝-闪购场景-step3定位选择“武汉未来智汇城”（等待2s）', 10, step3)
        self.execute_performance_step('淘宝-闪购场景-step4搜索“蜜雪冰城（未来科技城（华为）店）”（等待3s）', 10, step4)
        self.execute_performance_step('淘宝-闪购场景-step5店铺内搜索“冰鲜柠檬水”，点击进入该商品（等待2s）', 20, step5)
        self.execute_performance_step('淘宝-闪购场景-step6加入购物车4杯', 20, step6)
        self.execute_performance_step('淘宝-闪购场景-step7点击去结算（等待2s）', 10, step7)
        self.execute_performance_step(
            '淘宝-闪购场景-step8地址默认“武汉未来智汇城A10栋”，点击提交订单（需要餐具，商家依据餐量提供）', 20, step8
        )
        self.execute_performance_step('淘宝-闪购场景-step9退出该页面，取消订单', 10, step9)
