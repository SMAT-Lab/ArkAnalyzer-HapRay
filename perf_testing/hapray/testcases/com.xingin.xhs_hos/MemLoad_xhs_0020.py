import time

from hypium import BY
from hypium.model.basic_data_type import MatchPattern

from hapray.core.perf_testcase import PerfTestCase


class MemLoad_xhs_0020(PerfTestCase):
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
            # 2.进入我的收藏页面：点击我（等待2s）、点击收藏（等待2s），向上滑动一次（等待2s）
            self.driver.touch(BY.text('我'), wait_time=2)
            self.driver.touch(BY.text('收藏'), wait_time=2)
            self.swipes_up(1, 2)

        def step3():
            # 3.播放视频10s：点击一口气看完历史上最荒唐的王朝北齐！，等待10s
            self.driver.touch(BY.text('一口气看完历史上最荒唐的王朝北齐！'), wait_time=10)

        def step4():
            # 4.点赞、取消点赞：点击点赞按钮（等待2s）、点击点赞按钮（等待2s）
            x, y = self.driver.get_component_pos(BY.text('说点什么', MatchPattern.STARTS_WITH))
            self.driver.touch((x + 236, y), wait_time=2)
            self.driver.touch((x + 236, y), wait_time=2)
            self.driver.slide((2581, 2579), (56, 2579), slide_time=0.2)
            time.sleep(10)

        def step5():
            # 5.浏览评论：点击评论（等待2s），上下滑动3次（滑动间隔2s）
            x, y = self.driver.get_component_pos(BY.text('说点什么', MatchPattern.STARTS_WITH))
            self.driver.touch((x + 776, y), wait_time=2)
            self.driver.check_component_exist(BY.text('条评论', MatchPattern.ENDS_WITH))
            self.swipes_up(3, 2)
            self.swipes_down(3, 2)

        self.execute_performance_step('小红书-收藏视频浏览场景-step1启动小红书（等待5s）', 10, step1)
        self.execute_performance_step(
            '小红书-收藏视频浏览场景-step2进入我的收藏页面：点击我（等待2s）、点击收藏（等待2s），向上滑动一次（等待2s）',
            10,
            step2,
        )
        self.execute_performance_step(
            '小红书-收藏视频浏览场景-step3播放视频10s：点击一口气看完历史上最荒唐的王朝北齐！，等待10s', 20, step3
        )
        self.execute_performance_step(
            '小红书-收藏视频浏览场景-step4点赞、取消点赞：点击点赞按钮（等待2s）、点击点赞按钮（等待2s）', 10, step4
        )
        self.execute_performance_step(
            '小红书-收藏视频浏览场景-step5浏览评论：点击评论（等待2s），上下滑动3次（滑动间隔2s）', 10, step5
        )
