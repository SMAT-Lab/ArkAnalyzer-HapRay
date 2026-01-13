from hypium import BY

from hapray.core.perf_testcase import PerfTestCase


class MemLoad_taobao_0060(PerfTestCase):
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
            # 2.进入相册页面：点击搜索框相机按钮（等待2s）
            x, y = self.driver.get_component_pos(BY.text('搜索'))
            self.driver.touch((x - 186, y), wait_time=2)

        def step3():
            # 3.选择图片：点击所有相册（等待1s），点击“购物”（等待2s），选择第一张图片（等待2s），点击完成（等待2s）
            self.driver.touch((265, 2363), wait_time=2)
            self.driver.touch(BY.type('CachedImage'), wait_time=2)

        def step4():
            # 4.搜索结果浏览：向上滑动3次（间隔2s）
            self.swipes_up(swip_num=3, sleep=2)

        self.execute_performance_step('淘宝-购物车浏览场景-step1启动淘宝（等待5s）', 10, step1)
        self.execute_performance_step('淘宝-购物车浏览场景-step2进入相册页面：点击搜索框相机按钮（等待2s）', 10, step2)
        self.execute_performance_step(
            '淘宝-购物车浏览场景-step3选择图片：点击所有相册（等待1s），点击“购物”（等待2s），选择第一张图片（等待2s），点击完成（等待2s）',
            10,
            step3,
        )
        self.execute_performance_step('淘宝-购物车浏览场景-step4搜索结果浏览：向上滑动3次（间隔2s）', 10, step4)
