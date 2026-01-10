import time

from hypium import BY
from hypium.model.basic_data_type import MatchPattern

from hapray.core.perf_testcase import PerfTestCase


class MemLoad_Douyin_0040(PerfTestCase):
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
            # 2.进入我的收藏视频页面：点击我（等待2s），点击收藏（等待4s），点击视频（等待2s）
            self.driver.touch(BY.text('我'), wait_time=2)
            self.driver.check_component_exist(BY.text('编辑资料'))
            self.driver.touch(BY.text('收藏'), wait_time=4)
            self.driver.check_component_exist(BY.text('视频'))
            self.driver.touch(BY.text('视频'), wait_time=2)

        def step3():
            # 3.播放视频10s：点击第一个视频，拖动到开头进行播放，等待10s
            self.driver.touch((212, 2012), wait_time=2)
            self.driver.check_component_exist(BY.text('@央视频'))
            self.driver.slide((406, 2531), slide_time=2)
            time.sleep(10)

        def step4():
            # 4.发表评论：点击评论按钮（等待2s），点击评论框（等待1s），输入“大好山河”（等待1s），点击发送（等待2s）
            if self.driver.find_component(BY.key('avatar_img')):
                x, y = self.driver.find_component_pos(BY.key('avatar_img'))
            else:
                x, y = self.driver.find_component_pos(BY.key('avatar_live'))
            self.driver.touch((x, y + 452), wait_time=2)
            self.driver.check_component_exist(BY.text('条评论', MatchPattern.ENDS_WITH))
            self.driver.touch(BY.text('善语结善缘，恶语伤人心'), wait_time=1)
            self.driver.input_text(BY.id('input_editor'), '大好河山')
            self.driver.touch(BY.text('发送'), wait_time=2)

        def step5():
            # 5.浏览评论：上下滑动5次（滑动间隔2s）
            self.swipes_up(5, 2)
            self.swipes_down(5, 2)

        self.execute_performance_step('抖音-收藏评论场景-step1打开抖音', 10, step1, sample_all_processes=True)
        self.execute_performance_step(
            '抖音-收藏评论场景-step2进入我的收藏视频页面：点击我（等待2s），点击收藏（等待4s），点击视频（等待2s）',
            10,
            step2,
        )
        self.execute_performance_step(
            '抖音-收藏评论场景-step3播放视频10s：点击第一个视频，拖动到开头进行播放，等待10s', 10, step3
        )
        self.execute_performance_step(
            '抖音-收藏评论场景-step4发表评论：点击评论按钮（等待2s），点击评论框（等待1s），输入“大好山河”（等待1s），点击发送（等待2s）',
            10,
            step4,
        )
        self.execute_performance_step('抖音-收藏评论场景-step5浏览评论：上下滑动5次（滑动间隔2s）', 10, step5)
