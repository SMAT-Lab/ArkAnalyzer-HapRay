# coding: utf-8

from hapray.core.perf_testcase import PerfTestCase


class ResourceUsage_PerformanceDynamic_jingdong_1000(PerfTestCase):

    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(self.TAG, controllers)

        self._app_package = 'com.jd.hm.mall'
        self._app_name = '京东'
        self._steps = [
            {
                "name": "step1",
                "description": "1. 应用冷启动，手机重启后及时输入开机密码和设置连接电脑传输文件。再检查重启后手机是否自动关闭了usb调试，如关闭，请手动打开"
            }
        ]
        # 原始采集设备的屏幕尺寸（Mate 60 Pro）
        self.source_screen_width = 1260
        self.source_screen_height = 2720

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

        self.execute_performance_step(1, step1, 5, True)
