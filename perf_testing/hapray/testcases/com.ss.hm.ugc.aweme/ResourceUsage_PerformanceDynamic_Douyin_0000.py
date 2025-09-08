import time

from hypium import BY
from hapray.core.perf_testcase import PerfTestCase


class ResourceUsage_PerformanceDynamic_Douyin_0000(PerfTestCase):
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
        def start():
            # '启动被测应用'
            self.start_app()

             # 浏览推荐视频, 上滑5次
            self.swipes_up(5, 1)

            #0120前置条件
            # 点击搜索框
            self.driver.touch(self.convert_coordinate(1013, 179))
            time.sleep(2)

            # 搜索与辉同行
            search_coords = self.convert_coordinate(500, 193)
            self.driver.input_text(search_coords, '与辉同行')
            self.driver.touch(BY.text('搜索'))
            time.sleep(4)

            #点击进入与辉同行主页
            self.driver.touch(self.convert_coordinate(300, 350))
            time.sleep(2)

            #关注与辉同行
            self.driver.touch(self.convert_coordinate(550, 1265))
            time.sleep(2)

            # 滑动返回
            self.driver.swipe_to_back()
            time.sleep(2)
            self.driver.swipe_to_back()
            time.sleep(2)
            self.driver.swipe_to_back()
            time.sleep(2)
            self.driver.swipe_to_back()
            time.sleep(2)
            
            #0110前置条件
            #点击+
            self.driver.touch(self.convert_coordinate(533, 2261))
            time.sleep(2)
            #录制视频
            self.driver.touch(self.convert_coordinate(533, 1990))
            time.sleep(5)
            self.driver.touch(self.convert_coordinate(533, 1990))
            time.sleep(1)
            #下一步
            self.driver.touch(BY.text('下一步'))
            time.sleep(1)
            self.driver.touch(self.convert_coordinate(509, 1517))
            time.sleep(1)

            #设置仅自己可见
            self.driver.touch(self.convert_coordinate(509, 1809))
            time.sleep(1)
            #发布
            self.driver.touch(BY.text('发布'))
            time.sleep(1)

            #抖音点击“我”，等待 2s
            self.touch_by_text('我')
            time.sleep(2)
            #点击私密
            self.touch_by_text('私密')
            time.sleep(1)
            #打开第一条视频
            self.driver.touch(self.convert_coordinate(185, 1788))
            time.sleep(1)

            #打开评论区
            self.driver.touch(self.convert_coordinate(975, 1548))
            time.sleep(1)

            #去评论
            self.touch_by_text('去评论')
            time.sleep(1)
            #选择图片
            self.driver.touch(self.convert_coordinate(90, 1409))
            time.sleep(3)
            #拍照
            self.driver.touch(self.convert_coordinate(110, 458))
            time.sleep(2)
            #拍照
            self.driver.touch(self.convert_coordinate(529, 2090))
            time.sleep(3)
            #确认图片
            self.driver.touch(self.convert_coordinate(925, 2085))
            time.sleep(3)
            #选择图片
            self.driver.touch(self.convert_coordinate(400, 440))
            time.sleep(3)
            #发送图片评论
            self.touch_by_text('发送')
            time.sleep(2)

            # 滑动返回
            self.driver.swipe_to_back()
            time.sleep(2)
            self.driver.swipe_to_back()
            time.sleep(2)
            self.driver.swipe_to_back()
            time.sleep(2)

            #0160前置条件
            # 点击搜索框
            self.driver.touch(self.convert_coordinate(1013, 179))
            time.sleep(2)

            # 搜索爱吃豆腐取图看主页
            search_coords = self.convert_coordinate(500, 193)
            self.driver.input_text(search_coords, '爱吃豆腐取图看主页')
            self.driver.touch(BY.text('搜索'))
            time.sleep(2)

            #点击进入爱吃豆腐取图看主页主页
            self.driver.touch(self.convert_coordinate(327, 392))
            time.sleep(2)
            #点击置顶第一个视频
            self.driver.touch(self.convert_coordinate(185, 1582))
            time.sleep(2)
            #收藏视频
            self.driver.touch(self.convert_coordinate(995, 1563))
            time.sleep(1)
            self.driver.touch(self.convert_coordinate(500, 1563))
            time.sleep(1)
            self.swipes_up(1, 2)
            self.driver.touch(self.convert_coordinate(995, 1563))
            time.sleep(1)
            self.driver.touch(self.convert_coordinate(500, 1563))
            time.sleep(1)
            self.swipes_up(1, 2)
            self.driver.touch(self.convert_coordinate(995, 1563))
            time.sleep(1)
            self.driver.touch(self.convert_coordinate(500, 1563))
            time.sleep(1)
            self.swipes_up(1, 2)
            self.driver.touch(self.convert_coordinate(995, 1563))
            time.sleep(1)
            self.driver.touch(self.convert_coordinate(500, 1563))
            time.sleep(1)
            self.swipes_up(1, 2)
            self.driver.touch(self.convert_coordinate(995, 1563))
            time.sleep(1)
            self.driver.touch(self.convert_coordinate(500, 1563))
            time.sleep(1)

            # 滑动返回
            self.driver.swipe_to_back()
            time.sleep(2)
            self.driver.swipe_to_back()
            time.sleep(2)
            self.driver.swipe_to_back()
            time.sleep(2)
            
            # 搜索Dear-迪丽热巴
            search_coords = self.convert_coordinate(500, 193)
            self.driver.input_text(search_coords, 'Dear-迪丽热巴')
            self.driver.touch(BY.text('搜索'))
            time.sleep(2)

            #点击进入Dear-迪丽热巴
            self.driver.touch(self.convert_coordinate(327, 392))
            time.sleep(2)
            #点击置顶第一个视频
            self.driver.touch(self.convert_coordinate(185, 1582))
            time.sleep(2)
            #收藏视频
            self.driver.touch(self.convert_coordinate(995, 1563))
            time.sleep(1)
            self.driver.touch(self.convert_coordinate(500, 1563))
            time.sleep(1)
            self.swipes_up(1, 1)
            time.sleep(1)
            self.driver.touch(self.convert_coordinate(995, 1665))
            time.sleep(1)
            self.driver.touch(self.convert_coordinate(500, 1563))
            time.sleep(1)
            self.swipes_up(1, 1)
            time.sleep(1)
            self.driver.touch(self.convert_coordinate(995, 1665))
            time.sleep(1)
            self.driver.touch(self.convert_coordinate(500, 1563))
            time.sleep(1)
            self.swipes_up(1, 1)
            time.sleep(1)
            self.driver.touch(self.convert_coordinate(995, 1665))
            time.sleep(1)
            self.driver.touch(self.convert_coordinate(500, 1563))
            time.sleep(1)
            self.swipes_up(1, 1)
            time.sleep(1)
            self.driver.touch(self.convert_coordinate(995, 1563))
            time.sleep(1)
            self.driver.touch(self.convert_coordinate(500, 1563))
            time.sleep(1)

        start()

