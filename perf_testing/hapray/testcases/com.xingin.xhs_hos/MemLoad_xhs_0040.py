from hypium import BY
from hypium.model.basic_data_type import MatchPattern

from hapray.core.perf_testcase import PerfTestCase


class MemLoad_xhs_0040(PerfTestCase):
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
            # 2.进入相册界面：点击+（等待2s）
            self.driver.touch((0.50, 0.94), wait_time=2)

        def step3():
            # 3.选择三张图片：点击顶部相册（等待1s），点击“图库测试图片”（等待2s），选择前三张图片（等待1s），点击下一步（等待2s）
            self.driver.touch(BY.text('相册'), wait_time=1)
            self.driver.touch(BY.text('图库测试图片'), wait_time=2)
            sele = self.driver.find_all_components(BY.key('Selector', MatchPattern.STARTS_WITH))
            for i in range(3):
                self.driver.touch(sele[i], wait_time=1)
            self.driver.touch(BY.text('下一步', MatchPattern.STARTS_WITH), wait_time=2)

        def step4():
            # 4.报错操作：点击下一步（等待2s），点击保存草稿（等待2s），点击确认（等待2s）
            self.driver.touch(BY.text('下一步'), wait_time=2)
            self.driver.touch(BY.text('存草稿'), wait_time=2)
            self.driver.touch(BY.text('确认'), wait_time=2)

        def step5():
            # 5.删除草稿：点击本地操作（等待2s），点垃圾桶（等待2s），点击确认（等待2s）
            self.driver.touch(BY.text('本地草稿'), wait_time=2)
            self.driver.touch((0.44, 0.44), wait_time=2)
            self.driver.touch(BY.text('确认'), wait_time=2)

        self.execute_performance_step('小红书-相册浏览场景-step1启动小红书（等待5s）', 10, step1)
        self.execute_performance_step('小红书-相册浏览场景-step2进入相册界面：点击+（等待2s））', 10, step2)
        self.execute_performance_step(
            '小红书-相册浏览场景-step3选择三张图片：点击顶部相册（等待1s），点击“图库测试图片”（等待2s），选择前三张图片（等待1s），点击下一步（等待2s）',
            20,
            step3,
        )
        self.execute_performance_step(
            '小红书-相册浏览场景-step4报错操作：点击下一步（等待2s），点击保存草稿（等待2s），点击确认（等待2s）',
            10,
            step4,
        )
        self.execute_performance_step(
            '小红书-相册浏览场景-step5删除草稿：点击本地操作（等待2s），点垃圾桶（等待2s），点击确认（等待2s）',
            10,
            step5,
        )
