import time

from hypium import BY

from hapray.core.perf_testcase import PerfTestCase


class PerfLoad_taobao_0080(PerfTestCase):
    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(self.TAG, controllers)

        self._app_package = 'com.taobao.taobao4hmos'
        self._app_name = '淘宝'
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

        # Step('启动被测应用')
        self.driver.start_app(self.app_package)
        self.driver.wait(5)

        def step1():
            self.driver.touch(BY.text('闪购'))
            self.driver.wait(2)
            time.sleep(2)
             # 更换定位
            self.driver.touch(self.convert_coordinate(125, 406))
            time.sleep(2)
            #self.driver.touch(BY.text('西安半导体产业园E2栋'))
            self.driver.touch(self.convert_coordinate(390, 729))
            self.driver.wait(2)
            # Step('关注页，上滑5次')
            self.swipes_up(swip_num=5, sleep=3)
            # Step('关注页，下滑5次')
            self.swipes_down(swip_num=5, sleep=3)

        def step2():
            # 点击搜索框
            self.driver.touch(self.convert_coordinate(473, 300))
            time.sleep(2)

            # 搜索蜜雪冰城
            search_coords = self.convert_coordinate(475, 198)
            self.driver.input_text(search_coords, 'kfc肯德基')
            self.driver.wait(2)
            self.driver.touch(self.convert_coordinate(962, 177))
            self.driver.wait(2)
            #self.driver.touch(BY.text('搜索'))
            time.sleep(2)
            # 点击第一家店铺
            self.driver.touch(self.convert_coordinate(390, 660))
            self.driver.wait(2)
            time.sleep(2)
            # 点击放大镜
            # self.driver.touch(self.convert_coordinate(560, 200))
            # time.sleep(2)
            search_coords = self.convert_coordinate(475, 198)
            self.driver.input_text(search_coords, '黄金SPA鸡排堡1人大满足')
            #self.driver.touch(BY.text('搜索'))
            self.driver.touch(self.convert_coordinate(873, 154))
            time.sleep(2)

            # self.driver.touch(BY.text('选规格'))
            # time.sleep(2)
            # +号
            self.driver.touch(self.convert_coordinate(1020, 506))
            time.sleep(1)
            # self.driver.touch(self.convert_coordinate(1020, 1218))
            # time.sleep(1)
            # self.driver.touch(self.convert_coordinate(1020, 1218))
            # time.sleep(1)
            # self.driver.touch(BY.text('加入购物车'))
            # time.sleep(2)
            #self.driver.touch(BY.text('去结算'))
            self.driver.touch(self.convert_coordinate(904, 2236))
            time.sleep(3)
            # self.driver.touch(BY.text('提交订单'))
            # time.sleep(2)
            self.driver.touch(self.convert_coordinate(540, 2250))
            time.sleep(3)
            self.driver.touch(self.convert_coordinate(540, 2250))
            time.sleep(8)
            # 关闭付款
            self.driver.touch(self.convert_coordinate(68, 1354))
            time.sleep(3)
            # 放弃
            self.driver.touch(self.convert_coordinate(346, 1300))
            time.sleep(3)
            #self.driver.touch(BY.text('取消订单'))
            self.driver.touch(self.convert_coordinate(880, 873))
            time.sleep(3)
            # self.driver.touch(BY.text('仍要取消'))
            self.driver.touch(self.convert_coordinate(538, 2263))
            time.sleep(3)

        self.execute_performance_step('淘宝-闪购-step1闪购页面上下滑动', 50, step1)
        self.execute_performance_step('淘宝-闪购-step1闪购页面下单', 50, step2)
