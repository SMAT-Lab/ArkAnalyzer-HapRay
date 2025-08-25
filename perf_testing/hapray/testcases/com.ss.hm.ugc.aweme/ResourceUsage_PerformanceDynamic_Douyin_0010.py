from hapray.core.perf_testcase import PerfTestCase


class ResourceUsage_PerformanceDynamic_Douyin_0010(PerfTestCase):
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
        def start():
            # '启动被测应用'
            self.start_app()

            # 浏览推荐视频, 上滑5次
            self.swipes_up(5, 1)

            # 2. 抖音点击“我”，等待 2s
            self.touch_by_text('我')

            # 3. 抖音“我”页面点击右上角选项，等待2s
            self.touch_by_coordinates(988, 183, 2)

        def step1():
            # 1. 抖音“我”页面点击观看历史，等待2s
            if not self.touch_by_text('观看历史', 2):
                self.touch_by_coordinates(442, 609, 2)

        def step2():
            # 2. 观看历史上滑5次，每次等待1s;观看历史下滑5次，每次等待1s'
            self.swipes_up(5, 1, 300)
            self.swipes_down(5, 1, 300)

        start()
        self.execute_performance_step('抖音-浏览视频场景-step1点击观看历史', 10, step1)
        self.execute_performance_step('抖音-浏览视频场景-step2观看历史浏览', 20, step2)
