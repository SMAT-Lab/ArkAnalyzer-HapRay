import time

from hypium import BY

from hapray.core.perf_testcase import PerfTestCase


class ResourceUsage_Memory_Wechat_0010(PerfTestCase):
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
        # 1.启动微信停留2秒
        self.start_app()

        def step1():
            time.sleep(2)

            # 2.群聊查看消息（主界面-->群聊窗口）
            self.driver.touch(BY.text('性能测试群'))
            self.driver.wait(0.5)
            time.sleep(2)

            # 3.查看聊天记录中的图片（横向滑动3次，2s,停留2s，重复5次）
            comps = self.driver.find_all_components(BY.type('Image'))
            self.driver.touch(comps[3])
            self.driver.wait(0.5)
            # 向右滑动
            for _ in range(1):
                self.swipes_right(swip_num=3, sleep=2)
            self.driver.touch(self.convert_coordinate(474, 1189))
            self.driver.wait(0.5)

            # 4.查看聊天记录中的视频（2s，播放10s，重复5次）
            # 打开视频
            self.driver.touch(BY.isAfter(BY.key('Video_Play_Btn')).type('Image'))
            self.driver.wait(0.5)
            time.sleep(10)
            # 暂停视频
            self.driver.touch(self.convert_coordinate(474, 1189))
            self.driver.wait(0.5)

            # 5.转发视频给其他好友（6s,停留2s）
            self.driver.touch(self.convert_coordinate(991, 2310))
            self.driver.wait(0.5)

            self.driver.touch(BY.isAfter(BY.key('scrollerForSheet')).isBefore(BY.text('转发给朋友')).type('Image'))
            self.driver.wait(0.5)

            self.driver.touch(BY.text('测试账号'))
            self.driver.wait(0.5)

            self.driver.touch(BY.text('发送'))
            self.driver.wait(0.5)

            self.driver.touch(BY.key('center'))
            self.driver.wait(0.5)

            self.driver.touch(self.convert_coordinate(96, 157))
            self.driver.wait(0.5)

            # 6.返回微信主界面（2s，停留2s）
            self.driver.touch(BY.isAfter(BY.key('left')).isBefore(BY.key('center')).type('Image'))
            self.driver.wait(0.5)

            # 7.查看好友留言（2s，停留2s）
            self.driver.touch(BY.text('测试账号'))
            self.driver.wait(0.5)
            # 8.播放语音留言（2s，停留2s）
            # 9.返回首页
            self.driver.touch(BY.isAfter(BY.key('left')).isBefore(BY.key('center')).type('Image'))
            self.driver.wait(0.5)
            # 10.点击测试账号
            self.driver.touch(BY.text('测试账号'))
            self.driver.wait(0.5)
            # 11.打开输入法（停留2s）
            # 12.发送文字消息“哈哈哈”给好友（2s，停留2s）
            send_input = self.convert_coordinate(490, 2250)
            self.driver.input_text(send_input, '哈哈哈')
            self.driver.touch(BY.text('发送'))
            self.driver.wait(0.5)
            # 13.发送语音（语音时长3s，停留2s）
            self.driver.touch(self.convert_coordinate(79, 1395))
            self.driver.wait(0.5)
            self.driver.touch(BY.text('按住 说话'), 'long')
            self.driver.wait(0.5)
            time.sleep(2)
            # 14.点击表情包，等待2秒
            self.driver.touch(self.convert_coordinate(892, 2263))
            self.driver.wait(0.5)
            time.sleep(2)
            # 15.选择前三个表情发送，等待2s
            self.driver.touch(self.convert_coordinate(98, 1732))
            self.driver.touch(self.convert_coordinate(247, 1732))
            self.driver.touch(self.convert_coordinate(400, 1732))
            # 发送
            self.driver.touch(self.convert_coordinate(1000, 1247))
            self.driver.wait(0.5)
            time.sleep(2)

            # 16.点击加号，等待2s
            self.driver.touch(self.convert_coordinate(1026, 1247))
            self.driver.wait(0.5)
            time.sleep(2)
            # 17.点击视频通话，等待2s
            self.driver.touch(BY.isAfter(BY.text('拍摄')).isBefore(BY.text('视频通话')).type('Image'))
            self.driver.wait(0.5)
            time.sleep(2)
            # 18.点击视频通话，等待2s
            self.driver.touch(BY.isAfter(BY.key('scroll')).isBefore(BY.text('语音通话')).type('Text').text('视频通话'))
            self.driver.wait(0.5)
            time.sleep(2)
            # 19.点击挂断，等待2s
            self.driver.touch(self.convert_coordinate(526, 2026))
            self.driver.wait(0.5)
            time.sleep(2)
            # 20.点击加号，等待2s
            self.driver.touch(self.convert_coordinate(1008, 2254))
            self.driver.wait(0.5)
            time.sleep(2)
            # 21.点击视频通话，等待2s
            self.driver.touch(BY.isAfter(BY.text('拍摄')).isBefore(BY.text('视频通话')).type('Image'))
            self.driver.wait(0.5)
            time.sleep(2)
            # 22.点击语音通话，等待2s
            self.driver.touch(BY.text('语音通话'))
            self.driver.wait(0.5)
            time.sleep(2)
            # 23.点击取消，等待2s
            self.driver.touch(BY.text('取消'))
            self.driver.wait(0.5)
            time.sleep(2)

            # 24.点击加号，等待2s
            self.driver.touch(self.convert_coordinate(1008, 2254))
            self.driver.wait(0.5)
            time.sleep(2)
            # 25.点击“红包”，返回聊天页面
            # self.driver.touch(BY.isAfter(BY.text('位置')).isBefore(BY.text('红包')).type('Image'))
            # self.driver.wait(0.5)
            #
            # self.driver.touch(BY.text('取消'))
            # self.driver.wait(0.5)
            # 26.点击加号，等待2s
            # 27.点击转账
            # 通过相对位置点击控件
            self.driver.touch(BY.isAfter(BY.text('红包')).isBefore(BY.text('转账')).type('Image'))
            self.driver.wait(0.5)
            # 28.点击添加转账说明
            self.driver.touch(BY.text('添加转账说明'))
            self.driver.wait(0.5)
            # 29.输入“修改”
            money_input = BY.isAfter(BY.text('转账说明')).isBefore(BY.text('取消')).type('TextInput')
            self.driver.input_text(money_input, '修改')
            self.driver.wait(2)
            self.driver.touch(self.convert_coordinate(114, 735))
            self.driver.wait(0.5)
            # 30.点击确定
            self.driver.touch(BY.text('确定'))
            self.driver.wait(0.5)
            time.sleep(2)
            # 31.返回测试账号聊天页面
            # 根据条件点击控件
            self.driver.touch(self.convert_coordinate(67, 194))
            self.driver.wait(0.5)
            # 32.聊天页面下滑3次
            self.swipes_down(swip_num=3, sleep=2)
            # 33.侧滑1次至微信首页，等待2s
            self.driver.swipe_to_back()
            time.sleep(2)
            # 34.返回home界面（2s，停留2s）
            self.driver.swipe_to_home()
            time.sleep(10)
            # 36.删除后台（等待10s）
            # self.driver.stop_app(self._app_package, 10)
            # time.sleep(10)

        self.execute_performance_step('0001&微信首页-点击-页面切换-群聊界面', 120, step1)
        # self.execute_performance_step('0002&群聊界面-点击-应用内操作-群聊界面', 12, step2)
        # self.execute_performance_step('0003&微信首页-点击-群聊界面-应用内操作-群聊界面', 16, step3)
        # self.execute_performance_step('0004&微信首页-点击-应用内操作-群聊界面', 40, step4)
        # self.execute_performance_step('0005&群聊界面-滑动-返回上一层-微信首页', 4, step5)
        # self.execute_performance_step('0006&微信首页-点击-页面切换-群聊界面', 2, step6)
        # self.execute_performance_step('0007&群聊界面-点击-应用内操作-群聊界面', 60, step7)
        # self.execute_performance_step('0008&群聊界面-滑动-返回上一级-微信首页', 120, step1)
        # self.execute_performance_step('0009&微信首页-点击-页面切换-好友聊天页面', 120, step1)
        # self.execute_performance_step('00010&好友聊天页面-点击-应用内操作-好友聊天页面拉起输入法', 120, step1)
        # self.execute_performance_step('00011&好友聊天页面拉起输入法-点击-输入法输入-好友聊天页面', 120, step1)
        # self.execute_performance_step('00012&好友聊天页面-点击-应用内操作-好友聊天页面', 120, step1)
        # self.execute_performance_step('00013&好友聊天页面-点击-应用内操作-好友聊天页面拉起表情框', 120, step1)
        # self.execute_performance_step('00014&好友聊天页面拉起表情框-点击-应用内操作-好友聊天页面拉起表情框', 120, step1)
        # self.execute_performance_step('00015&好友聊天页面拉起表情框-点击-应用内操作-好友聊天页面拉起更多操作框', 120, step1)
        # self.execute_performance_step('00016&好友聊天页面拉起更多操作框-点击-应用内操作-选择视频语音通话的弹框页面', 120, step1)
        # self.execute_performance_step('00017&选择视频语音通话的弹框页面-点击-页面切换-发起视频通话待接听页面', 120, step1)
        # self.execute_performance_step('00018&发起视频通话待接听页面-点击-页面切换-好友聊天页面', 120, step1)
        # self.execute_performance_step('00019&好友聊天页面-点击-应用内操作-好友聊天页面拉起更多操作框', 120, step1)
        # self.execute_performance_step('00020&好友聊天页面拉起更多操作框-点击-应用内操作-选择视频语音通话的弹框页面', 120, step1)
        # self.execute_performance_step('00021&选择视频语音通话的弹框页面-点击-页面切换-发起语音通话待接听页面', 120, step1)
        # self.execute_performance_step('00022&发起语音通话待接听页面-点击-页面切换-好友聊天页面', 120, step1)
        # self.execute_performance_step('00023&测试账号页面-点击-应用内操作-测试账号页面拉起更多工具框页面', 120, step1)
        # self.execute_performance_step('00024&测试账号页面拉起更多工具框页面-点击-页面切换-发红包页面-点击红包', 120, step1)
        # self.execute_performance_step('00025&测试账号页面拉起表情框-点击-应用内操作-测试账号页面拉起更多工具框页面-点击加号', 120, step1)
        # self.execute_performance_step('00026&测试账号页面拉起更多工具框页面-点击-页面切换-转账页面-点击转账', 120, step1)
        # self.execute_performance_step('00027&转账页面-点击-页面切换-转账说明页面-点击转账说明', 120, step1)
        # self.execute_performance_step('00028&转账说明页面-点击-输入法输入-测试账号页面-点击输入修改', 120, step1)
        # self.execute_performance_step('00029&转账说明页面-点击-页面切换-转账页面-点击确定', 120, step1)
        # self.execute_performance_step('00030&测试账号页面-滑动-返回上一级-微信首页-侧滑1次至微信首页', 120, step1)
        # self.execute_performance_step('00031&聊天页面-滑动-应用内操作-聊天页面-向下滑动查看聊天记录', 120, step1)
        # self.execute_performance_step('00032&好友聊天页面-滑动-返回上一级-微信首页', 120, step1)
        # self.execute_performance_step('00033&微信首页-滑动-退出应用-桌面', 120, step1)
