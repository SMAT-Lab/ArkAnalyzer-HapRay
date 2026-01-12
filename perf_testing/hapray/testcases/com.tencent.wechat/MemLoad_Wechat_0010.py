import time

from hypium import BY
from hypium.model.basic_data_type import MatchPattern

from hapray.core.perf_testcase import PerfTestCase


class MemLoad_Wechat_0010(PerfTestCase):
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
            # 2.进入聊天窗口： 点击微信（等待1s），点击“群聊1”（等待2s）
            self.touch_by_text('微信', 1)
            self.touch_by_text('群聊1', 1)

        def step3():
            # 3.发送文字：点击聊天框（等待1s），输入“你好”（等待1s），点击发送（等待1s）
            self.driver.touch(BY.type('RichEditorContent'), wait_time=1)
            self.driver.input_text(BY.type('RichEditorContent'), '你好')
            time.sleep(1)
            self.touch_by_text('发送', 1)

        def step4():
            # 4.进入图库页面：点击+（等待1s），点击照片（等待2s）
            self.driver.touch((0.93, 0.58), wait_time=1)
            self.touch_by_text('照片', 2)

        def step5():
            # 5.进入具体相册页面：点击图片和视频（等待1s），点击“图库测试图片”相册（等待1s）
            self.touch_by_text('图片和视频', 1)
            self.touch_by_text('图库测试图片', 1)

        def step6():
            # 6.选择图片：选择三张图片（等待1s）
            sele = self.driver.find_all_components(BY.key('Selector', MatchPattern.STARTS_WITH))
            for i in range(3):
                self.driver.touch(sele[i], wait_time=1)

        def step7():
            # 7.发送消息：点击发送（等待5s）
            self.driver.touch(BY.text('发送', MatchPattern.STARTS_WITH), wait_time=5)

        def step8():
            # 8.进入图库页面：点击+（等待1s），点击照片（等待2s）
            self.driver.touch((0.94, 0.93), wait_time=1)
            self.driver.touch(BY.text('照片'), wait_time=2)

        def step9():
            # 9.进入具体相册页面：点击图片和视频（等待1s），点击“图库测试视频”相册（等待1s）
            self.driver.touch(BY.text('图片和视频'), wait_time=1)
            self.driver.touch(BY.text('图库测试视频'), wait_time=1)

        def step10():
            # 10.选择视频：选择第一个视频（等待1s）
            self.driver.touch(BY.key('Selector', MatchPattern.STARTS_WITH), wait_time=1)

        def step11():
            # 11.发送消息：点击发送（等待10s）
            self.driver.touch(BY.text('发送', MatchPattern.STARTS_WITH), wait_time=10)

        def step12():
            # 12.消息视频查看：点击一个视频（等待10s）
            self.driver.touch(BY.key('Video_Play_Btn'), wait_time=10)

        def step13():
            # 13.图片记录浏览：向左滑动3次（滑动间隔2s）
            self.swipes_right(3, 2)

        def step14():
            # 14.整体消息浏览：返回（等待1s），向下滑动1次，向上滑动1次（滑动间隔2s）
            self.driver.swipe_to_back()
            time.sleep(1)
            self.swipes_up(1, 2)
            self.swipes_down(1, 2)

        def step15():
            # 15.删除消息：点击右上设置（等待1s），向下滑一次（等待1s），点击删除聊天记录（等待1s），点击删除聊天记录（等待4s）
            self.driver.touch(BY.key('right'), wait_time=1)
            self.swipes_up(1, 1)
            self.driver.touch(BY.text('删除聊天记录'), wait_time=1)
            self.driver.touch(self.driver.find_all_components(BY.text('删除聊天记录'), 1), wait_time=4)

        self.execute_performance_step('微信-群聊图片消息发送和浏览场景-step1打开微信', 10, step1)
        self.execute_performance_step(
            '微信-群聊图片消息发送和浏览场景-step2进入聊天窗口： 点击微信（等待1s），点击“群聊1”（等待2s）', 10, step2
        )
        self.execute_performance_step(
            '微信-群聊图片消息发送和浏览场景-step3发送文字：点击聊天框（等待1s），输入“你好”（等待1s），点击发送（等待1s）',
            10,
            step3,
        )
        self.execute_performance_step(
            '微信-群聊图片消息发送和浏览场景-step4进入图库页面：点击+（等待1s），点击照片（等待2s）', 10, step4
        )
        self.execute_performance_step(
            '微信-群聊图片消息发送和浏览场景-step5进入具体相册页面：点击图片和视频（等待1s），点击“图库测试图片”相册（等待1s）',
            10,
            step5,
        )
        self.execute_performance_step(
            '微信-群聊图片消息发送和浏览场景-step6选择图片：选择三张图片（等待1s）', 15, step6
        )
        self.execute_performance_step('微信-群聊图片消息发送和浏览场景-step7发送消息：点击发送（等待5s）', 10, step7)
        self.execute_performance_step(
            '微信-群聊图片消息发送和浏览场景-step8进入图库页面：点击+（等待1s），点击照片（等待2s）', 10, step8
        )
        self.execute_performance_step(
            '微信-群聊图片消息发送和浏览场景-step9进入具体相册页面：点击图片和视频（等待1s），点击“图库测试视频”相册（等待1s）',
            10,
            step9,
        )
        self.execute_performance_step(
            '微信-群聊图片消息发送和浏览场景-step10选择视频：选择第一个视频（等待1s）', 10, step10
        )
        self.execute_performance_step('微信-群聊图片消息发送和浏览场景-step11发送消息：点击发送（等待10s）', 15, step11)
        self.execute_performance_step(
            '微信-群聊图片消息发送和浏览场景-step12消息视频查看：点击一个视频（等待10s）', 15, step12
        )
        self.execute_performance_step(
            '微信-群聊图片消息发送和浏览场景-step13图片记录浏览：向左滑动3次（滑动间隔2s）', 10, step13
        )
        self.execute_performance_step(
            '微信-群聊图片消息发送和浏览场景-step14整体消息浏览：返回（等待1s），向下滑动1次，向上滑动1次（滑动间隔2s）',
            10,
            step14,
        )
        self.execute_performance_step(
            '微信-群聊图片消息发送和浏览场景-step15删除消息：点击右上设置（等待1s），向下滑一次（等待1s），点击删除聊天记录（等待1s），点击删除聊天记录（等待4s）',
            15,
            step15,
        )
