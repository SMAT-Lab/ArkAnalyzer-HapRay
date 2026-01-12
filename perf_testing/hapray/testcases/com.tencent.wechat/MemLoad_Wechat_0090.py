import time

from hypium import BY
from hypium.model.basic_data_type import MatchPattern, UiParam

from hapray.core.perf_testcase import PerfTestCase


class MemLoad_Wechat_0090(PerfTestCase):
    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(self.TAG, controllers)

        self._app_package = 'com.tencent.wechat'
        self._app_name = '微信'
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
            # 1.打开微信（等待5s）
            self.start_app()
            time.sleep(5)

        def step2():
            # 2.进入小程序选择页面：下滑调出最新小程序页面（等待2s）
            self.driver.swipe(UiParam.DOWN, distance=100, start_point=(0.52, 0.34))
            time.sleep(2)

        def step3():
            # 3.点击喜茶小程序：喜茶（等待5s）
            self.touch_by_text('喜茶GO', 5)

        def step4():
            # 4.进入商品界面：点击到店取（等待2s）
            if self.driver.wait_for_component(BY.text('同意'), timeout=3):
                self.touch_by_text('同意', 2)

            if self.driver.wait_for_component(BY.text('允许'), timeout=3):
                self.touch_by_text('允许', 2)

            if self.driver.wait_for_component(BY.text('到店取'), timeout=3):
                self.touch_by_text('到店取', 2)
            else:
                self.driver.touch((0.26, 0.74), wait_time=2)
            if self.driver.find_component(BY.text('时令上新')) and (not self.driver.find_component(BY.text('点单'))):
                self.driver.touch((626, 2624), wait_time=2)  # 领卷弹框

        def step5():
            # 5.页面浏览：上下滑动3次（等待2s）
            if self.driver.wait_for_component(BY.text('<UNK>'), timeout=3):
                self.driver.touch((1196 / 1260, 1984 / 2844))
                time.sleep(2)
            self.swipes_up(3, 2)
            self.swipes_down(3, 2)

        def step6():
            # 6.返回微信首页（等待2s）
            self.driver.swipe_to_back()
            time.sleep(2)

        def step7():
            # 7.进入小程序选择页面：下滑调出最新小程序页面（等待2s）
            for _i in range(5):
                if self.driver.find_component(BY.text('通讯录')) and self.driver.find_component(BY.text('我')):
                    break
                self.driver.swipe_to_back()
                time.sleep(1)
            self.driver.swipe(UiParam.DOWN, distance=100, start_point=(0.52, 0.34))
            time.sleep(2)

        def step8():
            # 8.进入小程序选择页面：下滑调出最近小程序页面（等待2s）
            self.driver.touch(BY.text('蜜雪冰城', MatchPattern.CONTAINS), wait_time=5)

        def step9():
            # 9.进入点餐界面：点击【点餐】（等待2s）
            if self.driver.find_component(BY.text('允许')):
                self.touch_by_text('允许', 2)
            if self.driver.find_component(BY.text('点餐')):
                self.touch_by_text('点餐', 2)
            else:
                self.driver.touch((0.37, 0.94), wait_time=2)

            if self.driver.find_component(BY.text('确认门店')):
                self.touch_by_text('确认门店', 1)
            else:
                self.driver.touch((0.50, 0.50), wait_time=1)

        def step10():
            # 10.页面浏览：上下滑动3次（等待2s）
            self.swipes_up(3, 2)
            self.swipes_down(3, 2)

        self.execute_performance_step('微信-小程序浏览场景-step1打开微信', 10, step1)
        self.execute_performance_step(
            '微信-小程序浏览场景-step2进入小程序选择页面：下滑调出最新小程序页面（等待2s）', 10, step2
        )
        self.execute_performance_step('微信-小程序浏览场景-step3点击喜茶小程序：喜茶（等待5s）', 10, step3)
        self.execute_performance_step('微信-小程序浏览场景-step4进入商品界面：点击到店取（等待2s））', 15, step4)
        self.execute_performance_step('微信-小程序浏览场景-step5页面浏览：上下滑动3次（等待2s）', 20, step5)
        self.execute_performance_step('微信-小程序浏览场景-step6返回微信首页（等待2s）', 10, step6)
        self.execute_performance_step(
            '微信-小程序浏览场景-step7进入小程序选择页面：下滑调出最新小程序页面（等待2s）', 10, step7
        )
        self.execute_performance_step(
            '微信-小程序浏览场景-step8进入小程序选择页面：下滑调出最近小程序页面（等待2s）', 10, step8
        )
        self.execute_performance_step('微信-小程序浏览场景-step9进入点餐界面：点击【点餐】（等待2s）', 15, step9)
        self.execute_performance_step('微信-小程序浏览场景-step10页面浏览：上下滑动3次（等待2s）', 20, step10)
