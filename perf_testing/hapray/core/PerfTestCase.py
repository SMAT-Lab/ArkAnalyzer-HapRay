import json
import os
import subprocess
import threading
import time
from abc import abstractmethod

from devicetest.core.test_case import TestCase
from xdevice import platform_logger
from hypium import UiDriver

from hapray.core.common.CommonUtils import CommonUtils
from hapray.core.config.config import Config

Log = platform_logger("PerfTestCase")


class PerfTestCase(TestCase):
    def __init__(self, tag: str, configs):
        super().__init__(tag, configs)
        self.driver = UiDriver(self.device1)
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
    def _get_hiperf_cmd(pid, output_path, duration, sample_all=False):
        """生成 hiperf 命令

        Args:
            pid: 进程ID
            output_path: 输出文件路径
            duration: 采集持续时间

        Returns:
            str: 完整的 hiperf 命令
        """
        cmd = f"hiperf record -p {pid} -o {output_path} -s dwarf --kernel-callchain -f 1000 -e raw-instruction-retired --clockid monotonic -m 1024 -d {duration}"
        if sample_all:
            cmd = f"hiperf record -a -o {output_path} -s dwarf --kernel-callchain -f 1000 -e raw-instruction-retired --clockid monotonic -m 1024 -d {duration}"
        # Log.debug(f"\n[DEBUG] Hiperf Command: {cmd}\n")  # 添加调试输出
        return cmd

    @staticmethod
    def _get_trace_and_perf_cmd(pid, output_path, duration, sample_all=False):
        """生成同时抓取trace和perf数据的命令

        Args:
            pid: 进程ID
            output_path: 输出文件路径
            duration: 采集持续时间

        Returns:
            str: 完整的命令
        """
        recort_args = f"-p {pid} -s dwarf --kernel-callchain -f 1000 -e raw-instruction-retired --clockid monotonic -m 1024 -d {duration}"
        if sample_all:
            recort_args = f"-a -s dwarf --kernel-callchain -f 1000 -e raw-instruction-retired --clockid monotonic -m 1024 -d {duration}"
        # 基础命令部分
        cmd = f"""hiprofiler_cmd \\
  -c - \\
  -o {output_path}.htrace \\
  -t {duration} \\
  -s \\
  -k \\
<<CONFIG
# 会话配置
 request_id: 1
 session_config {{
  buffers {{
   pages: 16384
  }}
 }}

# ftrace插件配置
 plugin_configs {{
  plugin_name: "ftrace-plugin"
  sample_interval: 1000
  config_data {{
   # ftrace事件配置
   ftrace_events: "sched/sched_switch"
   ftrace_events: "power/suspend_resume"
   ftrace_events: "sched/sched_wakeup"
   ftrace_events: "sched/sched_wakeup_new"
   ftrace_events: "sched/sched_waking"
   ftrace_events: "sched/sched_process_exit"
   ftrace_events: "sched/sched_process_free"
   ftrace_events: "task/task_newtask"
   ftrace_events: "task/task_rename"
   ftrace_events: "power/cpu_frequency"
   ftrace_events: "power/cpu_idle"

   # hitrace类别配置
   hitrace_categories: "ability"
   hitrace_categories: "ace"
   hitrace_categories: "app"
   hitrace_categories: "ark"
   hitrace_categories: "binder"
   hitrace_categories: "disk"
   hitrace_categories: "freq"
   hitrace_categories: "graphic"
   hitrace_categories: "idle"
   hitrace_categories: "irq"
   hitrace_categories: "memreclaim"
   hitrace_categories: "mmc"
   hitrace_categories: "multimodalinput"
   hitrace_categories: "notification"
   hitrace_categories: "ohos"
   hitrace_categories: "pagecache"
   hitrace_categories: "rpc"
   hitrace_categories: "sched"
   hitrace_categories: "sync"
   hitrace_categories: "window"
   hitrace_categories: "workq"
   hitrace_categories: "zaudio"
   hitrace_categories: "zcamera"
   hitrace_categories: "zimage"
   hitrace_categories: "zmedia"

   # 缓冲区配置
   buffer_size_kb: 204800
   flush_interval_ms: 1000
   flush_threshold_kb: 4096
   parse_ksyms: true
   clock: "boot"
   trace_period_ms: 200
   debug_on: false
  }}
 }}

# hiperf插件配置
 plugin_configs {{
  plugin_name: "hiperf-plugin"
  sample_interval: 5000
  config_data {{
   is_root: false
   outfile_name: "{output_path}"
   record_args: "{recort_args}"
  }}
 }}
CONFIG"""
        # Log.debug(f"\n[DEBUG] Hiprofiler Command: {cmd}\n")
        return cmd

    @staticmethod
    def _run_hiperf(driver, cmd):
        """在后台线程中运行 hiperf 命令"""
        driver.shell(cmd, timeout=120)

    @staticmethod
    def generate_hapray_report(scene_dirs: list[str], scene_dir: str) -> bool:
        if not scene_dirs:
            Log.error("Error: scene_dirs length is 0!")
            return False

        """
        执行 hapray 命令生成性能分析报告
        :param scene_dir: 场景目录路径，例如 perf_output/wechat002 或完整路径
        :return: bool 表示是否成功生成报告
        """
        # 获取 perf_testing 目录
        perf_testing_dir = CommonUtils.get_project_root()

        # 获取项目根目录（perf_testing 的上一级目录）
        project_root = os.path.dirname(perf_testing_dir)

        # 检查是否已经是完整路径
        if os.path.isabs(scene_dir):
            # 如果是绝对路径，直接使用
            full_scene_dir = scene_dir
        else:
            # 否则，添加 perf_testing 目录前缀
            full_scene_dir = os.path.normpath(os.path.join(perf_testing_dir, scene_dir))

        # 获取 hapray-cmd.js 的绝对路径
        hapray_cmd_path = os.path.abspath(os.path.join(perf_testing_dir, 'hapray-toolbox', 'hapray-cmd.js'))

        # 检查 hapray-cmd.js 是否存在
        if not os.path.exists(hapray_cmd_path):
            Log.error(f"Error: hapray-cmd.js not found at {hapray_cmd_path}")
            return False

        # 打印调试信息
        Log.info(f"Project root: {project_root}")
        Log.info(f"Scene directory: {full_scene_dir}")
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
            # 设置工作目录为项目根目录，并指定编码为 utf-8
            result = subprocess.run(
                cmd,
                check=True,
                cwd=project_root,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace'  # 使用 replace 策略处理无法解码的字符
            )
            Log.info(f"Command output: {result.stdout}")
            if result.stderr:
                Log.error(f"Command stderr: {result.stderr}")
            return True
        except subprocess.CalledProcessError as e:
            Log.error(f"Failed to generate HapRay report: {str(e)}")
            if e.stdout:
                Log.error(f"Command stdout: {e.stdout}")
            if e.stderr:
                Log.error(f"Command stderr: {e.stderr}")
            return False
        except FileNotFoundError:
            Log.error(
                "Error: Node.js command not found. Please make sure Node.js is installed and in your PATH.")
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
            # if not os.path.exists(local_output_db_path):
            #     return

        except Exception as e:
            # 尝试获取更多调试信息
            self.driver.shell("df -h")
            self.driver.shell("ls -l /data/local/tmp/")

    def _save_perf_and_htrace_data(self, device_file, step_id):
        """保存性能数据和htrace数据

        Args:
            device_file: 设备上的perf文件路径
            step_id: 步骤ID
        """
        # 构建perf的目录结构
        hiperf_dir = os.path.join(self.report_path, 'hiperf')
        perf_step_dir = os.path.join(hiperf_dir, f'step{str(step_id)}')

        # 构建htrace的目录结构
        htrace_dir = os.path.join(self.report_path, 'htrace')
        htrace_step_dir = os.path.join(htrace_dir, f'step{str(step_id)}')

        # 构建文件路径
        local_perf_path = os.path.join(perf_step_dir, Config.get('hiperf.data_filename', 'perf.data'))
        local_perf_db_path = os.path.join(perf_step_dir, Config.get('hiperf.db_filename', 'perf.db'))
        local_htrace_path = os.path.join(htrace_step_dir, 'trace.htrace')

        # 确保所有必要的目录都存在
        os.makedirs(perf_step_dir, exist_ok=True)
        os.makedirs(htrace_step_dir, exist_ok=True)

        # 检查设备上的perf文件是否存在
        try:
            perf_result = self.driver.shell(f"ls -l {device_file}")
            if "No such file" in perf_result:
                Log.error(f"Perf file not found: {device_file}")
                return

            # 检查设备上的htrace文件是否存在
            device_htrace_file = f"{device_file}.htrace"
            htrace_result = self.driver.shell(f"ls -l {device_htrace_file}")
            if "No such file" in htrace_result:
                Log.error(f"Htrace file not found: {device_htrace_file}")
                return

            # 拉取perf文件
            self.driver.pull_file(device_file, local_perf_path)
            if not os.path.exists(local_perf_path):
                Log.error(f"Failed to pull perf file to: {local_perf_path}")
                return

            # 拉取htrace文件
            self.driver.pull_file(device_htrace_file, local_htrace_path)
            if not os.path.exists(local_htrace_path):
                Log.error(f"Failed to pull htrace file to: {local_htrace_path}")
                return

            Log.info(f"Successfully saved perf and htrace data for step {step_id}")
            Log.info(f"Perf data saved to: {local_perf_path}")
            Log.info(f"Htrace data saved to: {local_htrace_path}")

        except Exception as e:
            Log.error(f"Error saving perf and htrace data: {str(e)}")
            # 尝试获取更多调试信息
            self.driver.shell("df -h")
            self.driver.shell("ls -l /data/local/tmp/")

    def execute_step_with_perf(self, step_id, action_func, duration):
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

        Log.info(f'execute_step_with_perf thread start run {duration}s')
        # 创建并启动 hiperf 线程
        hiperf_cmd = PerfTestCase._get_hiperf_cmd(self.pid, output_file, duration)
        hiperf_thread = threading.Thread(target=PerfTestCase._run_hiperf, args=(self.driver, hiperf_cmd))
        hiperf_thread.start()

        # 执行动作
        action_func(self.driver)

        # 等待 hiperf 线程完成
        hiperf_thread.join()
        Log.info(f'execute_step_with_perf thread end')

        # 保存性能数据和htrace数据
        self._save_perf_data(output_file, step_id)

    def execute_step_with_perf_and_trace(self, step_id, action_func, duration, sample_all=False):
        """
        执行一个步骤并同时收集性能数据和trace数据

        Args:
            step_id: 步骤ID
            action_func: 要执行的动作函数
            duration: 数据采集持续时间（秒）
        """
        import threading
        # 设置当前步骤的输出路径
        output_file = f"/data/local/tmp/hiperf_step{step_id}.data"

        # 确保设备上的目标目录存在
        output_dir = os.path.dirname(output_file)
        self.driver.shell(f"mkdir -p {output_dir}")

        # 清理可能存在的旧文件
        self.driver.shell(f"rm -f {output_file}")
        self.driver.shell(f"rm -f {output_file}.htrace")

        if self.pid == -1:
            self.pid = self._get_app_pid()

        Log.info(f'execute_step_with_perf_and_trace thread start run {duration}s')

        # 启动采集线程
        cmd = PerfTestCase._get_trace_and_perf_cmd(self.pid, output_file, duration, sample_all)
        perf_trace_thread = threading.Thread(target=PerfTestCase._run_hiperf, args=(self.driver, cmd))
        perf_trace_thread.start()

        # 执行动作
        action_func(self.driver)

        # 等待线程完成
        perf_trace_thread.join()
        Log.info(f'execute_step_with_perf_and_trace thread end')

        # 保存性能数据和htrace数据（异步）
        def save_data_async():
            self._save_perf_and_htrace_data(output_file, step_id)

        save_thread = threading.Thread(target=save_data_async)
        save_thread.start()
        # 不等待 save_thread，主流程直接返回

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
        return int(self.driver.shell(pid_cmd).strip())
