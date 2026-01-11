from hypium import BY

from hapray.core.perf_testcase import PerfTestCase


class MemLoad_jingdong_0060(PerfTestCase):
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
            # 2.进入直播界面：点击逛（等待2s），点击直播（等待2s）
            self.driver.touch(BY.text('逛'), wait_time=2)
            self.driver.touch(BY.text('直播'), wait_time=2)

        def step3():
            # 3.直播页面浏览：上滑5次、下滑6次（间隔2s）
            self.driver.check_component_exist(BY.text('采销直播'))
            self.swipes_up(swip_num=5, sleep=2)
            self.swipes_down(swip_num=6, sleep=2)

        def step4():
            # 4.进入第一个直播间，观看10s：点击第一个直播间（等待10s）
            self.driver.touch(BY.type('FlowItem'), wait_time=10)

        def step5():
            # 5.直播间切换：上滑5次（间隔2s）
            self.driver.check_component_exist(BY.text('聊一聊...'))
            self.swipes_up(swip_num=5, sleep=2)

        self.execute_performance_step('京东-观看直播场景-step1启动京东（等待5s）', 10, step1, sample_all_processes=True)
        self.execute_performance_step(
            '京东-观看直播场景-step2进入直播界面：点击逛（等待2s），点击直播（等待2s）', 10, step2
        )
        self.execute_performance_step('京东-观看直播场景-step3直播页面浏览：上滑5次、下滑6次（间隔2s）', 30, step3)
        self.execute_performance_step(
            '京东-观看直播场景-step4进入第一个直播间，观看10s：点击第一个直播间（等待10s）', 20, step4
        )
        self.execute_performance_step('京东-观看直播场景-step5直播间切换：上滑5次（间隔2s）', 20, step5)
