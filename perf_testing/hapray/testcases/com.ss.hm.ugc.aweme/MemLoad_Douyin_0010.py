from hapray.core.perf_testcase import PerfTestCase


class MemLoad_Douyin_0010(PerfTestCase):
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
            # 2.滑动浏览视频：上滑5次（滑动间隔3s），下滑4次（滑动间隔3s）
            self.swipes_up(5, 3)
            self.swipes_down(4, 3)

        self.execute_performance_step('抖音-浏览视频场景-step1打开抖音', 10, step1, sample_all_processes=True)
        self.execute_performance_step(
            '抖音-浏览视频场景-step2滑动浏览视频：上滑5次（滑动间隔3s），下滑4次（滑动间隔3s）', 30, step2
        )
