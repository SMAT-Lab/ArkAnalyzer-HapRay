import json
import os
import subprocess
import threading
import time
from abc import abstractmethod

from devicetest.core.test_case import TestCase
from devicetest.log.logger import DeviceTestLog as Log
from hypium.advance.perf.driver_perf.uiexplorer_perf import UiExplorerPerf

from aw.config.config import Config


class PerfTestCase(TestCase):
    def __init__(self, tag: str, configs):
        super().__init__(tag, configs)
        self.driver = UiExplorerPerf(self.device1)
        self.TAG = tag
        self.pid = -1

    @property
    @abstractmethod
    def steps(self) -> []:
        pass

    @property
    @abstractmethod
    def app_package(self) -> str:
        pass

    @property
    @abstractmethod
    def app_name(self) -> str:
        pass

    @property
    def report_path(self) -> str:
        return self.get_case_report_path()

    @staticmethod
    def _get_hiperf_cmd(pid, output_path, duration):
        """生成 hiperf 命令

        Args:
            pid: 进程ID
            output_path: 输出文件路径
            duration: 采集持续时间

        Returns:
            str: 完整的 hiperf 命令
        """
        cmd = f"hiperf record -p {pid} -o {output_path} -s dwarf --kernel-callchain -f 1000 -e raw-instruction-retired --clockid monotonic -m 1024 -d {duration}"
        Log.debug(f"\n[DEBUG] Hiperf Command: {cmd}\n")  # 添加调试输出
        return cmd

    @staticmethod
    def _run_hiperf(driver, cmd):
        """在后台线程中运行 hiperf 命令"""
        driver.shell(cmd)

    @staticmethod
    def _generate_hapray_report(scene_dir: str) -> bool:
        """
        执行 hapray 命令生成性能分析报告
        :param scene_dir: 场景目录路径，例如 perf_output/wechat002 或完整路径
        :return: bool 表示是否成功生成报告
        """
        # 获取 perf_testing 目录
        perf_testing_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        # 获取项目根目录（perf_testing 的上一级目录）
        project_root = os.path.dirname(perf_testing_dir)

        # 检查是否已经是完整路径
        if os.path.isabs(scene_dir):
            # 如果是绝对路径，直接使用
            full_scene_dir = scene_dir
        else:
            # 否则，添加 perf_testing 目录前缀
            full_scene_dir = os.path.normpath(os.path.join(perf_testing_dir, scene_dir))

        # 检查目录是否存在
        if not os.path.exists(full_scene_dir):
            Log.error(f"Error: Scene directory does not exist: {full_scene_dir}")
            return False

        # 检查 hiperf 目录是否存在
        hiperf_dir = os.path.join(full_scene_dir, 'hiperf')
        if not os.path.exists(hiperf_dir):
            Log.error(f"Error: hiperf directory does not exist: {hiperf_dir}")
            return False

        # 检查 hiperf 目录中是否有文件
        hiperf_files = os.listdir(hiperf_dir)
        if not hiperf_files:
            Log.error(f"Error: hiperf directory is empty: {hiperf_dir}")
            return False

        Log.info(f"Found {len(hiperf_files)} files in hiperf directory")

        # 构建输出路径 - 直接输出到场景目录的 report 文件夹
        output_dir = os.path.join(full_scene_dir, 'report')

        # 确保输出目录存在
        os.makedirs(output_dir, exist_ok=True)

        # 获取 hapray-cmd.js 的绝对路径
        hapray_cmd_path = os.path.abspath(os.path.join(project_root, 'toolbox', 'dist', 'hapray-cmd.js'))

        # 检查 hapray-cmd.js 是否存在
        if not os.path.exists(hapray_cmd_path):
            Log.error(f"Error: hapray-cmd.js not found at {hapray_cmd_path}")
            return False

        # 打印调试信息
        Log.info(f"Project root: {project_root}")
        Log.info(f"Scene directory: {full_scene_dir}")
        Log.info(f"Hiperf directory: {hiperf_dir}")
        Log.info(f"Hapray command path: {hapray_cmd_path}")
        Log.info(f"Current working directory: {os.getcwd()}")

        # 确保路径使用双反斜杠
        full_scene_dir_escaped = full_scene_dir.replace('\\', '\\\\')
        hapray_cmd_path_escaped = hapray_cmd_path.replace('\\', '\\\\')

        # 构建并执行命令 - 使用绝对路径
        cmd = [
            'node', hapray_cmd_path_escaped,
            'hapray', 'dbtools',
            '-i', full_scene_dir_escaped
        ]

        # 打印完整命令
        Log.info(f"Executing command: {' '.join(cmd)}")

        try:
            # 设置工作目录为项目根目录
            result = subprocess.run(cmd, check=True, cwd=project_root, capture_output=True, text=True)
            Log.info(f"Command output: {result.stdout}")
            if result.stderr:
                Log.error(f"Command stderr: {result.stderr}")

            # 检查输出目录中是否有文件
            report_files = os.listdir(output_dir)
            if not report_files:
                Log.warn(f"Warning: No files found in report directory: {output_dir}")
                return False

            Log.info(f"Found {len(report_files)} files in report directory")
            Log.info(f"Successfully generated HapRay report in: {output_dir}")
            return True
        except subprocess.CalledProcessError as e:
            Log.error(f"Failed to generate HapRay report: {str(e)}")
            if e.stdout:
                Log.error(f"Command stdout: {e.stdout}")
            if e.stderr:
                Log.error(f"Command stderr: {e.stderr}")
            return False
        except FileNotFoundError:
            Log.error("Error: Node.js command not found. Please make sure Node.js is installed and in your PATH.")
            return False

    def make_reports(self):
        # 读取配置文件中的步骤信息
        steps_info = []
        for i, step in enumerate(self.steps, 1):
            steps_info.append({
                "name": step['name'],
                "description": step['description'],
                "stepIdx": i
            })

        # 保存步骤信息到steps.json
        steps_json_path = os.path.join(self.report_path, 'hiperf/steps.json')

        with open(steps_json_path, 'w', encoding='utf-8') as f:
            json.dump(steps_info, f, ensure_ascii=False, indent=4)

        # 保存测试信息
        self._save_test_info()

        # 生成 HapRay 报告
        PerfTestCase._generate_hapray_report(self.report_path)

    def execute_step_with_perf(self, step_id, action_func, duration=5):
        """
        执行一个步骤并收集性能数据

        Args:
            step_id: 步骤ID
            action_func: 要执行的动作函数
            duration: 性能数据采集持续时间（秒）
        """
        # 设置当前步骤的输出路径
        output_file = f"/data/local/tmp/hiperf_step{step_id}.data"

        # 确保设备上的目标目录存在
        output_dir = os.path.dirname(output_file)
        self.driver.shell(f"mkdir -p {output_dir}")

        # 清理可能存在的旧文件
        self.driver.shell(f"rm -f {output_file}")

        if self.pid == -1:
            self.pid = self._get_app_pid()

        # 创建并启动 hiperf 线程
        hiperf_cmd = PerfTestCase._get_hiperf_cmd(self.pid, output_file, duration)
        hiperf_thread = threading.Thread(target=PerfTestCase._run_hiperf, args=(self.driver, hiperf_cmd))
        hiperf_thread.start()

        # 执行动作
        action_func(self.driver)

        # 等待 hiperf 线程完成
        hiperf_thread.join()

        # 保存性能数据
        self._save_perf_data(output_file, step_id)

    def _save_perf_data(self, device_file, step_id):
        """保存性能数据"""

        # 构建完整的目录结构
        hiperf_dir = os.path.join(self.report_path, 'hiperf')
        step_dir = os.path.join(hiperf_dir, f'step{str(step_id)}')

        # 构建文件路径
        local_output_path = os.path.join(step_dir, Config.get('hiperf.data_filename', 'perf.data'))
        local_output_db_path = os.path.join(step_dir, Config.get('hiperf.db_filename', 'perf.db'))

        # 确保所有必要的目录都存在
        os.makedirs(step_dir, exist_ok=True)

        # 检查设备上的文件是否存在
        try:
            # 使用 ls 命令检查文件是否存在
            result = self.driver.shell(f"ls -l {device_file}")

            if "No such file" in result:
                # 尝试列出目录内容以进行调试
                dir_path = os.path.dirname(device_file)
                self.driver.shell(f"ls -l {dir_path}")
                return

            # 如果文件存在，尝试拉取
            self.driver.pull_file(device_file, local_output_path)

            # 检查本地文件是否成功拉取
            if not os.path.exists(local_output_path):
                return

            # 检查转换后的文件是否存在
            if not os.path.exists(local_output_db_path):
                return

        except Exception as e:
            # 尝试获取更多调试信息
            self.driver.shell("df -h")
            self.driver.shell("ls -l /data/local/tmp/")

    def _save_test_info(self):
        """
        生成并保存测试信息到testInfo.json
        :return: 保存的结果字典
        """
        # 确保输出目录存在
        os.makedirs(self.report_path, exist_ok=True)

        # 从配置中获取应用名称，如果没有配置则自动获取
        app_version = self._get_app_version()

        # 准备结果信息
        result = {
            "app_id": self.app_package,
            "app_name": self.app_name,
            "app_version": app_version,
            "scene": self.TAG,
            "timestamp": int(time.time() * 1000)  # 毫秒级时间戳
        }

        # 保存到文件
        result_path = os.path.join(self.report_path, 'testInfo.json')
        with open(result_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=4, ensure_ascii=False)

        return result

    def _get_app_version(self) -> str:
        """
        获取应用版本号
        :return: str: 应用版本号
        """
        # 使用 bm dump 命令获取版本号
        cmd = f"bm dump -n {self.app_package}"
        result = self.driver.shell(cmd)
        Log.debug(f"Debug - bm dump result: {result}")  # 添加调试输出

        try:
            # 解析 JSON 结果
            # 移除开头的包名和冒号
            json_str = result.split(':', 1)[1].strip()
            data = json.loads(json_str)

            if 'applicationInfo' in data and 'versionName' in data['applicationInfo']:
                version = data['applicationInfo']['versionName']
                if version:
                    Log.debug(f"Debug - Found version: {version}")  # 添加调试输出
                    return version
        except json.JSONDecodeError as e:
            Log.debug(f"Debug - JSON parsing error: {e}")  # 添加调试输出

        Log.debug(f"Debug - No version found for {self.app_package}")  # 添加调试输出
        return "Unknown Version"  # 如果无法获取版本号，返回未知版本

    def _get_app_pid(self) -> int:
        pid_cmd = f"pidof {self.app_package}"
        return self.driver.shell(pid_cmd).strip()