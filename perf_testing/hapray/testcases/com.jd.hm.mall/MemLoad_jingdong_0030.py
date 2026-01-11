import time

from hypium import BY

from hapray.core.perf_testcase import PerfTestCase


class MemLoad_jingdong_0030(PerfTestCase):
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
            # 2.点击搜索、输入搜索内容：点击搜索框（等待2s），输入“华为手机”（等待1s）
            x, y = self.driver.get_component_pos(BY.text('搜索'))
            self.driver.touch((x - 600, y), wait_time=2)
            self.driver.input_text(BY.type('TextInput'), '华为手机')
            time.sleep(1)

        def step3():
            # 3.进行搜索：点击搜索（等待4s）
            self.driver.touch(BY.text('搜索'), wait_time=4)

        def step4():
            # 4.搜索结果浏览：上滑5次、下滑6次（间隔2s）
            self.driver.check_component_exist(BY.text('销量'))
            self.swipes_up(swip_num=5, sleep=2)
            self.swipes_down(swip_num=6, sleep=2)

        def step5():
            # 5.销量排序：点击“销量”（等待2s）
            self.driver.touch(BY.text('销量'), wait_time=2)

        self.execute_performance_step('京东-搜索商品场景-step1启动京东（等待5s）', 10, step1, sample_all_processes=True)
        self.execute_performance_step(
            '京东-搜索商品场景-step2点击搜索、输入搜索内容：点击搜索框（等待2s），输入“华为手机”（等待1s）', 10, step2
        )
        self.execute_performance_step('京东-搜索商品场景-step3进行搜索：点击搜索（等待4s）', 10, step3)
        self.execute_performance_step('京东-搜索商品场景-step4搜索结果浏览：上滑5次、下滑6次（间隔2s）', 30, step4)
        self.execute_performance_step('京东-搜索商品场景-step5销量排序：点击“销量”（等待2s）', 10, step5)
