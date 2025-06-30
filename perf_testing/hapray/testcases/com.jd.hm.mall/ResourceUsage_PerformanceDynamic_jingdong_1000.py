# coding: utf-8
import os
import time

from hapray.core.perf_testcase import PerfTestCase, Log


class ResourceUsage_PerformanceDynamic_jingdong_1000(PerfTestCase):

    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(self.TAG, controllers)

        self._app_package = 'com.jd.hm.mall'
        self._app_name = '京东'
        self._steps = [
            {
                "name": "step1",
                "description": "1. 应用冷启动，手机重启后及时输入开机密码和设置连接电脑传输文件。再检查重启后手机是否自动关闭了usb调试，如关闭，请手动打开"
            }
        ]
        # 原始采集设备的屏幕尺寸（Mate 60 Pro）
        self.source_screen_width = 1260
        self.source_screen_height = 2720

    @property
    def steps(self) -> list:
        return self._steps

    @property
    def app_package(self) -> str:
        return self._app_package

    @property
    def app_name(self) -> str:
        return self._app_name

    def setup(self):
        Log.info('setup')
        os.makedirs(os.path.join(self.report_path, 'hiperf'), exist_ok=True)
        os.makedirs(os.path.join(self.report_path, 'htrace'), exist_ok=True)

        # 设置hdc参数
        Log.info('设置hdc参数: persist.ark.properties 0x200105c')
        os.system('hdc shell param set persist.ark.properties 0x200105c')

        # 重启手机
        Log.info('重启手机')
        os.system('hdc shell reboot')

        # 检测手机是否重启成功
        Log.info('检测手机重启状态')
        max_wait_time = 180  # 最大等待时间180秒
        wait_interval = 10  # 每10秒检查一次
        elapsed_time = 0

        while elapsed_time < max_wait_time:
            try:
                # 使用hdc shell命令检测设备是否真正连接
                result = os.system('hdc shell "echo device_ready"')
                if result == 0:
                    Log.info('手机重启成功，设备已连接')
                    Log.info('等待手机完全启动到大屏幕界面...')
                    time.sleep(60)  # 额外等待60秒确保系统完全启动到大屏幕
                    return
                else:
                    Log.info(f'设备未连接，返回码: {result}')
            except Exception as e:
                Log.info(f'设备检测失败: {e}')

            Log.info(f'等待设备重启中... ({elapsed_time}/{max_wait_time}秒)')
            time.sleep(wait_interval)
            elapsed_time += wait_interval
            Log.info(f'时间已更新: {elapsed_time}秒')

        # 如果超时仍未检测到设备
        raise Exception('手机重启超时，设备未连接')

    def process(self):
        self.driver.swipe_to_home()
        self.driver.start_app(self.app_package)

        def step1(driver):
            time.sleep(3)

        self.execute_performance_step(1, step1, 5)

        Log.info('开始获取redundant file')
        bundle_name = self.app_package
        source_path = f'data/app/el2/100/base/{bundle_name}/files/{bundle_name}_redundant_file.txt'
        target_path = os.path.join(self.report_path, 'result', f'{bundle_name}_redundant_file.txt')

        # 确保目标目录存在
        os.makedirs(os.path.dirname(target_path), exist_ok=True)

        # 先检查文件是否存在
        Log.info(f'检查设备端文件是否存在: {source_path}')
        check_cmd = f'hdc shell ls {source_path}'
        check_result = os.system(check_cmd)

        if check_result != 0:
            Log.warning(f'文件不存在: {source_path}')
            return

        Log.info('文件存在，开始获取')
        Log.info(f'设备端文件路径: {source_path}')
        Log.info(f'本地保存路径: {target_path}')

        try:
            # 使用hdc file recv命令获取文件
            cmd = f'hdc file recv {source_path} {target_path}'
            Log.info(f'执行命令: {cmd}')
            result = os.system(cmd)

            if result == 0:
                Log.info('redundant file获取成功')
                Log.info(f'设备端路径: {source_path}')
                Log.info(f'本地保存路径: {target_path}')
            else:
                Log.warning(f'redundant file获取失败，返回码: {result}')

        except Exception as e:
            Log.error(f'获取redundant file时发生异常: {e}')

    def teardown(self):
        Log.info('teardown')
        self.driver.stop_app(self.app_package)
        self.generate_reports()
