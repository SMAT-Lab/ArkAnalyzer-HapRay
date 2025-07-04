# coding: utf-8
import time

from devicetest.core.test_case import Step
from hypium import BY

from hapray.core.common.common_utils import CommonUtils
from hapray.core.common.coordinate_adapter import CoordinateAdapter
from hapray.core.perf_testcase import PerfTestCase


class ResourceUsage_PerformanceDynamic_zhifubao_0080(PerfTestCase):

    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(self.TAG, controllers)

        self._app_package = 'com.alipay.mobile.client'
        self._app_name = '支付宝'
        self._steps = [
            {
                "name": "step1",
                "description": "1. 领饲料，上下拖滑3次，间隔2s"
            },
            {
                "name": "step2",
                "description": "2. 去捐蛋，上下拖滑1次，间隔2s"
            },
            {
                "name": "step3",
                "description": "3. 芭芭农场，领肥料，上下拖滑3次，间隔2s"
            },
            {
                "name": "step4",
                "description": "4. 跳转至蚂蚁森林，点击奖励，上下拖滑3次，间隔2s"
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

    def process(self):
        self.driver.swipe_to_home()

        Step('启动被测应用')
        self.driver.start_app(self.app_package)
        self.driver.wait(5)
        # 搜索 蚂蚁庄园 ，进入该小程序
        self.driver.touch(CoordinateAdapter.convert_coordinate(
            self.driver,
            x=599,  # 原始x坐标
            y=245,  # 原始y坐标
            source_width=self.source_screen_width,
            source_height=self.source_screen_height
        ))
        time.sleep(3)
        self.driver.input_text((BY.type('SearchField')), '蚂蚁庄园')
        time.sleep(3)
        self.driver.touch(BY.type('Button').text('搜索'))
        time.sleep(5)
        self.driver.touch(CoordinateAdapter.convert_coordinate(
            self.driver,
            x=387,  # 原始x坐标
            y=628,  # 原始y坐标
            source_width=self.source_screen_width,
            source_height=self.source_screen_height
        ))
        time.sleep(5)
        self.driver.touch(CoordinateAdapter.convert_coordinate(
            self.driver,
            x=392,  # 原始x坐标
            y=2288,  # 原始y坐标
            source_width=self.source_screen_width,
            source_height=self.source_screen_height
        ))
        time.sleep(2)
        self.driver.touch(CoordinateAdapter.convert_coordinate(
            self.driver,
            x=658,  # 原始x坐标
            y=2114,  # 原始y坐标
            source_width=self.source_screen_width,
            source_height=self.source_screen_height
        ))
        time.sleep(2)

        def step1():
            Step('1. 领饲料，上下拖滑3次，间隔2s')
            # 领饲料
            self.driver.touch(CoordinateAdapter.convert_coordinate(
                self.driver,
                x=337,  # 原始x坐标
                y=2500,  # 原始y坐标
                source_width=self.source_screen_width,
                source_height=self.source_screen_height
            ))
            time.sleep(2)
            for i in range(3):
                CommonUtils.swipe(self.driver.device_sn, 625, 2500, 625, 2100, 300)
                time.sleep(2)
            for i in range(3):
                CommonUtils.swipe(self.driver.device_sn, 625, 2100, 625, 2500, 300)
                time.sleep(2)
            time.sleep(3)

        def step2():
            Step('2. 去捐蛋，上下拖滑1次，间隔2s')
            # self.driver.touch(BY.text('去捐蛋'))
            self.driver.touch(CoordinateAdapter.convert_coordinate(
                self.driver,
                x=780,  # 原始x坐标
                y=2500,  # 原始y坐标
                source_width=self.source_screen_width,
                source_height=self.source_screen_height
            ))
            time.sleep(2)
            CommonUtils.swipe(self.driver.device_sn, 625, 2500, 625, 1550, 300)
            time.sleep(2)
            CommonUtils.swipe(self.driver.device_sn, 625, 1550, 625, 2500, 300)
            time.sleep(2)

        def step3():
            Step('3. 芭芭农场，领肥料，上下拖滑3次，间隔2s')
            # 点左边树苗
            self.driver.touch(CoordinateAdapter.convert_coordinate(
                self.driver,
                x=56,  # 原始x坐标
                y=1515,  # 原始y坐标
                source_width=self.source_screen_width,
                source_height=self.source_screen_height
            ))
            time.sleep(5)
            # self.driver.touch(BY.text('领肥料'))
            self.driver.touch(CoordinateAdapter.convert_coordinate(
                self.driver,
                x=1125,  # 原始x坐标
                y=2200,  # 原始y坐标
                source_width=self.source_screen_width,
                source_height=self.source_screen_height
            ))
            time.sleep(5)
            for i in range(3):
                CommonUtils.swipe(self.driver.device_sn, 625, 2500, 625, 2100, 300)
                time.sleep(2)
            for i in range(3):
                CommonUtils.swipe(self.driver.device_sn, 625, 2100, 625, 2500, 300)
                time.sleep(2)

        def step4():
            Step('4. 跳转至蚂蚁森林，点击奖励，上下拖滑3次，间隔2s')
            # 点击右侧树苗
            self.driver.touch(CoordinateAdapter.convert_coordinate(
                self.driver,
                x=910,  # 原始x坐标
                y=1198,  # 原始y坐标
                source_width=self.source_screen_width,
                source_height=self.source_screen_height
            ))
            time.sleep(3)
            # self.driver.touch(BY.text('奖励'))
            self.driver.touch(CoordinateAdapter.convert_coordinate(
                self.driver,
                x=520,  # 原始x坐标
                y=1820,  # 原始y坐标
                source_width=self.source_screen_width,
                source_height=self.source_screen_height
            ))

            time.sleep(3)
            for i in range(3):
                CommonUtils.swipe(self.driver.device_sn, 625, 2500, 625, 2100, 300)
                time.sleep(2)
            for i in range(3):
                CommonUtils.swipe(self.driver.device_sn, 625, 2100, 625, 2500, 300)
                time.sleep(2)

        self.execute_performance_step(1, step1, 25)
        time.sleep(10)
        # 点击 x 图标返回上一页
        self.driver.touch(CoordinateAdapter.convert_coordinate(
            self.driver,
            x=1198,  # 原始x坐标
            y=903,  # 原始y坐标
            source_width=self.source_screen_width,
            source_height=self.source_screen_height
        ))
        time.sleep(2)

        self.execute_performance_step(2, step2, 15)
        # 点击 x 图标返回上一页
        self.driver.touch(CoordinateAdapter.convert_coordinate(
            self.driver,
            x=1198,  # 原始x坐标
            y=903,  # 原始y坐标
            source_width=self.source_screen_width,
            source_height=self.source_screen_height
        ))
        time.sleep(2)

        self.execute_performance_step(3, step3, 25)
        time.sleep(10)
        # 点击右上角
        self.driver.touch(CoordinateAdapter.convert_coordinate(
            self.driver,
            x=1175,  # 原始x坐标
            y=197,  # 原始y坐标
            source_width=self.source_screen_width,
            source_height=self.source_screen_height
        ))
        time.sleep(2)
        # 点击左上角返回蚂蚁庄园
        self.driver.touch(CoordinateAdapter.convert_coordinate(
            self.driver,
            x=387,  # 原始x坐标
            y=628,  # 原始y坐标
            source_width=self.source_screen_width,
            source_height=self.source_screen_height
        ))
        time.sleep(2)

        self.execute_performance_step(4, step4, 25)
        # 上滑返回桌面
        self.driver.swipe_to_home()
