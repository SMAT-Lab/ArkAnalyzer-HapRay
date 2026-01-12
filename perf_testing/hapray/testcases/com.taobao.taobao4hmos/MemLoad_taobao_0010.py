from hypium import BY

from hapray.core.perf_testcase import PerfTestCase


class MemLoad_taobao_0010(PerfTestCase):
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
            # 2.首页浏览：点击首页（等待2s），上下滑动5次（间隔2s）
            self.driver.touch(BY.text('0'), wait_time=2)
            self.swipes_up(swip_num=5, sleep=2)
            self.swipes_down(swip_num=5, sleep=2)

        self.execute_performance_step('淘宝-首页浏览场景-step1启动淘宝（等待5s）', 10, step1)
        self.execute_performance_step(
            '淘宝-首页浏览场景-step2首页浏览：点击首页（等待2s），上下滑动5次（间隔2s）', 30, step2
        )
