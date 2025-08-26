from hapray.core.perf_testcase import PerfTestCase


class ResourceUsage_PerformanceDynamic_xhs_0100(PerfTestCase):
    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(self.TAG, controllers)

        self._app_package = 'com.xingin.xhs_hos'
        self._app_name = '小红书'
        # 原始采集设备的屏幕尺寸（Nova14）
        self.source_screen_width = 1084
        self.source_screen_height = 2412

    @property
    def app_package(self) -> str:
        return self._app_package

    @property
    def app_name(self) -> str:
        return self._app_name

    def process(self):
        self.start_app()
        self.touch_by_text('购物', 2)

        def step1():
            self.swipes_up(5, 3, 300)
            self.swipes_down(5, 3, 300)

        def step2():
            # 点击进去购物车
            self.touch_by_text('购物车')
            self.swipes_up(5, 3, 300)
            self.swipes_down(5, 3, 300)

        def step3():
            # 进入商品详情页，上下滑动5次
            self.touch_by_text(' 美的 · 电压力锅鸳鸯内胆家用多功能智能4L大容量蒸煮一体高压锅推荐', 1)
            self.swipes_up(5, 2, 300)
            self.swipes_down(5, 2, 300)

        self.execute_performance_step('小红书-购物浏览场景-step1购物页浏览', 45, step1)
        self.execute_performance_step('小红书-购物浏览场景-step2购物车列表浏览', 45, step2)

        self.swipes_down(1, 1, 300)
        # 点击进入美的生活小家电旗舰店
        self.touch_by_text('美的生活小家电旗舰店', 2)
        self.find_by_text_up(' 美的 · 电压力锅鸳鸯内胆家用多功能智能4L大容量蒸煮一体高压锅推荐')
        self.execute_performance_step('小红书-购物浏览场景-step3商品详情页浏览', 35, step3)
