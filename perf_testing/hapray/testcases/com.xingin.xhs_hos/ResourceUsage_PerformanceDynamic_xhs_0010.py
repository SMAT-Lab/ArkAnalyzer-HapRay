from hapray.core.perf_testcase import PerfTestCase


class ResourceUsage_PerformanceDynamic_xhs_0010(PerfTestCase):
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
        # 启动被测应用
        self.start_app()

        self.swipes_down(1, 5)
        self.touch_by_text('视频')

        def step1():
            # 首页上滑5次、下滑5次，停留2s
            # 上滑5次
            self.swipes_up(5, 3, 300)
            self.swipes_down(5, 3, 300)

        self.execute_performance_step('小红书-首页浏览场景-step1首页浏览', 45, step1)
