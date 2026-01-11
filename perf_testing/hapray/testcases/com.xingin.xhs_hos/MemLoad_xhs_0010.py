from hypium import BY

from hapray.core.perf_testcase import PerfTestCase


class MemLoad_xhs_0010(PerfTestCase):
    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(self.TAG, controllers)

        self._app_package = 'com.xingin.xhs_hos'
        self._app_name = '小红书'
        # 原始采集设备的屏幕尺寸（Mate 60 Pro）
        self.source_screen_width = 1260
        self.source_screen_height = 2720

    @property
    def app_package(self) -> str:
        return self._app_package

    @property
    def app_name(self) -> str:
        return self._app_name

    def process(self):
        def step1():
            # 1.启动小红书（等待5s）
            self.start_app()

        def step2():
            # 2.进入视频频道：下拉一次（等待2s）显示隐藏tab，点击上方“视频”频道（等待2s）
            self.swipes_up(1, 2)
            self.driver.touch(BY.text('视频'), wait_time=2)

        def step3():
            # 3.进行浏览：上下滑动3次（滑动间隔2s）
            self.swipes_up(3, 2)
            self.swipes_down(3, 2)

        self.execute_performance_step('小红书-视频浏览场景-step1启动小红书（等待5s）', 10, step1)
        self.execute_performance_step(
            '小红书-视频浏览场景-step2进入视频频道：下拉一次（等待2s）显示隐藏tab，点击上方“视频”频道（等待2s）',
            10,
            step2,
        )
        self.execute_performance_step('小红书-视频浏览场景-step3进行浏览：上下滑动3次（滑动间隔2s）', 20, step3)
