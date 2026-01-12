import time

from hypium import BY

from hapray.core.perf_testcase import PerfTestCase


class MemLoad_kuaishou_0040(PerfTestCase):
    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(self.TAG, controllers)

        self._app_package = 'com.kuaishou.hmapp'
        self._app_name = '快手'
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
        self.driver.swipe_to_home()

        def step1():
            # 1.启动快手（等待5s）
            self.driver.start_app(self.app_package)
            self.driver.wait(5)
            time.sleep(5)

        def step2():
            # 2.进入我的收藏视频页面：点击我（等待2s），点击收藏（等待5s）
            self.driver.touch(BY.text('我'), wait_time=2)
            self.driver.touch(BY.text('收藏'), wait_time=2)

        def step3():
            # 3.播放视频10s：点击第一个视频，拖动到开头进行播放，等待10s
            self.driver.touch(BY.type('GridItem'), wait_time=2)
            self.driver.slide((500, 2550), (100, 2550), slide_time=3)

        def step4():
            # 4.发表评论：点击评论按钮（等待2s），点击评论框（等待1s），输入“大好河山”（等待1s），点击发送（等待2s）
            x, y = self.driver.get_component_pos(BY.text('分享'))
            self.driver.touch((x, y - 591), wait_time=2)
            self.driver.touch((0.38, 0.94), wait_time=2)
            self.driver.input_text(BY.key('comment_input_area'), '大好河山')
            time.sleep(1)
            self.driver.touch(BY.text('发送'), wait_time=2)

        def step5():
            # 5.浏览评论：上下滑动5次（滑动间隔2s）
            self.swipes_up(swip_num=5, sleep=2)
            self.swipes_down(swip_num=5, sleep=2)

        self.execute_performance_step('快手-评论浏览-step1启动快手（等待5s）', 10, step1, sample_all_processes=True)
        self.execute_performance_step(
            '快手-评论浏览-step2进入我的收藏视频页面：点击我（等待2s），点击收藏（等待5s）', 10, step2
        )
        self.execute_performance_step(
            '快手-评论浏览-step3播放视频10s：点击第一个视频，拖动到开头进行播放，等待10s', 10, step3
        )
        self.execute_performance_step(
            '快手-评论浏览-step4发表评论：点击评论按钮（等待2s），点击评论框（等待1s），输入“大好河山”（等待1s），点击发送（等待2s）',
            10,
            step4,
        )
        self.execute_performance_step('快手-评论浏览-step5浏览评论：上下滑动5次（滑动间隔2s）', 10, step5)
