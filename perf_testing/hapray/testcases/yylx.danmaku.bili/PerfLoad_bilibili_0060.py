import time

from hypium import BY

from hapray.core.perf_testcase import PerfTestCase


class PerfLoad_bilibili_0060(PerfTestCase):
    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(self.TAG, controllers)
        self._app_package = 'yylx.danmaku.bili'
        self._app_name = '哔哩哔哩'
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
            # 搜索框输入“航拍中国“ （键盘输入15次，每0.5s点击一次，15s），并且点击”航拍中国“（1s），点击搜索（1s）')

            # 点击H
            self.touch_by_coordinates(643, 1850, 0.5)  # Mate60 Pro

            # 点击A
            self.touch_by_coordinates(120, 1850, 0.5)

            # 点击N
            self.touch_by_coordinates(747, 2030, 0.5)

            # 点击G
            self.touch_by_coordinates(544, 1850, 0.5)

            # 点击P
            self.touch_by_coordinates(1014, 1690, 0.5)

            # 点击A
            self.touch_by_coordinates(120, 1850, 0.5)

            # 点击I
            self.touch_by_coordinates(803, 1690, 0.5)

            # 点击Z
            self.touch_by_coordinates(220, 2030, 0.5)

            # 点击H
            self.touch_by_coordinates(643, 1850, 0.5)

            # 点击O
            self.touch_by_coordinates(902, 1690, 0.5)

            # 点击N
            self.touch_by_coordinates(747, 2030, 0.5)

            # 点击G
            self.touch_by_coordinates(544, 1850, 0.5)

            # 点击G
            self.touch_by_coordinates(544, 1850, 0.5)

            # 点击U
            self.touch_by_coordinates(690, 1690, 0.5)

            # 点击O
            self.touch_by_coordinates(898, 1690, 0.5)

            time.sleep(7.5)

            # 点击航拍中国
            self.driver.touch(BY.text('航拍中国'))
            time.sleep(1)

            # 点击搜索
            self.driver.touch(BY.text('搜索'))
            time.sleep(4)

        # 启动被测应用
        self.start_app()
        # 点击搜索框，停留2s
        self.driver.touch((657, 185))  # Mate60 Pro
        self.driver.wait(0.5)
        time.sleep(2)

        # 搜索框输入“航拍中国“ （键盘输入15次，每0.5s点击一次，15s），并且点击”航拍中国“（1s），点击搜索（1s）
        self.execute_performance_step('哔哩哔哩-视频搜索场景-step1视频搜索', 20, step1)

        # 搜索结果页上滑3次
        self.swipes_up(swip_num=3, sleep=2)
