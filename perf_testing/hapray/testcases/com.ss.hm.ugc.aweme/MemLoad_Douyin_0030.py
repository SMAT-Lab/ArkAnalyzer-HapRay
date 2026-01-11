from hypium import BY

from hapray.core.perf_testcase import PerfTestCase


class MemLoad_Douyin_0030(PerfTestCase):
    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(self.TAG, controllers)

        self._app_package = 'com.ss.hm.ugc.aweme'
        self._app_name = '抖音'
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
        def step1():
            # 1. 打开抖音，等待 5s
            self.start_app()

        def step2():
            # 2. 进入博主主页：点击我（等待2s），点击关注（等待2s），点击雷军博主（等待2s）
            self.driver.touch(BY.text('我'), wait_time=2)
            self.driver.check_component_exist(BY.text('编辑资料'))
            self.driver.touch(BY.text('关注'), wait_time=2)
            self.driver.touch(BY.text('雷军'), wait_time=2)
            self.driver.check_component_exist(BY.text('私信'))

        def step3():
            # 3.主页浏览：上滑2次、下滑3次（滑动间隔2s）
            self.swipes_up(2, 2)
            self.swipes_down(3, 2)

        self.execute_performance_step('抖音-关注场景-step1打开抖音', 10, step1, sample_all_processes=True)
        self.execute_performance_step(
            '抖音-关注场景-step2进入博主主页：点击我（等待2s），点击关注（等待2s），点击雷军博主（等待2s）', 10, step2
        )
        self.execute_performance_step('抖音-关注场景-step3主页浏览：上滑2次、下滑3次', 10, step3)
