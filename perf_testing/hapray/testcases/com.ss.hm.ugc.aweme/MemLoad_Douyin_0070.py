import time

from hypium import BY

from hapray.core.perf_testcase import PerfTestCase


class MemLoad_Douyin_0070(PerfTestCase):
    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(self.TAG, controllers)

        self._app_package = 'com.ss.hm.ugc.aweme'
        self._app_name = '抖音'
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
            # 1. 打开抖音，等待 5s
            self.start_app()

        def step2():
            # 2.进入拍照页面：点击“+”（等待2s），点击照片（等待2s）
            self.driver.touch((640, 2648), wait_time=2)
            self.driver.touch(BY.text('照片'), wait_time=2)

        def step3():
            # 3.进行拍照：点击拍照按钮（等待5s）
            self.driver.touch((640, 2307), wait_time=5)
            self.driver.check_component_exist(BY.text('下一步'))

        def step4():
            # 4.清空内容：返回（等待1s），点击清空内容（等待2s）
            self.driver.swipe_to_back()
            time.sleep(2)
            if self.driver.find_component(BY.text('清空内容')):
                self.driver.touch(BY.text('清空内容'), wait_time=2)
            self.driver.check_component_exist(BY.text('选择音乐'))

        self.execute_performance_step('抖音-拍照场景-step1打开抖音', 10, step1, sample_all_processes=True)
        self.execute_performance_step(
            '抖音-拍照场景-step2进入拍照页面：点击“+”（等待2s），点击照片（等待2s）', 10, step2
        )
        self.execute_performance_step('抖音-拍照场景-step3进行拍照：点击拍照按钮（等待5s）', 10, step3)
        self.execute_performance_step('抖音-拍照场景-step4清空内容：返回（等待1s），点击清空内容（等待2s）', 10, step4)
