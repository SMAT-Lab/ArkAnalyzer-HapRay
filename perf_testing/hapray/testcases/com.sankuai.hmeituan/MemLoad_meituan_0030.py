import time

from hypium import BY
from hypium.model.basic_data_type import MatchPattern

from hapray.core.perf_testcase import PerfTestCase


class MemLoad_meituan_0030(PerfTestCase):
    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(self.TAG, controllers)

        self._app_package = 'com.sankuai.hmeituan'
        self._app_name = '美团'
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

        def step1():
            # 1.打开美团，等待5s
            self.driver.start_app(self.app_package)
            self.driver.wait(5)
            time.sleep(2)

        def step2():
            # 2.点击搜索，等待2s
            x, y = self.driver.get_component_pos(BY.text('搜索'))
            self.driver.touch((x - 299, y), wait_time=2)

        def step3():
            # 3.输入“蜜雪冰城”点击搜索，等待2s
            self.driver.input_text(BY.type('TextInput'), '蜜雪冰城')
            time.sleep(2)
            self.driver.touch(BY.text('搜索'), wait_time=2)

        def step4():
            # 4.搜索界面上滑动5次，等待2s
            self.swipes_up(swip_num=5, sleep=2)

        def step5():
            # 5.搜索界面下滑动5次，等待2s
            self.swipes_down(swip_num=5, sleep=2)

        def step6():
            # 6.点击“米雪冰城华为店”，等待2s
            self.driver.touch(BY.text('到店'), wait_time=2)
            com = self.driver.find_all_components(BY.text('蜜雪冰城', MatchPattern.STARTS_WITH), 1)
            self.driver.touch(com, wait_time=2)

        def step7():
            # 7.页面上滑动5次，等待2s
            self.swipes_up(swip_num=5, sleep=2)

        def step8():
            # 8.页面下滑动5次，等待2s
            self.swipes_down(swip_num=5, sleep=2)

        def step9():
            # 9.点击评价-更多评价
            self.driver.touch(BY.text('评价'), wait_time=2)
            self.driver.touch(BY.text('更多评价'), wait_time=2)

        def step10():
            # 10.评价页上滑5次，下滑5次，每次间隔2s
            self.swipes_up(swip_num=5, sleep=2)
            self.swipes_down(swip_num=5, sleep=2)

        self.execute_performance_step('美团-店铺滑动浏览场景-step1打开美团，等待5s', 10, step1)
        self.execute_performance_step('美团-店铺滑动浏览场景-step2点击搜索，等待2s', 5, step2)
        self.execute_performance_step('美团-店铺滑动浏览场景-step3输入“蜜雪冰城”点击搜索，等待2s', 5, step3)
        self.execute_performance_step('美团-店铺滑动浏览场景-step4搜索界面上滑动5次，等待2s', 20, step4)
        self.execute_performance_step('美团-店铺滑动浏览场景-step5搜索界面下滑动5次，等待2s', 20, step5)
        self.execute_performance_step('美团-店铺滑动浏览场景-step6点击“米雪冰城华为店”，等待2s', 10, step6)
        self.execute_performance_step('美团-店铺滑动浏览场景-step7页面上滑动5次，等待2s', 20, step7)
        self.execute_performance_step('美团-店铺滑动浏览场景-step8页面下滑动5次，等待2s', 20, step8)
        self.execute_performance_step('美团-店铺滑动浏览场景-step9点击评价-更多评价', 10, step9)
        self.execute_performance_step('美团-店铺滑动浏览场景-step10评价页上滑5次，下滑5次，每次间隔2ss', 30, step10)
