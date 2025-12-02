from hapray.core.perf_testcase import PerfTestCase


class PerfLoad_jingdong_1000(PerfTestCase):
    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(self.TAG, controllers)

        self._app_package = 'com.jd.hm.mall'
        self._app_name = '京东'
        # 原始采集设备的屏幕尺寸（Mate 60 Pro）
        self.source_screen_width = 1260
        self.source_screen_height = 2720

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

        self.execute_performance_step('京东-冷启动场景-step1应用冷启动', 10, step1, sample_all_processes=True)
