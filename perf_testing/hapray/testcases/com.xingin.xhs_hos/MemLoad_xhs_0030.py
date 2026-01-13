import time

from hypium import BY

from hapray.core.perf_testcase import PerfTestCase


class MemLoad_xhs_0030(PerfTestCase):
    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(self.TAG, controllers)

        self._app_package = 'com.xingin.xhs_hos'
        self._app_name = '小红书'
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
        def step1():
            # 1.启动小红书（等待5s）
            self.start_app()

        def step2():
            # 2.进入搜索界面：点击搜索按钮（等待2s）
            self.driver.touch((0.92, 0.08), wait_time=2)

        def step3():
            # 3.进行搜索：输入“穿搭图片”（等待1s），点击搜索（等待3s）
            self.driver.input_text(BY.type('SearchField'), '穿搭图片')
            time.sleep(1)
            self.driver.touch(BY.text('搜索'), wait_time=3)
            self.driver.check_component_exist(BY.text('全部'))

        def step4():
            # 4.页面浏览：上下滑动3次（滑动间隔2s）
            self.swipes_up(3, 2)
            self.swipes_down(3, 2)

        self.execute_performance_step('小红书-搜索浏览场景-step1启动小红书（等待5s）', 10, step1)
        self.execute_performance_step('小红书-搜索浏览场景-step2进入搜索界面：点击搜索按钮（等待2s）', 10, step2)
        self.execute_performance_step(
            '小红书-搜索浏览场景-step3进行搜索：输入“穿搭图片”（等待1s），点击搜索（等待3s）', 10, step3
        )
        self.execute_performance_step('小红书-搜索浏览场景-step4页面浏览：上下滑动3次（滑动间隔2s））', 20, step4)
