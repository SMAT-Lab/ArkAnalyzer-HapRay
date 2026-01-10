import time

from devicetest.utils.file_util import get_resource_path
from hypium import BY
from hypium.model.basic_data_type import UiParam

from hapray.core.perf_testcase import PerfTestCase


class MemLoad_jingdong_0050(PerfTestCase):
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

        def step1():
            # 1.启动京东（等待5s）
            self.driver.start_app(self.app_package)
            self.driver.wait(5)

        def step2():
            # 2.进入京东超市：左滑频道（列表（等待2s），点击“全部频道”（等待5s），上滑找到京东超市（等待2s），点击“京东超市”（等待5s）
            if self.driver.find_component(BY.type('ListItem')):
                self.driver.swipe(UiParam.LEFT, area=BY.type('ListItem'))
                time.sleep(2)
                self.driver.touch(BY.text('全部频道'), wait_time=2)
                for _i in range(8):
                    if self.driver.find_component(BY.text('京东超市')):
                        break
                    self.driver.swipe(UiParam.UP, distance=20)
                    time.sleep(2)
            else:
                component_str_list = ['秒杀', '领券', '省钱卡', '京东超市', '充值中心']
                for component_str in component_str_list:
                    if self.driver.find_component(BY.text(component_str)):
                        _, y = self.driver.find_component_pos(BY.text(component_str))
                        break

                for _i in range(2):
                    self.driver.swipe('LEFT', start_point=(858, y))
                    time.sleep(2)
                    if self.driver.find_component(BY.text('全部频道')):
                        break

                self.driver.touch(BY.text('全部频道'), wait_time=2)
                for _i in range(8):
                    self.driver.swipe(UiParam.UP, distance=20)
                    if self.driver.find_component(BY.text('京东超市')):
                        break

            self.driver.touch(BY.text('京东超市'), wait_time=2)

        def step3():
            # 3.进入粮油调味页面：点击上方粮油调味（等待5s）
            if self.driver.find_component(BY.text('京东超市，查收返礼')):
                self.driver.swipe_to_back()
                time.sleep(2)
            if self.driver.find_component(BY.text('再看看')):
                self.driver.touch(BY.text('再看看'), wait_time=2)
            self.driver.touch(BY.text('粮油调味'), wait_time=5)

        def step4():
            # 4.页面浏览：上滑5次，下滑6次（间隔2s）
            self.driver.check_component_exist(BY.text('南北干货'))
            self.swipes_up(swip_num=5, sleep=2)
            self.swipes_down(swip_num=6, sleep=2)

        def step5():
            # 5.将第一个商品加入购物车，返回京东购物首页：点击加号（等待2s），返回（等待2s）
            if self.driver.find_image(
                image_path_pc=get_resource_path('com_jd_hm_mall/add.png'), mode='template', similarity=0.6
            ):
                self.driver.touch_image(
                    image_path_pc=get_resource_path('com_jd_hm_mall/add.png'), similarity=0.6, wait_time=2
                )
            else:
                x, y = self.driver.get_component_pos(BY.text('￥'))
                self.driver.touch((x + 563, y), wait_time=2)

            for _i in range(5):
                if self.driver.find_component(BY.text('购物车')):
                    break
                self.driver.swipe_to_back()
                time.sleep(2)

        def step6():
            # 6.进入结算界面：点击购物车（等待2s），点击去结算（等待2s）
            self.driver.touch(BY.text('购物车'), wait_time=2)
            self.driver.touch(BY.text('去结算'), wait_time=2)

        def step7():
            # 7.删除购物车：返回（等待1s），对商品左滑（等待1s），点击删除（等待1s）
            self.driver.swipe_to_back()
            time.sleep(1)
            x, y = self.driver.get_component_pos(BY.type('ListItemGroup'))
            self.driver.swipe(UiParam.LEFT, start_point=(x + 400, y + 180))
            self.driver.touch(BY.text('删除'), wait_time=2)

        self.execute_performance_step('京东-京东超市场景-step1启动京东（等待5s）', 10, step1, sample_all_processes=True)
        self.execute_performance_step(
            '京东-京东超市场景-step2进入京东超市：左滑频道（列表（等待2s），点击“全部频道”（等待5s），上滑找到京东超市（等待2s），点击“京东超市”（等待5s）',
            10,
            step2,
        )
        self.execute_performance_step('京东-京东超市场景-step3进入粮油调味页面：点击上方粮油调味（等待5s）', 10, step3)
        self.execute_performance_step('京东-京东超市场景-step4页面浏览：上滑5次，下滑6次（间隔2s）', 30, step4)
        self.execute_performance_step(
            '京东-京东超市场景-step5将第一个商品加入购物车，返回京东购物首页：点击加号（等待2s），返回（等待2s）',
            10,
            step5,
        )
        self.execute_performance_step(
            '京东-京东超市场景-step6进入结算界面：点击购物车（等待2s），点击去结算（等待2s）', 10, step6
        )
        self.execute_performance_step(
            '京东-京东超市场景-step7删除购物车：返回（等待1s），对商品左滑（等待1s），点击删除（等待1s）', 10, step7
        )
