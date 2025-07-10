# coding: utf-8
import time

from hypium import BY

from hapray.core.perf_testcase import PerfTestCase


class ResourceUsage_PerformanceDynamic_zhifubao_0050(PerfTestCase):

    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(self.TAG, controllers)

        self._app_package = 'com.alipay.mobile.client'
        self._app_name = '支付宝'
        # 原始采集设备的屏幕尺寸（Mate 60 Pro）
        self.source_screen_width = 1260
        self.source_screen_height = 2720

    @property
    def app_package(self) -> str:
        return self._app_package

    @property
    def app_name(self) -> str:
        return self._app_name

    def process(self):
        self.driver.swipe_to_home()

        # 启动被测应用
        self.driver.start_app(self.app_package)
        self.driver.wait(5)
        # 搜索 蚂蚁庄园 ，进入该小程序
        self.driver.touch(self.convert_coordinate(599, 245))
        time.sleep(3)
        self.driver.input_text((BY.type('SearchField')), '蚂蚁庄园')
        time.sleep(3)
        self.driver.touch(BY.type('Button').text('搜索'))
        time.sleep(5)
        self.driver.touch(self.convert_coordinate(387, 628))
        time.sleep(5)
        self.driver.touch(self.convert_coordinate(392, 2288))
        time.sleep(2)
        self.driver.touch(self.convert_coordinate(658, 2114))
        time.sleep(2)

        def step1():
            # 领饲料，上下拖滑3次，间隔2s
            # 领饲料
            self.driver.touch(self.convert_coordinate(337, 2500))
            time.sleep(2)

            self.swipes_up(3, 2)
            self.swipes_down(3, 2)

            # 点击 x 图标返回上一页
            self.driver.touch(self.convert_coordinate(1198, 903))
            time.sleep(2)

        def step2():
            # 去捐蛋，上下拖滑1次，间隔2s
            self.driver.touch(self.convert_coordinate(780, 2500))
            time.sleep(2)
            self.swipes_up(1, 2)
            self.swipes_down(1, 2)
            # 点击 x 图标返回上一页
            self.driver.touch(self.convert_coordinate(1198, 903))
            time.sleep(2)

        def step3():
            # 点击领肥料
            self.driver.touch(self.convert_coordinate(1125, 2200))
            time.sleep(5)
            # 上下拖滑3次，间隔2s
            self.swipes_up(3, 2)
            self.swipes_down(3, 2)

        def step4():
            # 跳转至蚂蚁森林，点击奖励，上下拖滑3次，间隔2s
            self.driver.touch(self.convert_coordinate(520, 1820))
            time.sleep(3)
            self.swipes_up(3, 2)
            self.swipes_down(3, 2)

        self.execute_performance_step("支付宝-蚂蚁庄园场景-step1蚂蚁庄园领饲料", 25, step1)
        time.sleep(10)

        self.execute_performance_step("支付宝-蚂蚁庄园场景-step2蚂蚁庄园捐蛋", 15, step2)
        time.sleep(10)

        # 点左边树苗，跳转芭芭农场
        self.driver.touch(self.convert_coordinate(56, 1515))
        time.sleep(5)
        self.execute_performance_step("支付宝-蚂蚁庄园场景-step3芭芭农场领肥料", 25, step3)
        time.sleep(10)
        # 点击右上角
        self.driver.touch(self.convert_coordinate(1175, 197))
        time.sleep(2)
        # 点击左上角返回蚂蚁庄园
        self.driver.touch(self.convert_coordinate(387, 628))
        time.sleep(2)

        # 点击右侧树苗
        self.driver.touch(self.convert_coordinate(910, 1198))
        time.sleep(3)

        self.execute_performance_step("支付宝-蚂蚁庄园场景-step4蚂蚁森林页面浏览", 25, step4)
        # 上滑返回桌面
        self.driver.swipe_to_home()
