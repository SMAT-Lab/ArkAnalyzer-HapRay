# coding: utf-8
import os

from hapray.core.common.common_utils import CommonUtils
from hapray.core.common.coordinate_adapter import CoordinateAdapter
from hapray.core.perf_testcase import PerfTestCase, Log


class ResourceUsage_PerformanceDynamic_jingdong_0050(PerfTestCase):

    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(self.TAG, controllers)

        self._app_package = 'com.jd.hm.mall'
        self._app_name = '京东'
        self._steps = [
            {
                "name": "step1",
                "description": "1.京东观看直播场景，上滑3次，下滑3次"
            }
        ]

        # 原始采集设备的屏幕尺寸（Mate 60 Pro）
        self.source_screen_width = 1212
        self.source_screen_height = 2616

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
        Log.info('setup')
        os.makedirs(os.path.join(self.report_path, 'hiperf'), exist_ok=True)
        os.makedirs(os.path.join(self.report_path, 'htrace'), exist_ok=True)

    def process(self):
        self.driver.swipe_to_home()

        # Step('启动京东应用')
        self.driver.start_app(self.app_package)
        self.driver.wait(3)
        # 点击直播
        self.driver.touch(CoordinateAdapter.convert_coordinate(
            self.driver,
            x=698,  # 原始x坐标
            y=1534,  # 原始y坐标
            source_width=self.source_screen_width,
            source_height=self.source_screen_height
        ))
        self.driver.wait(3)

        def step1(driver):
            # Step('京东直播上滑操作')
            CommonUtils.swipes_up_load(self.driver, swip_num=3, sleep=2)
            # Step('京东直播下滑操作')
            CommonUtils.swipes_down_load(self.driver, swip_num=3, sleep=2)

        self.execute_performance_step(1, step1, 30)

    def teardown(self):
        Log.info('teardown')
        self.driver.stop_app(self.app_package)
        self.generate_reports()
