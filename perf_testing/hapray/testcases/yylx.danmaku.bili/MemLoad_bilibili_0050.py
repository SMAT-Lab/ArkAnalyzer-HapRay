import time

from hypium import BY

from hapray.core.perf_testcase import PerfTestCase


class MemLoad_bilibili_0050(PerfTestCase):
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
            # 2.进入我的收藏：点击我的（等待2s），点击我的收藏（等待2s）
            self.driver.touch(BY.text('我的'), wait_time=2)
            self.driver.touch(BY.text('我的收藏'), wait_time=2)

        def step3():
            # 3.播放指定视频：点击航拍中国第一季 新疆（等待2s）
            self.driver.touch(BY.text('航拍中国 第一季'), wait_time=2)

        def step4():
            # 4.拖动视频进度：调出进度条，拖动到开头（等待5s），拖动到20%（等待5s），拖动到50%（等待5s）
            # 调出进度条
            x, y = self.driver.get_comment_pos(BY.type('Blank'))
            self.driver.touch((x, y), wait_time=1)
            # 拖动到开头（等待5s）
            self.driver.slide((826, 765), (182, 765), slide_time=0.2)
            time.sleep(5)
            # 拖动到20%（等待5s）
            self.driver.touch((x, y), wait_time=1)
            self.driver.slide((182, 765), (311, 765), slide_time=0.2)
            time.sleep(5)
            # 拖动到50%（等待5s）
            self.driver.touch((x, y), wait_time=1)
            self.driver.slide((311, 765), (504, 765), slide_time=0.2)
            time.sleep(5)

        def step5():
            # 5.倍速播放10s：长按视频中心10s，点击暂停（等待2s）
            x, y = self.driver.get_comment_pos(BY.type('Blank'))
            self.driver.long_click((x, y), press_time=10)
            time.sleep(2)
            self.driver.touch((x, y), wait_time=1)
            self.driver.touch((0.06, 0.27), wait_time=2)

        def step6():
            # 6.评论浏览：点击评论（等待2s），上下滑动5次（滑动间隔2s）
            self.driver.touch(BY.text('评论'), wait_time=2)
            self.swipes_up(swip_num=5, sleep=2)
            self.swipes_down(swip_num=5, sleep=2)

        self.execute_performance_step('哔哩哔哩-播放收藏视频-step1哔哩哔哩启动', 10, step1, sample_all_processes=True)
        self.execute_performance_step(
            '哔哩哔哩-播放收藏视频-step2进入我的收藏：点击我的（等待2s），点击我的收藏（等待2s）', 10, step2
        )
        self.execute_performance_step(
            '哔哩哔哩-播放收藏视频-step3播放指定视频：点击航拍中国第一季 新疆（等待2s）', 10, step3
        )
        self.execute_performance_step(
            '哔哩哔哩-播放收藏视频-step4拖动视频进度：调出进度条，拖动到开头（等待5s），拖动到20%（等待5s），拖动到50%（等待5s）',
            30,
            step4,
        )
        self.execute_performance_step(
            '哔哩哔哩-播放收藏视频-step5倍速播放10s：长按视频中心10s，点击暂停（等待2s）', 20, step5
        )
        self.execute_performance_step(
            '哔哩哔哩-播放收藏视频-step6评论浏览：点击评论（等待2s），上下滑动5次（滑动间隔2s）', 30, step6
        )
