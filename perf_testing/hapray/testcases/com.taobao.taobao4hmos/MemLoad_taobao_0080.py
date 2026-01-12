from hypium import BY

from hapray.core.perf_testcase import PerfTestCase


class MemLoad_taobao_0080(PerfTestCase):
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
            # 2.点击购物车
            tab_button = self.driver.find_all_components(BY.text('0'), 3)
            self.driver.touch(tab_button, wait_time=2)

        def step3():
            # 3.购物车上滑5次，每次停留2s
            self.swipes_up(swip_num=5, sleep=2)

        def step4():
            # 4.购物车下滑5次，每次停留2s
            self.swipes_down(swip_num=6, sleep=2)

        def step5():
            # 5.点击视频，等待2s
            tab_button = self.driver.find_all_components(BY.text('0'), 1)
            self.driver.touch(tab_button, wait_time=2)

        def step6():
            # 6.视频页面上滑5次，每次停留2s
            self.swipes_up(swip_num=5, sleep=2)

        def step7():
            # 7.视频页面下滑5次，每次停留2s
            self.swipes_down(swip_num=6, sleep=2)

        def step8():
            # 8.点击我的淘宝，等待2s
            tab_button = self.driver.find_all_components(BY.text('0'), -1)
            self.driver.touch(tab_button, wait_time=2)

        def step9():
            # 9.我的淘宝页上滑5次，每次停留2s
            self.swipes_up(swip_num=5, sleep=2)

        def step10():
            # 10.我的淘宝页下滑5次，每次停留2s
            self.swipes_down(swip_num=6, sleep=2)

        self.execute_performance_step('淘宝-闪购场景-step1启动淘宝（等待5s）', 10, step1)
        self.execute_performance_step('淘宝-闪购场景-step2点击购物车', 10, step2)
        self.execute_performance_step('淘宝-闪购场景-step3购物车上滑5次，每次停留2s', 15, step3)
        self.execute_performance_step('淘宝-闪购场景-step4购物车下滑5次，每次停留2s', 15, step4)
        self.execute_performance_step('淘宝-闪购场景-step5点击视频，等待2s', 10, step5)
        self.execute_performance_step('淘宝-闪购场景-step6视频页面上滑5次，每次停留2s', 15, step6)
        self.execute_performance_step('淘宝-闪购场景-step7视频页面下滑5次，每次停留2s', 15, step7)
        self.execute_performance_step('淘宝-闪购场景-step8点击我的淘宝，等待2s', 10, step8)
        self.execute_performance_step('淘宝-闪购场景-step9我的淘宝页上滑5次，每次停留2s', 15, step9)
        self.execute_performance_step('淘宝-闪购场景-step10我的淘宝页下滑5次，每次停留2s', 15, step10)
