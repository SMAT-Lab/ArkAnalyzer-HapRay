import time

from hapray.core.config.config import Config
from hapray.core.perf_testcase import PerfTestCase


class PerformanceDynamic_Manual(PerfTestCase):
    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(self.TAG, controllers)
        self._app_package = Config.get('app')
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
            print('正在负载采集...请操作测试UI')
            time.sleep(30)

        while True:
            print('\n' + '=' * 50)
            print('负载采集准备提示')
            print('=' * 50)
            ready = input('请确保：测试页面已正确加载\n\n是否开始30秒的负载采集？(Y): ')
            if ready.upper() == 'Y':
                print('开始负载采集...')
                break

        self.execute_performance_step('手动测试', 30, step1)
