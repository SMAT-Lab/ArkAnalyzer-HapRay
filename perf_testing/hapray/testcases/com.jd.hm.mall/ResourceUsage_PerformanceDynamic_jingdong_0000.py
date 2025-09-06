import time

from hypium import BY
from hapray.core.perf_testcase import PerfTestCase

class ResourceUsage_PerformanceDynamic_jingdong_0000(PerfTestCase):
    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(self.TAG, controllers)

        self._app_package = 'com.jd.hm.mall'
        self._app_name = '京东'
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
        self.driver.swipe_to_home()

        # Step('启动被测应用')
        self.driver.start_app(self.app_package)
        self.driver.wait(5)

        # 点击搜索框
        self.driver.touch(self.convert_coordinate(608, 315))
        time.sleep(2)
        # 搜索华为手机
        search_coords = self.convert_coordinate(475, 198)
        self.driver.input_text(search_coords, 'huawei pura70Pro 雪域白')
        self.driver.touch(BY.text('搜索'))
        time.sleep(2)
        # 点击type为{Text}并且text为{HUAWEI Pura 70 Pro 雪域白 12GB+512GB 超高速风驰闪拍 华为鸿蒙智能手机}的控件
        self.driver.touch(BY.type('Text').text('HUAWEI Pura 70 Pro 雪域白 12GB+512GB 超高速风驰闪拍 华为鸿蒙智能手机'))
        time.sleep(2)
        # 点击收藏
        self.driver.touch(self.convert_coordinate(1070,200))
        time.sleep(2)
        # 滑动返回
        self.driver.swipe_to_back()
        time.sleep(2)




        # 点击搜索框
        self.driver.touch(self.convert_coordinate(475, 198))
        time.sleep(2)
        #删除原来搜索内容
        self.driver.touch(self.convert_coordinate(867, 213))
        time.sleep(2)
        self.driver.input_text(search_coords, 'huawei mate70pro 黑色')
        self.driver.touch(BY.text('搜索'))
        time.sleep(2)
        # 点击type为{Text}并且text为{HUAWEI Mate 70 Pro 12GB+512GB曜石黑鸿蒙AI 红枫原色影像 超可靠玄武架构华为鸿蒙智能手机}的控件
        self.driver.touch(self.convert_coordinate(640, 1000))
        time.sleep(2)
        # 加入购物车
        self.driver.touch(self.convert_coordinate(515, 2588))
        time.sleep(2)
        # 点击type为{Text}并且text为{确认}的控件
        self.driver.touch(BY.type('Text').text('确认'))
        time.sleep(2)























