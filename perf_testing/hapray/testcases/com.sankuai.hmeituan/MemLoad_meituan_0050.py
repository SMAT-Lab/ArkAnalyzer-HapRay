import time

from devicetest.utils.file_util import get_resource_path
from hypium import BY
from hypium.model.basic_data_type import UiParam

from hapray.core.perf_testcase import PerfTestCase


class MemLoad_meituan_0050(PerfTestCase):
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
            # 1.打开美团，等待5s，修改定位地址为武汉
            self.driver.start_app(self.app_package)
            self.driver.wait(5)
            time.sleep(2)
            self.driver.touch_image(
                image_path_pc=get_resource_path('com_sankuai_hmeituan/position.jpeg'), similarity=0.7, wait_time=2
            )
            self.driver.touch(BY.text('搜索城市/区县'), wait_time=2)
            self.driver.input_text((698, 212), '武汉')
            time.sleep(2)
            self.driver.touch(BY.text('武汉'), wait_time=2)

        def step2():
            # 2.点击团购，等待2s
            self.driver.touch(BY.text('团购'), wait_time=2)

        def step3():
            # 3.团购页面上滑5次，下滑5次，每次间隔2s
            self.swipes_up(swip_num=5, sleep=2)
            self.swipes_down(swip_num=5, sleep=2)

        def step4():
            # 4.点击搜索框，等待2s，输入“蜜雪冰城（未来科技城（华为）店）”
            x, y = self.driver.get_component_pos(BY.text('搜索'))
            self.driver.touch((x - 299, y), wait_time=2)
            self.driver.input_text(BY.type('TextInput'), '奶茶')
            time.sleep(2)

        def step5():
            # 5.点击搜索结果，点击新客价，提交订单，等待2s
            self.driver.touch(BY.text('搜索'), wait_time=2)
            for _i in range(10):
                if self.driver.find_component(BY.text('新客价')):
                    break
                self.driver.swipe(UiParam.UP, distance=40, start_point=(0.5, 0.7), swipe_time=0.2)
                time.sleep(2)
            self.driver.touch(BY.text('新客价'), wait_time=2)
            self.driver.touch(BY.text('立即抢购'), wait_time=2)
            comp = self.driver.find_all_components(BY.text('提交订单'), -1)
            self.driver.touch(comp, wait_time=2)

        def step6():
            # 6.订单页返回，点击确认离开，等待2s
            self.driver.swipe_to_back()
            time.sleep(2)
            self.driver.touch(BY.text('确认离开'), wait_time=2)

        def step7():
            # 7.返回至首页，点击我的-全部订单，删除订单
            for _i in range(10):
                if self.driver.find_component(BY.text('酒店民宿')) and self.driver.find_component(BY.text('美食')):
                    break
                self.driver.swipe_to_back()
                time.sleep(1)
            self.driver.touch(BY.text('我的'), wait_time=2)
            self.driver.touch(BY.text('全部订单'), wait_time=2)
            self.driver.touch(BY.text('删除订单'), wait_time=2)
            self.driver.touch(BY.text('删除'), wait_time=2)

        self.execute_performance_step('美团-团购场景-step1打开美团，等待5s，修改定位地址为武汉', 10, step1)
        self.execute_performance_step('美团-团购场景-step2点击团购，等待2s', 10, step2)
        self.execute_performance_step('美团-团购场景-step3团购页面上滑5次，下滑5次，每次间隔2s', 30, step3)
        self.execute_performance_step(
            '美团-团购场景-step4点击搜索框，等待2s，输入“蜜雪冰城（未来科技城（华为）店）”', 10, step4
        )
        self.execute_performance_step('美团-团购场景-step5点击搜索结果，点击新客价，提交订单，等待2s', 10, step5)
        self.execute_performance_step('美团-团购场景-step6订单页返回，点击确认离开，等待2s', 10, step6)
        self.execute_performance_step('美团-团购场景-step7返回至首页，点击我的-全部订单，删除订单', 10, step7)
