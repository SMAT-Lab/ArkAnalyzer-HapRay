import time

from hypium import BY

from hapray.core.perf_testcase import PerfTestCase


class MemLoad_kuaishou_0060(PerfTestCase):
    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(self.TAG, controllers)

        self._app_package = 'com.kuaishou.hmapp'
        self._app_name = '快手'
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
            # 1.启动快手（等待5s）
            self.driver.start_app(self.app_package)
            self.driver.wait(5)
            time.sleep(5)

        def step2():
            # 2.进入拍视频页面：点击“+”（等待2s）
            self.driver.touch((0.50, 0.94), wait_time=2)

        def step3():
            # 3.进行视频录制：点击录制按钮，等待5s，点击停止录像按钮（等待2s）
            self.driver.touch(BY.key('photo_capture'))
            time.sleep(5)
            self.driver.touch(BY.key('photo_capture'), wait_time=2)

        def step4():
            # 4.返回拍摄界面：侧滑返回（等待2s）
            for _i in range(3):
                if self.driver.find_component(BY.text('选择音乐')):
                    break
                self.driver.swipe_to_back()
                time.sleep(2)

        self.execute_performance_step('快手-录制视频-step1启动快手（等待5s）', 10, step1, sample_all_processes=True)
        self.execute_performance_step('快手-录制视频-step2进入拍视频页面：点击“+”（等待2s）', 10, step2)
        self.execute_performance_step(
            '快手-录制视频-step3进行视频录制：点击录制按钮，等待5s，点击停止录像按钮（等待2s）', 10, step3
        )
        self.execute_performance_step('快手-录制视频-step4返回拍摄界面：侧滑返回（等待2s）', 10, step4)
