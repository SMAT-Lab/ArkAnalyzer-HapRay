from hapray.core.perf_testcase import PerfTestCase


class ResourceUsage_PerformanceDynamic_TencentVideo_0010(PerfTestCase):
    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(self.TAG, controllers)

        self._app_package = 'com.tencent.videohm'
        self._app_name = '腾讯视频'
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
        self.start_app()

        def step1():
            # 首页上滑5次
            self.swipes_up(5, 1)
            self.swipes_down(5, 1)

        def step2():
            # 首页上滑5次
            self.touch_by_coordinates(500, 500, 15)

        self.execute_performance_step('腾讯视频-视频播放-step1首页浏览', 15, step1)
        self.execute_performance_step('腾讯视频-视频播放-step2推荐视频播放', 15, step2)
