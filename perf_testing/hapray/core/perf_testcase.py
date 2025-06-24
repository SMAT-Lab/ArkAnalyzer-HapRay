"""
Copyright (c) 2025 Huawei Device Co., Ltd.
Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

 http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

import json
import os
import threading
import time
from abc import abstractmethod

from devicetest.core.test_case import TestCase
from hypium import UiDriver
from xdevice import platform_logger

from hapray.core.config.config import Config

Log = platform_logger("PerfTestCase")

_PERF_CMD_TEMPLATE = '{cmd} {pids} --call-stack dwarf --kernel-callchain -f 1000 --cpu-limit 100 -e {event} --enable-debuginfo-symbolic --clockid boottime -m 1024 -d {duration} {output_path}'
_TRACE_PERF_CMD_TEMPLATE = """hiprofiler_cmd \\
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
  config_data {{
   is_root: false
   outfile_name: "{output_path}"
   record_args: "{record_args}"
  }}
 }}
CONFIG"""


class PerfTestCase(TestCase):
    def __init__(self, tag: str, configs):
        super().__init__(tag, configs)
        self.driver = UiDriver(self.device1)
        self.TAG = tag
        self.pid = -1
        self._start_app_package = None

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
    def _build_trace_perf_cmd(output_path, duration, record_args) -> str:
        """构建trace和perf命令的通用方法"""
        return _TRACE_PERF_CMD_TEMPLATE.format(
            output_path=output_path,
            duration=duration,
            record_args=record_args
        )

    @staticmethod
    def _build_perf_cmd(pids: str, duration: int, cmd='', output_path='') -> str:
        return _PERF_CMD_TEMPLATE.format(cmd=cmd, pids=pids, output_path=output_path, duration=duration,
                                         event=Config.get('hiperf.event'))

    @staticmethod
    def _get_hiperf_cmd(pid, output_path, duration, sample_all=False):
        """生成 hiperf 命令

        Args:
            pid: 进程ID
            output_path: 输出文件路径
            duration: 采集持续时间（秒）
            sample_all: 是否采样所有进程（需要root权限）

        Returns:
            str: 完整的 hiperf 命令
        """
        if sample_all:
            return PerfTestCase._build_perf_cmd(cmd='hiperf record', pids='-a', duration=duration,
                                                output_path=f'-o {output_path}')
        else:
            return PerfTestCase._build_perf_cmd(cmd='hiperf record', pids=f'-p {pid}', duration=duration,
                                                output_path=f'-o {output_path}')

    @staticmethod
    def _get_trace_and_perf_cmd(pids: str, output_path: str, duration: int) -> str:
        """生成同时抓取trace和perf数据的命令

        Args:
            pid: 进程ID
            output_path: 输出文件路径
            duration: 采集持续时间（秒）
            sample_all: 是否采样所有进程（需要root权限）

        Returns:
            str: 完整的命令
        """
        record_args = PerfTestCase._build_perf_cmd(pids=pids, duration=duration)
        # 基础命令部分
        return PerfTestCase._build_trace_perf_cmd(
            output_path=output_path,
            duration=duration,
            record_args=record_args
        )

    @staticmethod
    def _run_hiperf(driver, cmd):
        """在后台线程中运行 hiperf 命令"""
        driver.shell(cmd, timeout=120)

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

        self._save_app_pids(perf_step_dir)

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

    def execute_step_with_perf_and_trace(self, step_id, action_func, duration: int, sample_all=False):
        """
        执行一个步骤并同时收集性能数据和trace数据

        Args:
            step_id: 步骤ID
            action_func: 要执行的动作函数
            duration: 数据采集持续时间（秒）
            sample_all: 是否采样所有进程（需要root权限）
            is_multi_pid: 是否采集多个进程的数据，默认为True
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
        if sample_all:
            # 如果是root权限，直接使用sample_all模式
            cmd = PerfTestCase._get_trace_and_perf_cmd('-a', output_file, duration)
        else:
            # 如果不是root权限，且需要采集多个进程
            pids, process_names = self._get_app_pids()
            if not pids:
                Log.error("No process found for multi-pid collection")
                return
            # 记录进程信息
            for pid, name in zip(pids, process_names):
                Log.info(f"Found process: {name} (PID: {pid})")
            pid_args = ','.join(map(str, pids))
            cmd = PerfTestCase._get_trace_and_perf_cmd(f'-p {pid_args}', output_file, duration)

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
            "device": self.devices[0].device_description,
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

    def _get_app_pids(self) -> tuple[list[int], list[str]]:
        """获取应用的所有相关进程ID和进程名

        使用 ps -ef | grep 命令获取所有相关进程，并过滤掉grep进程本身。
        例如对于 com.jd.hm.mall 可能会返回:
        - PIDs: [1234, 1235]
        - 进程名: ["com.jd.hm.mall", "com.jd.hm.mall:render"]
        等所有相关进程的PID和进程名

        Returns:
            tuple[list[int], list[str]]: 返回两个列表，第一个是进程ID列表，第二个是进程名列表
        """
        # 使用 ps -ef | grep 命令获取所有相关进程
        app_package = self.app_package
        if self._start_app_package is not None:
            app_package = self._start_app_package
        cmd = f"ps -ef | grep {app_package}"
        result = self.driver.shell(cmd)

        # 解析输出，提取PID和进程名
        pids = []
        process_names = []
        for line in result.splitlines():
            # 跳过grep进程本身
            if 'grep' in line:
                continue

            # 尝试从每行提取PID和进程名
            try:
                # ps -ef 输出格式: UID PID PPID ... CMD
                parts = line.split()
                if len(parts) >= 2:
                    pid = int(parts[1])
                    # 获取进程名（通常是最后一个部分）
                    process_name = parts[-1]
                    pids.append(pid)
                    process_names.append(process_name)
            except (ValueError, IndexError):
                continue

        return pids, process_names

    def _get_app_pid(self) -> int:
        pid_cmd = f"pidof {self.app_package}"
        return int(self.driver.shell(pid_cmd).strip())

    def _save_app_pids(self, perf_step_dir):
        pids, process_names = self._get_app_pids()
        result_path = os.path.join(perf_step_dir, 'pids.json')
        with open(result_path, 'w', encoding='utf-8') as f:
            json.dump({'pids': pids, 'process_names': process_names}, f, indent=4, ensure_ascii=False)
