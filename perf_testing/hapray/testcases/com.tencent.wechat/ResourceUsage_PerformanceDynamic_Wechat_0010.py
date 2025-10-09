from hapray.core.perf_testcase import PerfTestCase


class ResourceUsage_PerformanceDynamic_Wechat_0010(PerfTestCase):
    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(self.TAG, controllers)

        self._app_package = 'com.tencent.wechat'
        self._app_name = '微信'
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
            # 首页上滑10次
            self.swipes_up(10, 1)
            self.swipes_down(10, 1)

        self.execute_performance_step('微信-群聊图片消息发送和浏览场景-step1消息列表浏览', 40, step1)
