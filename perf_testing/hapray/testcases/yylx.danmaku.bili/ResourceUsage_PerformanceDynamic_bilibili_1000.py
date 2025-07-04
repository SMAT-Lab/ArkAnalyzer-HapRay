# coding: utf-8

from hapray.core.perf_testcase import PerfTestCase


class ResourceUsage_PerformanceDynamic_bilibili_1000(PerfTestCase):

    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(self.TAG, controllers)

        self._app_package = 'yylx.danmaku.bili'
        self._app_name = '哔哩哔哩'
        self._steps = [
            {
                "name": "step1",
                "description": "1. 应用冷启动"
            }
        ]

    @property
    def steps(self) -> list:
        return self._steps

    @property
    def app_package(self) -> str:
        return self._app_package

    @property
    def app_name(self) -> str:
        return self._app_name

    def setup(self):
        super().setup()

        self.set_device_redundant_mode()
        self.reboot_device()

    def process(self):
        def step1():
            self.start_app()
            self.swipe_to_home()

        self.execute_performance_step(1, step1, 10, True)
