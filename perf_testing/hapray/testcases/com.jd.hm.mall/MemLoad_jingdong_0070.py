from hypium import BY

from hapray.core.perf_testcase import PerfTestCase


class MemLoad_jingdong_0070(PerfTestCase):
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
            # 2.进入相册页面：点击搜索框相机按钮（等待2s）
            x, y = self.driver.get_component_pos(BY.text('搜索'))
            self.driver.touch((x - 143, y), wait_time=2)

        def step3():
            # 3.选择图片：点击所有相册（等待1s），点击“购物”（等待2s），选择第一张图片（等待2s），点击完成（等待2s）
            self.driver.touch(BY.text('所有相册'), wait_time=1)
            self.driver.touch(BY.text('购物'), wait_time=2)
            self.driver.touch((0.13, 0.19), wait_time=2)
            self.driver.touch(BY.text('完成'), wait_time=2)

        def step4():
            # 4.搜索结果浏览：向上滑动3次（间隔2s）
            self.driver.check_component_exist(BY.text('为您找到一下相似商品'))
            self.swipes_up(swip_num=3, sleep=2)

        self.execute_performance_step('京东-查看相册场景-step1启动京东（等待5s）', 10, step1, sample_all_processes=True)
        self.execute_performance_step('京东-查看相册场景-step2进入相册页面：点击搜索框相机按钮（等待2s）', 10, step2)
        self.execute_performance_step(
            '京东-查看相册场景-step3选择图片：点击所有相册（等待1s），点击“购物”（等待2s），选择第一张图片（等待2s），点击完成（等待2s）',
            20,
            step3,
        )
        self.execute_performance_step('京东-查看相册场景-step4搜索结果浏览：向上滑动3次（间隔2s）', 20, step4)
