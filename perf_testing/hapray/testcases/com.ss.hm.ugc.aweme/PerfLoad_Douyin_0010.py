import time

from hypium import BY

from hapray.core.perf_testcase import PerfTestCase


class PerfLoad_Douyin_0010(PerfTestCase):
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
            # 1. 打开抖音，等待 5s
            self.start_app()

            # 2. 搜索“李点点简笔画”， 进入该主页
            ret = self.touch_by_id('topTabsRightSlot')
            if not ret:
                self.touch_by_coordinates(1228, 200)

            self.driver.input_text(BY.type('TextInput'), '李点点简笔画')
            time.sleep(1)

            self.touch_by_text('搜索', 2)

            self.touch_by_text('李点点', 5)

        def step1():
            # 点开置顶的第一个视频（内容为画篮球，排球，足球，棒球);
            self.touch_by_coordinates(200, 2080, 3)

        def step2():
            # 点击评论图标，弹出评论界面
            # self.touch_by_text('2.4万', 2)
            self.touch_by_coordinates(998, 1452, 2)

            # 点击空白处，收起评论界面
            self.touch_by_coordinates(500, 576, 2)

        def step3():
            # 在评论界面开始上滑，每1s滑动一次，先下滑10次，再上滑10次，共20次
            self.swipes_up(10, 1)
            self.swipes_down(10, 1)

        def step4():
            # 点击输入框，收起输入框，反复操作10次，每次间隔1s
            for _ in range(10):
                self.touch_by_text('善语结善缘，恶语伤人心', 1)
                self.touch_by_coordinates(500, 576, 1)

        start()
        self.execute_performance_step('抖音-短视频浏览评论场景-step1点击观看历史', 10, step1)
        # 暂停播放视频
        self.touch_by_id('MAIN_SHELL_ID', 1)

        self.execute_performance_step('抖音-短视频浏览评论场景-step2评论界面弹出/收起', 10, step2)

        # 点击评论图标，弹出评论界面, 预先上滑/下滑一轮后再抓取
        # self.touch_by_text('2.4万', 2)
        self.touch_by_coordinates(998, 1452, 2)
        self.swipes_up(10, 1)
        self.swipes_down(10, 1)

        # self.touch_by_text('2.4万', 2)
        self.touch_by_coordinates(998, 1452, 2)
        self.execute_performance_step('抖音-短视频浏览评论场景-step3评论内容浏览', 40, step3)

        # self.touch_by_text('2.4万', 2)
        self.touch_by_coordinates(998, 1452, 2)
        self.execute_performance_step('抖音-短视频浏览评论场景-step4输入框弹出/收起', 35, step4)
