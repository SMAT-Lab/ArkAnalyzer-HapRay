import time

from hypium import BY

from hapray.core.perf_testcase import PerfTestCase


class ResourceUsage_PerformanceDynamic_zdh_0010(PerfTestCase):
    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(self.TAG, controllers)

        self._app_package = 'com.example.frameandpropertyanimation'
        self._app_name = '帧动画测试app'
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
        # 代码仓：https://gitcode.com/B1A2/FrameAndPropertyAnimation
        # 启动被测应用，明确指定 ability 名称
        self.start_app(page_name='EntryAbility')

        def step1():
            # 根据条件点击控件
            self.driver.touch(BY.text('帧动画'))
            self.driver.wait(0.5)
            # 根据条件点击控件
            self.driver.touch(BY.text('开始动画'))
            self.driver.wait(0.5)
            time.sleep(10)
            # 根据条件点击控件
            self.driver.touch(BY.text('停止动画'))
            self.driver.wait(0.5)


        def step2():
            # 根据条件点击控件
            self.driver.touch(BY.text('属性动画'))
            self.driver.wait(0.5)
            # 根据条件点击控件
            self.driver.touch(BY.text('开始动画'))
            self.driver.wait(0.5)
            time.sleep(10)
            # 根据条件点击控件
            self.driver.touch(BY.text('停止动画'))
            self.driver.wait(0.5)

        def step3():
            # 根据条件点击控件
            self.driver.touch(BY.text('帧动画'))
            self.driver.wait(0.5)
            # 根据条件点击控件
            self.driver.touch(BY.text('切换到头像变换'))
            self.driver.wait(0.5)
            # 根据条件点击控件
            self.driver.touch(BY.text('开始动画'))
            self.driver.wait(0.5)
            time.sleep(10)
            # 根据条件点击控件
            self.driver.touch(BY.text('停止动画'))
            self.driver.wait(0.5)

        self.execute_performance_step('帧动画测试app-step1帧动画头像旋转测试', 15, step1)
        # 根据条件点击控件
        self.driver.touch(BY.text('← 返回'))
        self.driver.wait(0.5)
        self.execute_performance_step('帧动画测试app-step1属性动画测试', 15, step2)
        # 根据条件点击控件
        self.driver.touch(BY.text('← 返回'))
        self.driver.wait(0.5)
        self.execute_performance_step('帧动画测试app-step1帧动画头像变换测试', 15, step3)
