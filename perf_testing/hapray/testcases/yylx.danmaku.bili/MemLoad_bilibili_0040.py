import time

from hypium import BY

from hapray.core.perf_testcase import PerfTestCase


class MemLoad_bilibili_0040(PerfTestCase):
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
            # 2.点击搜索输入华为终端：点击搜索框（等待2s），输入“华为终端”（等待1s）
            x, y = self.driver.get_component_pos(BY.text('热门'))
            self.driver.touch((x, y - 120), wait_time=2)
            self.driver.input_text(BY.type('TextInput'), '华为终端')
            time.sleep(1)

        def step3():
            # 3.点击搜索：点击搜索按钮（等待5s）
            self.driver.touch(BY.text('搜索'), wait_time=5)

        def step4():
            # 4.搜索结果浏览：上下滑动5次（滑动间隔2s）
            self.driver.check_component_exist(BY.text('综合'))
            self.swipes_up(swip_num=5, sleep=2)
            self.swipes_down(swip_num=5, sleep=2)

        self.execute_performance_step('哔哩哔哩-UP主主页浏览-step1哔哩哔哩启动', 10, step1, sample_all_processes=True)
        self.execute_performance_step('哔哩哔哩-UP主主页浏览-step2点击搜索输入华为终端）', 10, step2)
        self.execute_performance_step('哔哩哔哩-UP主主页浏览-step3点击搜索：点击搜索按钮（等待5s）', 10, step3)
        self.execute_performance_step('哔哩哔哩-UP主主页浏览-step4搜索结果浏览：上下滑动5次（滑动间隔2s）', 10, step4)
