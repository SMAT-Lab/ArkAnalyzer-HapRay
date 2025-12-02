import time
from typing import Optional

from hypium import BY

from hapray.core.perf_testcase import Log, PerfTestCase


class PerfLoad_kuaishou_0050(PerfTestCase):
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

    def process(self):
        self.driver.swipe_to_home()

        # Step('启动被测应用')
        self.driver.start_app(self.app_package)
        self.driver.wait(5)
        time.sleep(2)

        # 点击中间加号
        self.driver.touch(self.convert_coordinate(540, 2253))
        time.sleep(2)



        def step1():
            # 点击拍摄按钮
            self.driver.touch(self.convert_coordinate(541, 2000))
            time.sleep(15)

            self.driver.touch(BY.text('下一步'))
            time.sleep(2)
            self.driver.touch(BY.text('发布'))
            time.sleep(2)

        self.execute_performance_step('快手-拍摄-step1快手拍视频发布', 35, step1)

        self.driver.touch(BY.text('我'))
        time.sleep(2)
        self.driver.touch(BY.text('作品'))
        time.sleep(2)
        # 进入作品
        self.driver.touch(self.convert_coordinate(161, 1344))
        time.sleep(15)
        self.driver.touch(BY.text('设置'))
        time.sleep(2)
        self.driver.touch(BY.text('删除作品'))
        time.sleep(2)
        self.driver.touch(BY.text('确认'))
        time.sleep(2)

