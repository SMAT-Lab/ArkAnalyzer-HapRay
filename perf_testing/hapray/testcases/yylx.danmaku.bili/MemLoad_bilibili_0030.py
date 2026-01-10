from hypium import BY

from hapray.core.perf_testcase import PerfTestCase


class MemLoad_bilibili_0030(PerfTestCase):
    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(self.TAG, controllers)
        self._app_package = 'yylx.danmaku.bili'
        self._app_name = '哔哩哔哩'

    @property
    def app_package(self) -> str:
        return self._app_package

    @property
    def app_name(self) -> str:
        return self._app_name

    def process(self):
        def step1():
            # 1.启动哔哩哔哩（等待5s）
            self.start_app()

        def step2():
            # 2.进入我的关注：点击我的（等待2s），点击关注（等待2s）
            self.driver.touch(BY.text('我的'), wait_time=2)
            self.driver.touch(BY.text('关注'), wait_time=2)

        def step3():
            # 3.进入up主首页：点击“华为终端”，等待5s
            self.driver.touch(BY.text('华为终端'), wait_time=5)

        def step4():
            # 4.主页浏览：上下滑动（滑动间隔2s）
            self.driver.check_component_exist(BY.text('投稿'))
            self.swipes_up(swip_num=5, sleep=2)
            self.swipes_down(swip_num=5, sleep=2)

        self.execute_performance_step('哔哩哔哩-UP主主页浏览-step1哔哩哔哩启动', 10, step1, sample_all_processes=True)
        self.execute_performance_step(
            '哔哩哔哩-UP主主页浏览-step2进入我的关注：点击我的（等待2s），点击关注（等待2s）', 10, step2
        )
        self.execute_performance_step('哔哩哔哩-UP主主页浏览-step3进入up主首页：点击“华为终端”，等待5s', 10, step3)
        self.execute_performance_step('哔哩哔哩-UP主主页浏览-step4主页浏览：上下滑动（滑动间隔2s）', 10, step4)
