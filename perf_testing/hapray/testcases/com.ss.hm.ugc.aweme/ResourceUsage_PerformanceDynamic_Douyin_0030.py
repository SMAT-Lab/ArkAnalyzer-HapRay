# coding: utf-8
import time

from hypium import BY

from hapray.core.perf_testcase import PerfTestCase


class ResourceUsage_PerformanceDynamic_Douyin_0030(PerfTestCase):

    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(self.TAG, controllers)

        self._app_package = 'com.ss.hm.ugc.aweme'
        self._app_name = '抖音'
        self._steps = [
            {
                "name": "step1",
                "description": "1. 点击播放置顶视频"
            },
            {
                "name": "step2",
                "description": "2. 评论界面弹出/收起"
            },
            {
                "name": "step3",
                "description": "3. 评论内容浏览"
            },
            {
                "name": "step4",
                "description": "4. 输入框弹出/收起"
            }
        ]
        # 原始采集设备的屏幕尺寸（Pura 70 Pro）
        self.source_screen_width = 1260
        self.source_screen_height = 2844

    @property
    def steps(self) -> list[dict[str, str]]:
        return self._steps

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

            ret = self.touch_by_id('search_button', 3)
            if not ret:
                self.touch_by_coordinates(1196, 196, 3)

            ret = self.touch_by_text('李点点', 5)
            if not ret:
                self.touch_by_coordinates(306, 411, 5)

        def step1():
            # 点开置顶的第一个视频（内容为画篮球，排球，足球，棒球);
            self.touch_by_coordinates(200, 2000, 3)

        def step2():
            # 点击评论图标，弹出评论界面
            self.touch_by_text('2.4万', 2)

            # 点击空白处，收起评论界面
            self.touch_by_coordinates(630, 338, 2)

        def step3():
            # 在评论界面开始上滑，每1s滑动一次，先下滑10次，再上滑10次，共20次
            self.swipes_up(10, 1)
            self.swipes_down(10, 1)

        def step4():
            # 点击输入框，收起输入框，反复操作10次，每次间隔1s
            for _ in range(10):
                self.touch_by_text('善语结善缘，恶语伤人心', 1)
                self.touch_by_coordinates(630, 338, 1)

        start()
        self.execute_performance_step(1, step1, 10)
        # 暂停播放视频
        self.touch_by_id('MAIN_SHELL_ID', 1)

        self.execute_performance_step(2, step2, 10)

        # 点击评论图标，弹出评论界面, 预先上滑/下滑一轮后再抓取
        self.touch_by_text('2.4万', 2)
        self.swipes_up(10, 1)
        self.swipes_down(10, 1)

        self.touch_by_text('2.4万', 2)
        self.execute_performance_step(3, step3, 40)

        self.touch_by_text('2.4万', 2)
        self.execute_performance_step(4, step4, 35)
