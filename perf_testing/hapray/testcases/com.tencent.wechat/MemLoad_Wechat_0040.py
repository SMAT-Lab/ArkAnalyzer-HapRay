import time

from hypium import BY
from hypium.model.basic_data_type import MatchPattern

from hapray.core.perf_testcase import PerfTestCase


class MemLoad_Wechat_0040(PerfTestCase):
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
            # 2.进入朋友圈页面：点击发现（等待1s），点击朋友圈（等待2s）
            self.driver.touch((0.63, 0.92), wait_time=1)
            self.touch_by_text('朋友圈', 1)

        def step3():
            # 3.进入具体相册页面：点击相机按钮（等待1s），点击从相册选择（等待2s），点击图片和视频（等待1s），选择“图库测试图片”（等待2s）
            if self.driver.find_component(BY.text('拍摄')):
                self.touch_by_text('拍摄', 1)
            else:
                self.driver.touch((0.93, 0.07), wait_time=1)

            self.driver.touch((0.50, 0.85), wait_time=1)
            self.touch_by_text('图片和视频', 1)
            self.touch_by_text('图库测试图片', 2)

        def step4():
            # 4.选择照片进行预览：选择三张照片（等待2s），点击预览（等待2s），左右滑动2次（滑动间隔2s）
            sele = self.driver.find_all_components(BY.key('Selector', MatchPattern.STARTS_WITH))
            img = self.driver.find_all_components(BY.type('CachedImage'), 2)
            for i in range(3):
                self.driver.touch(sele[i], wait_time=2)
            self.driver.touch(img, wait_time=2)
            self.swipes_left(2, 2)
            self.swipes_right(2, 2)

        def step5():
            # 5.进入发表页面：点击完成（等待2s）
            self.driver.touch(BY.text('完成', MatchPattern.STARTS_WITH), wait_time=2)

        def step6():
            # 6.发表朋友圈：点击发表（等待2s）
            if self.driver.find_component(BY.text('发表')):
                self.driver.touch(BY.text('发表'), wait_time=2)
            else:
                self.driver.touch((0.86, 0.07), wait_time=2)

        def step7():
            # 7.浏览朋友圈：点击第一张图片（等待1s），左右滑动2次（滑动间隔2s）
            self.driver.touch((0.47, 0.60), wait_time=1)
            self.swipes_left(2, 2)
            self.swipes_right(2, 2)

        def step8():
            # 8.删除朋友圈：点击删除按钮（等待1s），点击删除（等待2s）
            if self.driver.find_component(BY.text('删除')):
                self.touch_by_text('删除', 1)
            else:
                self.driver.touch((0.93, 0.07), wait_time=1)
            self.driver.touch((0.70, 0.56), wait_time=2)

        def step9():
            # 9.进入具体相册页面：点击相机按钮（等待1s），点击从相册选择（等待2s），点击图片和视频（等待1s），选择“图库测试视频”（等待2s）
            if self.driver.find_component(BY.text('拍摄')):
                self.touch_by_text('拍摄', 1)
            else:
                self.driver.touch((0.93, 0.07), wait_time=1)
            self.driver.touch((0.50, 0.85), wait_time=2)
            self.driver.touch(BY.text('图片和视频'), wait_time=1)
            self.driver.touch(BY.text('图库测试视频'), wait_time=1)

        def step10():
            # 10.选择照片进行预览：选择第一个视频（等待2s）
            self.driver.touch(BY.key('Selector', MatchPattern.STARTS_WITH), wait_time=2)

        def step11():
            # 11.进入发表页面：点击完成（等待2s）
            self.driver.touch(BY.text('完成', MatchPattern.STARTS_WITH), wait_time=2)

        def step12():
            # 12.发表朋友圈：点击发表（等待2s）
            if self.driver.find_component(BY.text('发表')):
                self.touch_by_text('发表', 2)
            else:
                self.driver.touch((0.86, 0.07), wait_time=2)

        def step13():
            # 13.浏览朋友圈：点击朋友圈视频（等待5s），返回
            self.driver.touch((0.39, 0.62), wait_time=5)
            self.driver.swipe_to_back()

        def step14():
            # 14.删除朋友圈：点击删除按钮（等待1s），点击删除（等待2s）
            if self.driver.find_component(BY.text('删除')):
                self.touch_by_text('删除', 1)
            else:
                self.driver.touch((0.38, 0.75), wait_time=1)
            self.driver.touch((0.70, 0.56), wait_time=2)

        self.execute_performance_step('微信-朋友圈浏览场景-step1打开微信', 10, step1)
        self.execute_performance_step(
            '微信-朋友圈浏览场景-step2进入朋友圈页面：点击发现（等待1s），点击朋友圈（等待2s）', 10, step2
        )
        self.execute_performance_step(
            '微信-朋友圈浏览场景-step3进入具体相册页面：点击相机按钮（等待1s），点击从相册选择（等待2s），点击图片和视频（等待1s），选择“图库测试图片”（等待2s）',
            10,
            step3,
        )
        self.execute_performance_step(
            '微信-朋友圈浏览场景-step4选择照片进行预览：选择三张照片（等待2s），点击预览（等待2s），左右滑动2次（滑动间隔2s）',
            20,
            step4,
        )
        self.execute_performance_step('微信-朋友圈浏览场景-step5进入发表页面：点击完成（等待2s）', 10, step5)
        self.execute_performance_step('微信-朋友圈浏览场景-step6发表朋友圈：点击发表（等待2s）', 10, step6)
        self.execute_performance_step(
            '微信-朋友圈浏览场景-step7浏览朋友圈：点击第一张图片（等待1s），左右滑动2次（滑动间隔2s）', 15, step7
        )
        self.execute_performance_step(
            '微信-朋友圈浏览场景-step8删除朋友圈：点击删除按钮（等待1s），点击删除（等待2s）', 10, step8
        )
        self.execute_performance_step(
            '微信-朋友圈浏览场景-step9进入具体相册页面：点击相机按钮（等待1s），点击从相册选择（等待2s），点击图片和视频（等待1s），选择“图库测试视频”（等待2s））',
            15,
            step9,
        )
        self.execute_performance_step(
            '微信-朋友圈浏览场景-step10选择照片进行预览：选择第一个视频（等待2s）', 10, step10
        )
        self.execute_performance_step('微信-朋友圈浏览场景-step11进入发表页面：点击完成（等待2s）', 10, step11)
        self.execute_performance_step('微信-朋友圈浏览场景-step12发表朋友圈：点击发表（等待2s）', 10, step12)
        self.execute_performance_step(
            '微信-朋友圈浏览场景-step13浏览朋友圈：点击朋友圈视频（等待5s），返回', 10, step13
        )
        self.execute_performance_step(
            '微信-朋友圈浏览场景-step14删除朋友圈：点击删除按钮（等待1s），点击删除（等待2s）', 10, step14
        )
