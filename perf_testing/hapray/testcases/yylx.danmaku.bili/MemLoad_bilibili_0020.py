import time

from hypium import BY

from hapray.core.perf_testcase import PerfTestCase


class MemLoad_bilibili_0020(PerfTestCase):
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
            # 2.进入热门页面：点击热门（等待2s）
            self.driver.touch(BY.text('热门'), wait_time=2)

        def step3():
            # 3.热门页面浏览：上下滑动5次（滑动间隔2s）
            self.swipes_up(swip_num=5, sleep=2)
            self.swipes_down(swip_num=5, sleep=2)

        def step4():
            # 4.播放第一个视频，返回：点击第一个视频（等待5s），返回（等待2s）
            self.driver.touch(BY.type('GridItem'), wait_time=5)
            self.driver.swipe_to_back()
            time.sleep(2)

        def step5():
            # 5.播放第二个视频，返回：点击第二个视频（等待5s），返回（等待2s）
            com = self.driver.find_all_components(BY.type('GridItem'), 1)
            self.driver.touch(com, wait_time=5)
            self.driver.swipe_to_back()
            time.sleep(2)

        def step6():
            # 6.播放第三个视频，返回：点击第三个视频（等待5s），返回（等待2s）
            com = self.driver.find_all_components(BY.type('GridItem'), 2)
            self.driver.touch(com, wait_time=5)
            self.driver.swipe_to_back()
            time.sleep(2)

        self.execute_performance_step(
            '哔哩哔哩-热门浏览播放视频-step1哔哩哔哩启动', 10, step1, sample_all_processes=True
        )
        self.execute_performance_step('哔哩哔哩-热门浏览播放视频-step2进入热门页面：点击热门（等待2s）', 10, step2)
        self.execute_performance_step(
            '哔哩哔哩-热门浏览播放视频-step3热门页面浏览：上下滑动5次（滑动间隔2s）', 10, step3
        )
        self.execute_performance_step(
            '哔哩哔哩-热门浏览播放视频-step4播放第一个视频，返回：点击第一个视频（等待5s），返回（等待2s）', 10, step4
        )
        self.execute_performance_step(
            '哔哩哔哩-热门浏览播放视频-step5播放第二个视频，返回：点击第二个视频（等待5s），返回（等待2s）', 10, step5
        )
        self.execute_performance_step(
            '哔哩哔哩-热门浏览播放视频-step6播放第三个视频，返回：点击第三个视频（等待5s），返回（等待2s）', 10, step6
        )
