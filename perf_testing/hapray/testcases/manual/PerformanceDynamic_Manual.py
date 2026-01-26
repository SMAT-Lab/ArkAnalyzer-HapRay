import time

from xdevice import platform_logger

from hapray.core.config.config import Config
from hapray.core.perf_testcase import PerfTestCase

Log = platform_logger('PerformanceDynamic_Manual')


class PerformanceDynamic_Manual(PerfTestCase):
    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(self.TAG, controllers)
        self._app_package = Config.get('package_name')
        if self._app_package is None:
            self._app_package = input('请输入应用的包名:')
        self._app_name = 'Manual'
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
        self.driver.swipe_to_home()

        # Step('启动被测应用')
        self.driver.start_app(self.app_package)
        self.driver.wait(5)

        def step1():
            Log.info('正在负载采集...请操作测试UI')
            time.sleep(30)
        Log.info('开始负载采集！')
        self.execute_performance_step('手动测试', 30, step1)
        Log.info('结束负载采集！')
