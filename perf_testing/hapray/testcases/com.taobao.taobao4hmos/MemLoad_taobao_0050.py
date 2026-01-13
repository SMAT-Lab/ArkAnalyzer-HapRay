import time

from devicetest.utils.file_util import get_resource_path
from hypium import BY
from hypium.model.basic_data_type import UiParam

from hapray.core.perf_testcase import PerfTestCase


class MemLoad_taobao_0050(PerfTestCase):
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
            # 2.进入天猫超市：点击“天猫超市”（等待2s）
            self.driver.touch(BY.text('天猫超市'), wait_time=2)
            image_path = r'resource/com_taobao_taobao4hmos/cancel.jpeg'
            cancel_button = self.driver.find_image(image_path, mode='template', similarity=0.7)
            if cancel_button:
                self.driver.touch(cancel_button, wait_time=2)

        def step3():
            # 3.进入纸品清洁页面：点击上方纸品清洁（等待5s）
            for _i in range(5):
                zhipinqingjie_button = self.driver.find_component(BY.text('纸品清洁'))
                if zhipinqingjie_button:
                    self.driver.touch(zhipinqingjie_button, wait_time=5)
                    break
                self.driver.swipe(UiParam.LEFT, distance=30, start_point=(0.8, 0.62), swipe_time=0.2)
                time.sleep(2)

        def step4():
            # 4.页面浏览：上滑5次，下滑6次（间隔2s）
            self.swipes_up(swip_num=5, sleep=2)
            self.swipes_down(swip_num=6, sleep=2)

        def step5():
            # 5.将第一个商品加入购物车，返回淘宝购物首页：点击第一个商品，点击加入购物车（等待2s），再次点击加入购物车（等待2s），返回首页
            for _i in range(3):
                if self.driver.find_component(BY.text('为你推荐')):
                    break
                self.swipes_down(swip_num=1, sleep=2)
            x, y = self.driver.get_component_pos(BY.text('为你推荐'))
            self.driver.touch((x, y + 127), wait_time=2)
            self.driver.touch(BY.text('加入购物车'), wait_time=2)
            self.driver.touch((638, 2665), wait_time=2)
            self.driver.swipe_to_back()
            time.sleep(2)

        def step6():
            # 6.进入结算界面：点击购物车（等待2s），点击结算（等待2s）
            self.driver.touch_image(
                image_path_pc=get_resource_path('com_taobao_taobao4hmos/shopping_car2.jpeg'),
                similarity=0.7,
                wait_time=2,
            )
            self.driver.touch_image(
                image_path_pc=get_resource_path('com_taobao_taobao4hmos/check_out.jpeg'), similarity=0.7, wait_time=2
            )

        def step7():
            # 7.删除购物车：返回（等待1s），对商品左滑（等待1s），点击删除（等待1s）
            self.driver.swipe_to_back()
            time.sleep(1)
            self.driver.swipe(UiParam.LEFT, distance=40, start_point=(0.75, 0.36), swipe_time=0.2)
            time.sleep(1)
            self.driver.touch_image(
                image_path_pc=get_resource_path('com_taobao_taobao4hmos/deleted.jpeg'), similarity=0.7, wait_time=1
            )

        self.execute_performance_step('淘宝-天猫超市场景-step1启动淘宝（等待5s）', 10, step1)
        self.execute_performance_step('淘宝-天猫超市场景-step2进入天猫超市：点击“天猫超市”（等待2s）', 10, step2)
        self.execute_performance_step('淘宝-天猫超市场景-step3进入纸品清洁页面：点击上方纸品清洁（等待5s）', 20, step3)
        self.execute_performance_step('淘宝-天猫超市场景-step4页面浏览：上滑5次，下滑6次（间隔2s）', 30, step4)
        self.execute_performance_step(
            '淘宝-天猫超市场景-step5将第一个商品加入购物车，返回淘宝购物首页：点击第一个商品，点击加入购物车（等待2s），再次点击加入购物车（等待2s），返回首页',
            20,
            step5,
        )
        self.execute_performance_step(
            '淘宝-天猫超市场景-step6进入结算界面：点击购物车（等待2s），点击结算（等待2s）', 10, step6
        )
        self.execute_performance_step(
            '淘宝-天猫超市场景-step7删除购物车：返回（等待1s），对商品左滑（等待1s），点击删除（等待1s）', 10, step7
        )
