import time
from typing import Optional

from hypium import BY

from hapray.core.perf_testcase import Log, PerfTestCase


class PerfLoad_kuaishou_0060(PerfTestCase):
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

    def setup(self):
        super().setup()
        self.set_device_redundant_mode()
        self.reboot_device()

    def process(self):
        def step1():
            self.start_app()
            self.swipe_to_home()

        self.execute_performance_step('快手-冷启动场景-step1应用冷启动', 10, step1, sample_all_processes=True)

