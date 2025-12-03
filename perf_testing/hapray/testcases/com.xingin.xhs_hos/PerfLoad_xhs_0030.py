import time

from hapray.core.perf_testcase import PerfTestCase


class PerfLoad_xhs_0030(PerfTestCase):
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
        # 启动被测应用
        self.start_app()

        # 首页点击 ”我“
        self.touch_by_text('我', 1)

        # ”我“ 页面点击“收藏”
        self.touch_by_text('收藏', 1)

        # 点击收藏的图片链接“100件温暖幸福的小事（3）”
        self.find_by_text_up('100件温暖幸福的小事 （3)', 3)
        self.touch_by_text('100件温暖幸福的小事 （3)', 1)

        def step1():
            # 浏览收藏图片左滑5次
            # 左滑5次，停留2s
            self.swipes_left(5, 2, 300)
            # 双指捏合放大、缩小2次
            p1 = self.convert_coordinate(
                x=820,  # 原始x坐标
                y=1040,  # 原始y坐标
            )
            p2 = self.convert_coordinate(
                x=480,  # 原始x坐标
                y=1450,  # 原始y坐标
            )
            p3 = self.convert_coordinate(
                x=1130,  # 原始x坐标
                y=720,  # 原始y坐标
            )
            p4 = self.convert_coordinate(
                x=180,  # 原始x坐标
                y=1850,  # 原始y坐标
            )
            for _i in range(2):
                self.driver._two_finger_swipe(p1, p2, p3, p4)
                time.sleep(1)
                self.driver._two_finger_swipe(p3, p4, p1, p2)
                time.sleep(1)

        def step2():
            # '查看评论，上下滑3次
            # 点击评论
            self.touch_by_coordinates(1071, 2538, 2)

            # 上滑3次，停留2s
            self.swipes_up(3, 2, 300)

            # 下滑3次，停留2s
            self.swipes_down(3, 2, 300)

            self.driver.swipe_to_back()
            self.touch_by_text('漫步上海佛罗伦萨小镇｜快乐不止一点点', 2)

            self.swipes_up(3, 2, 300)
            self.swipes_down(3, 2, 300)

        self.execute_performance_step('小红书-浏览图文详情及评论场景-step1收藏图片浏览、双指捏合放大/缩小', 35, step1)
        self.execute_performance_step('小红书-浏览图文详情及评论场景-step2评论页浏览、长文笔记浏览', 50, step2)

