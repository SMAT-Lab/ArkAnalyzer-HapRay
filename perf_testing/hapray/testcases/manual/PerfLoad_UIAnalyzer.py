import os
import re
import time

from xdevice import platform_logger

from hapray.core.config.config import Config
from hapray.core.perf_testcase import PerfTestCase

Log = platform_logger('PerfLoad_UIAnalyzer')


class PerfLoad_UIAnalyzer(PerfTestCase):
    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(self.TAG, controllers)
        self._app_package = self._get_current_app_package()
        self._app_name = 'Unknown'

    def setup(self):
        """common setup

        注意：不再创建 memory 目录，memory 数据从 trace.htrace 中获取
        """
        Log.info('PerfTestCase setup')
        os.makedirs(os.path.join(self.report_path, 'hiperf'), exist_ok=True)
        os.makedirs(os.path.join(self.report_path, 'htrace'), exist_ok=True)

    def teardown(self):
        """common teardown"""
        Log.info('PerfTestCase teardown')
        self._generate_reports()

    def _get_current_app_package(self) -> str:
        """
        从hdc命令获取当前应用包名
        使用 aa dump -l 命令获取前台应用的 bundle name

        Returns:
            当前前台应用的包名，如果获取失败则返回配置中的包名
        """
        try:
            # 使用 aa dump -l 命令获取当前任务列表
            result = self.driver.shell('aa dump -l')

            # 查找 state #FOREGROUND 的应用并提取 bundle name
            # 输出格式示例：
            #   AbilityRecord ID #3818
            #     app name [com.ss.hm.ugc.aweme]
            #     main name [MainAbility]
            #     bundle name [com.ss.hm.ugc.aweme]
            #     ability type [PAGE]
            #     state #FOREGROUND
            #     app state #FOREGROUND
            lines = result.split('\n')
            current_bundle_name = None

            # 查找 app state #FOREGROUND
            for i in range(len(lines) - 1, -1, -1):
                line = lines[i]
                if 'app state #FOREGROUND' in line:
                    # 向前查找 bundle name（在同一个 AbilityRecord 块中，通常在 state 之前）
                    for j in range(i, max(0, i - 15), -1):
                        bundle_match = re.search(r'bundle name \[([a-zA-Z0-9_.]+)\]', lines[j])
                        if bundle_match:
                            current_bundle_name = bundle_match.group(1)
                            break
                    if current_bundle_name:
                        break

            if current_bundle_name:
                Log.info(f'从hdc命令获取到当前应用包名: {current_bundle_name}')
                return current_bundle_name

            Log.warning('未找到 FOREGROUND 状态的应用')

        except Exception as e:
            # 如果获取失败，回退到使用配置中的包名
            Log.warning(f'无法从hdc命令获取当前应用包名: {e}，使用配置中的包名')

        # 回退到配置中的包名
        return Config.get('package_name', '')

    @property
    def app_package(self) -> str:
        return self._app_package

    @property
    def app_name(self) -> str:
        return self._app_name

    def process(self):
        def step1():
            self.swipes_up(1, 2)
            time.sleep(3)

        self.execute_performance_step('UI测试', 5, step1)
