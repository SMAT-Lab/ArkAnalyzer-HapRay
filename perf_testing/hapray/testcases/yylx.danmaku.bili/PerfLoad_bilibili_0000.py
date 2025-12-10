import time

from hypium import BY

from hapray.core.perf_testcase import PerfTestCase


class PerfLoad_bilibili_0000(PerfTestCase):
    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(self.TAG, controllers)
        self._app_package = 'yylx.danmaku.bili'
        self._app_name = '哔哩哔哩'
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
        # 启动被测应用
        self.start_app()

        # 0020前置条件
        # 点击搜索框
        self.driver.touch(self.convert_coordinate(535, 177))
        time.sleep(2)

        # 搜索航拍中国 第一季
        search_coords = self.convert_coordinate(500, 193)
        self.driver.input_text(search_coords, '航拍中国 第一季')
        self.driver.touch(BY.text('搜索'))
        time.sleep(4)

        # 点击播放”航拍中国 第一季“
        self.driver.touch(self.convert_coordinate(192, 830))
        time.sleep(2)

        # 关注第一集新疆
        self.driver.touch(self.convert_coordinate(543, 1166))
        time.sleep(2)

        # 滑动返回
        self.driver.swipe_to_back()
        time.sleep(2)
        self.driver.swipe_to_back()
        time.sleep(2)

        # 关注EDIFIER漫步者
        search_coords = self.convert_coordinate(500, 193)
        self.driver.input_text(search_coords, 'EDIFIER漫步者')
        self.driver.touch(BY.text('搜索'))
        time.sleep(3)

        # 点击用户
        self.driver.touch(self.convert_coordinate(700, 310))
        time.sleep(2)
        # 点击关注
        self.driver.touch(self.convert_coordinate(937, 498))
        time.sleep(2)
        # 点击空白处
        self.driver.touch(self.convert_coordinate(500, 1200))
        time.sleep(2)

        # 滑动返回
        self.driver.swipe_to_back()
        time.sleep(2)

        # 0030前置条件
        # 搜索视频 “当各省风景出现在课本上”
        search_coords = self.convert_coordinate(500, 193)
        self.driver.input_text(search_coords, '“当各省风景出现在课本上”')
        self.driver.touch(BY.text('搜索'))
        time.sleep(3)

        # 点击播放”当各省风景出现在课本上“
        self.driver.touch(self.convert_coordinate(759, 637))
        time.sleep(2)
        # 关注视频
        self.driver.touch(self.convert_coordinate(747, 2141))
        time.sleep(2)

        # 滑动返回
        self.driver.swipe_to_back()
        time.sleep(2)
        self.driver.swipe_to_back()
        time.sleep(2)

        # 0050前置条件
        # 搜索 哔哩哔哩王者荣耀赛事
        search_coords = self.convert_coordinate(500, 193)
        self.driver.input_text(search_coords, '哔哩哔哩王者荣耀赛事')
        self.driver.touch(BY.text('搜索'))
        time.sleep(3)

        # 点击用户
        self.driver.touch(self.convert_coordinate(700, 310))
        time.sleep(2)
        # 点击关注
        self.driver.touch(self.convert_coordinate(937, 498))
        time.sleep(2)
        # 点击空白处
        self.driver.touch(self.convert_coordinate(500, 1200))
        time.sleep(2)
