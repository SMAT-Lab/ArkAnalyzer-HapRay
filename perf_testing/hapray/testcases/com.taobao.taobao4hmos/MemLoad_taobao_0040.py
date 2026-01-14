from hypium import BY

from hapray.core.perf_testcase import PerfTestCase


class MemLoad_taobao_0040(PerfTestCase):
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
            # 2.进入购物车：点击购物车（等待2s）
            tab_button = self.driver.find_all_components(BY.text('0'), 3)
            self.driver.touch(tab_button, wait_time=2)

        def step3():
            # 3.商品详情浏览：点击“HUAWEI Mate 70 Pro”（等待2s），上滑3次，下滑4次（间隔2s）
            self.driver.touch((641, 589), wait_time=2)
            self.swipes_up(swip_num=3, sleep=2)
            self.swipes_down(swip_num=4, sleep=2)

        def step4():
            # 4.商品图片浏览：点击商品图片（等待2s），左右滑动3次（间隔2s）
            com = self.driver.find_components(BY.text('图集'))
            if com:
                self.driver.touch(com, wait_time=2)
            self.driver.touch((640, 640), wait_time=2)
            self.swipes_left(swip_num=3, sleep=2)
            self.swipes_right(swip_num=3, sleep=2)

        self.execute_performance_step('淘宝-购物车浏览场景-step1启动淘宝（等待5s）', 10, step1)
        self.execute_performance_step('淘宝-购物车浏览场景-step2进入购物车：点击购物车（等待2s）', 10, step2)
        self.execute_performance_step(
            '淘宝-购物车浏览场景-step3商品详情浏览：点击“HUAWEI Mate 70 Pro”（等待2s），上滑3次，下滑4次（间隔2s）',
            20,
            step3,
        )
        self.execute_performance_step(
            '淘宝-购物车浏览场景-step4商品图片浏览：点击商品图片（等待2s），左右滑动3次（间隔2s））', 20, step4
        )
