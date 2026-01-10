import time

from hypium import BY

from hapray.core.perf_testcase import PerfTestCase


class MemLoad_Douyin_0090(PerfTestCase):
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
            # 2.进入具体相册页面：点击“+”（等待2s），点击相册（等待2s）、点击最近项目（等待2s），点击“图库测试图片”相册（等待2s）
            self.driver.touch(BY.key('camera_entrance_plus_icon'), wait_time=2)
            self.driver.touch(BY.text('相册'), wait_time=2)
            self.driver.touch(BY.text('最近项目'), wait_time=2)
            self.driver.touch(BY.text('图库测试图片'), wait_time=2)

        def step3():
            # 3.图片浏览：上下滑动2次（等待2s）
            self.driver.check_component_exist(BY.text('全部'))
            self.swipes_up(2, 2)
            self.swipes_down(2, 2)

        def step4():
            # 4.选择第一张图片：选择第一张图片（等待2s），点击下一步（等待5s）
            self.swipes_down(1, 2)
            self.driver.touch(BY.type('Checkbox'), wait_time=2)
            self.driver.touch(BY.text('下一步'), wait_time=5)

        def step5():
            # 5.清空内容：侧滑返回（等待1s），点击清空内容（等待2s）
            self.driver.check_component_exist(BY.text('朋友日常'))
            self.driver.swipe_to_back()
            time.sleep(2)
            if self.driver.check_component(BY.text('清空内容')):
                self.driver.touch(BY.text('清空内容'), wait_time=2)

        self.execute_performance_step('抖音-图片浏览场景-step1打开抖音', 10, step1, sample_all_processes=True)
        self.execute_performance_step(
            '抖音-图片浏览场景-step2进入具体相册页面：点击“+”（等待2s），点击相册（等待2s）、点击最近项目（等待2s），点击“图库测试图片”相册（等待2s）',
            10,
            step2,
        )
        self.execute_performance_step('抖音-图片浏览场景-step3图片浏览：上下滑动2次（等待2s）', 10, step3)
        self.execute_performance_step(
            '抖音-图片浏览场景-step4选择第一张图片：选择第一张图片（等待2s），点击下一步（等待5s）', 10, step4
        )
        self.execute_performance_step(
            '抖音-图片浏览场景-step5清空内容：侧滑返回（等待1s），点击清空内容（等待2s）', 10, step5
        )
