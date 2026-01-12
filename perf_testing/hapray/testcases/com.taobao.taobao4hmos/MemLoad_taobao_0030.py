import time

from hypium import BY

from hapray.core.perf_testcase import PerfTestCase


class MemLoad_taobao_0030(PerfTestCase):
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
            # 2.点击搜索框、输入搜索内容：点击搜索框（等待2s），输入“华为手机”（等待1s）
            x, y = self.driver.get_component_pos(BY.text('搜索'))
            self.driver.touch((x - 566, y), wait_time=2)

            self.driver.input_text(BY.type('TextInput'), '华为手机')
            time.sleep(1)

        def step3():
            # 3.进行搜索：点击搜索（等待4s）
            self.driver.touch(BY.text('搜索'), wait_time=3)
            if self.driver.find_component(BY.text('进店')) is None:
                self.driver.touch((1152, 224))

        def step4():
            # 4.搜索结果浏览：上滑5次、下滑6次（间隔2s）
            self.swipes_up(swip_num=5, sleep=2)
            self.swipes_down(swip_num=6, sleep=2)

        def step5():
            # 5.销量排序：点击“销量”（等待2s）
            self.driver.touch(BY.text('销量'), wait_time=2)

        self.execute_performance_step('淘宝-搜索商品场景-step1启动淘宝（等待5s）', 10, step1)
        self.execute_performance_step(
            '淘宝-搜索商品场景-step2点击搜索框、输入搜索内容：点击搜索框（等待2s），输入“华为手机”（等待1s）', 10, step2
        )
        self.execute_performance_step('淘宝-搜索商品场景-step3进行搜索：点击搜索（等待4s）', 10, step3)
        self.execute_performance_step('淘宝-搜索商品场景-step4搜索结果浏览：上滑5次、下滑6次（间隔2s）', 30, step4)
        self.execute_performance_step('淘宝-搜索商品场景-step5销量排序：点击“销量”（等待2s）', 10, step5)
