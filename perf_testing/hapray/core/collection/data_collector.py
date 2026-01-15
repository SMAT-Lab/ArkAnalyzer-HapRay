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

import os
import threading
import time
from datetime import datetime
from typing import Any

from xdevice import platform_logger

from hapray.core.collection.capture_ui import CaptureUI
from hapray.core.collection.command_builder import CommandBuilder
from hapray.core.collection.command_templates import DIR_HIPERF, DIR_HTRACE, FILENAME_PERF_DATA, FILENAME_TRACE_HTRACE
from hapray.core.collection.data_transfer import DataTransfer
from hapray.core.collection.process_manager import ProcessManager
from hapray.core.collection.xvm import XVM
from hapray.core.config.config import Config

Log = platform_logger('DataCollector')


class DataCollector:
    """性能数据采集类，负责协调数据采集流程"""

    def __init__(self, driver: Any, app_package: str, module_name: str = None):
        """
        初始化DataCollector

        Args:
            driver: 设备驱动对象（需要有shell、pull_file、has_file方法）
            app_package: 应用包名
            module_name: 模块名称（用于覆盖率数据采集）
        """
        self.driver = driver
        self.app_package = app_package
        self.module_name = module_name

        # 初始化各个组件
        self.process_manager = ProcessManager(driver, app_package)
        self.command_builder = CommandBuilder(self.process_manager)
        self.data_transfer = DataTransfer(driver, app_package, module_name)
        self.capture_ui_handler = CaptureUI(driver)
        self.xvm = XVM(driver, app_package)

        # 内存采集线程管理
        self.memory_collection_threads: dict[int, dict] = {}  # step_id -> {'thread': thread, 'stop_event': event}
        # 性能采集线程管理
        self.perf_collection_threads: dict[int, threading.Thread] = {}  # step_id -> thread

    # ==================== 公共接口 ====================

    def collect_step_data_start(self, step_id: int, report_path: str, duration: int, sample_all_processes: bool) -> str:
        """
        步骤开始时的数据采集（统一接口）

        Args:
            step_id: 步骤ID
            report_path: 报告路径
            duration: 采集时长（秒）
            sample_all_processes: 是否采样所有进程

        Returns:
            设备上的输出文件路径
        """
        # 生成并准备输出文件路径
        hiprofiler_output = self._prepare_hiprofiler_output_path(step_id)
        self._clean_previous_output(hiprofiler_output)

        Log.info(f'开始步骤 {step_id} 的数据采集准备')

        perf_step_dir, trace_step_dir = self._get_step_directories(step_id, report_path)
        self._ensure_directories_exist(perf_step_dir, trace_step_dir)
        self.process_manager.save_process_info(perf_step_dir)

        # 检查UI采集开关
        if Config.get('ui.capture_enable', False):
            self.capture_ui_handler.capture_ui(step_id, report_path, 'start')

        self._start_collect_memory_data(step_id, report_path)  # 持续到步骤结束

        Log.info(f'步骤 {step_id} 开始采集准备完成')

        # 启动XVM追踪
        self.xvm.start_trace(duration)

        # 启动性能采集线程
        collection_thread = threading.Thread(
            target=self._run_perf_command, args=(hiprofiler_output, duration, sample_all_processes)
        )
        self.perf_collection_threads[step_id] = collection_thread
        collection_thread.start()

        return hiprofiler_output

    def collect_step_data_end(
        self, hiprofiler_device_file: str, step_id: int, report_path: str, redundant_mode_status: bool
    ):
        """
        步骤结束时的数据采集（统一接口）

        注意：memory 数据已包含在 trace.htrace 中，不再单独保存

        Args:
            hiprofiler_device_file: 设备上的文件路径
            step_id: 步骤ID
            report_path: 报告路径
            redundant_mode_status: 是否启用冗余模式
        """
        # 等待性能采集线程完成
        if step_id in self.perf_collection_threads:
            collection_thread = self.perf_collection_threads[step_id]
            collection_thread.join()
            del self.perf_collection_threads[step_id]

        Log.info(f'开始步骤 {step_id} 的数据采集结束处理')
        self._stop_memory_collection(step_id)

        perf_step_dir, trace_step_dir = self._get_step_directories(step_id, report_path)
        self._ensure_directories_exist(perf_step_dir, trace_step_dir)

        local_perf_path = os.path.join(perf_step_dir, Config.get('hiperf.data_filename', FILENAME_PERF_DATA))
        local_trace_path = os.path.join(trace_step_dir, FILENAME_TRACE_HTRACE)

        self.process_manager.save_process_info(perf_step_dir)
        self.data_transfer.transfer_perf_data('/data/local/tmp/perf.data', local_perf_path)
        self.data_transfer.transfer_trace_data(hiprofiler_device_file, local_trace_path)
        self.data_transfer.transfer_redundant_data(trace_step_dir, redundant_mode_status)
        self.data_transfer.collect_coverage_data(perf_step_dir)

        # 检查UI采集开关
        if Config.get('ui.capture_enable', False):
            self.capture_ui_handler.capture_ui(step_id, report_path, 'end')

        # 检查是否启用 snapshot 采集，如果启用则采集一次
        snapshot_enabled = Config.get('memory.snapshot_enable', False)
        if snapshot_enabled:
            self._collect_snapshot_once(step_id, report_path)

        Log.info(f'步骤 {step_id} 数据采集结束处理完成')

        # 停止XVM追踪
        self.xvm.stop_trace(perf_step_dir)

    # ==================== 私有方法：步骤采集 ====================

    def _build_collection_command(self, output_path: str, duration: int, sample_all: bool) -> str:
        """
        根据采集参数构建采集命令（私有方法）

        Args:
            output_path: 设备上的输出文件路径
            duration: 采集时长（秒）
            sample_all: 是否采样所有进程

        Returns:
            格式化的采集命令字符串
        """
        return self.command_builder.build_collection_command(output_path, duration, sample_all)

    def _run_perf_command(self, output_path: str, duration: int, sample_all: bool):
        """
        在设备上执行性能采集命令（私有方法）

        Args:
            output_path: 设备上的输出文件路径
            duration: 预期时长（秒）
            sample_all: 是否采样所有进程
        """
        command = self._build_collection_command(output_path, duration, sample_all)
        Log.info(f'Starting performance collection for {duration}s')
        Log.info(f'Command: {command}')
        result = self.driver.shell(command, timeout=duration + 30)
        Log.info('Performance collection completed %s', result)

    # ==================== 私有方法：工具函数 ====================

    def _prepare_hiprofiler_output_path(self, step_id: int) -> str:
        """
        生成设备上的输出文件路径（私有方法）

        Args:
            step_id: 步骤ID

        Returns:
            设备上的输出文件路径
        """
        return f'/data/local/tmp/hiperf_step{step_id}.data'

    def _clean_previous_output(self, output_path: str):
        """
        清理设备上的旧输出文件（私有方法）

        Args:
            output_path: 输出文件路径
        """
        output_dir = os.path.dirname(output_path)
        self.driver.shell(f'mkdir -p {output_dir}')
        self.driver.shell(f'rm -f {output_path}')
        self.driver.shell(f'rm -f {output_path}.htrace')

    def _get_step_directories(self, step_id: int, report_path: str) -> tuple[str, str]:
        """
        获取步骤目录路径

        Args:
            step_id: 步骤ID
            report_path: 报告路径

        Returns:
            (perf_step_dir, trace_step_dir) 元组
        """
        perf_step_dir = os.path.join(report_path, DIR_HIPERF, f'step{step_id}')
        trace_step_dir = os.path.join(report_path, DIR_HTRACE, f'step{step_id}')
        return perf_step_dir, trace_step_dir

    def _ensure_directories_exist(self, *paths):
        """
        确保所需目录存在

        Args:
            *paths: 目录路径列表
        """
        for path in paths:
            os.makedirs(path, exist_ok=True)

    # ==================== 私有方法：内存采集 ====================

    def _start_collect_memory_data(
        self, step_id: int, report_path: str, interval_seconds: int = Config.get('memory.interval_seconds', 5)
    ):
        """
        启动内存采集后台线程（私有方法）

        Args:
            step_id: 步骤ID
            report_path: 报告路径
            interval_seconds: 采集间隔（秒）
        """
        # 如果该步骤已有活跃的采集线程，先停止它
        if step_id in self.memory_collection_threads:
            self._stop_memory_collection(step_id)

        # 创建停止事件
        stop_event = threading.Event()

        # 创建并启动采集线程
        thread = threading.Thread(
            target=self._memory_collection_worker,
            args=(step_id, report_path, None, interval_seconds, stop_event),
            daemon=True,
        )

        # 保存线程信息
        self.memory_collection_threads[step_id] = {'thread': thread, 'stop_event': stop_event}

        thread.start()
        Log.info(f'启动步骤 {step_id} 的内存数据采集线程，每 {interval_seconds}s 采集一次，持续直到停止')

    def _memory_collection_worker(
        self, step_id: int, report_path: str, duration_seconds: int, interval_seconds: int, stop_event: threading.Event
    ):
        """
        内存采集工作线程

        Args:
            step_id: 步骤ID
            report_path: 报告路径
            duration_seconds: 采集总时长（秒），如果为None则持续直到被停止
            interval_seconds: 采集间隔（秒）
            stop_event: 停止事件
        """
        if duration_seconds is None:
            Log.info(f'内存采集线程启动：步骤 {step_id}，持续采集，间隔 {interval_seconds}s')
            end_time = None
        else:
            Log.info(f'内存采集线程启动：步骤 {step_id}，总时长 {duration_seconds}s，间隔 {interval_seconds}s')
            end_time = time.time() + duration_seconds

        collection_count = 0

        while (end_time is None or time.time() < end_time) and not stop_event.is_set():
            collection_count += 1
            Log.info(f'步骤 {step_id} 第 {collection_count} 次内存数据采集')

            # 记录采集开始时间
            collection_start_time = time.time()

            try:
                # 内联的内存数据采集逻辑
                # 生成时间戳（yyyymmdd-hhmmss格式）
                timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
                timestamp = f'{timestamp}_count{collection_count}'

                # 创建内存数据目录
                meminfo_step_dir = os.path.join(report_path, 'meminfo', f'step{step_id}')
                showmap_dir = os.path.join(meminfo_step_dir, 'dynamic_showmap')
                gpu_mem_dir = os.path.join(meminfo_step_dir, 'dynamic_gpuMem')
                dmabuf_dir = os.path.join(meminfo_step_dir, 'dynamic_process_dmabuff_info')

                self._ensure_directories_exist(showmap_dir, gpu_mem_dir, dmabuf_dir)

                # 获取所有进程ID和名称
                process_ids, process_names = self.process_manager.get_app_pids()

                # 为每个pid创建smaps采集线程
                smaps_threads = []
                for pid, process_name in zip(process_ids, process_names):
                    thread = threading.Thread(
                        target=self._collect_smaps_data,
                        args=(pid, process_name, showmap_dir, timestamp),
                        daemon=True,
                    )
                    smaps_threads.append(thread)

                # 创建GPU和DMA采集线程
                gpu_thread = threading.Thread(
                    target=self._collect_gpu_data,
                    args=(gpu_mem_dir, timestamp),
                    daemon=True,
                )
                dma_thread = threading.Thread(
                    target=self._collect_dma_data,
                    args=(dmabuf_dir, timestamp),
                    daemon=True,
                )

                # 启动所有线程（包括所有smaps线程、GPU线程和DMA线程）
                all_threads = smaps_threads + [gpu_thread, dma_thread]
                for thread in all_threads:
                    thread.start()

                # 等待所有线程完成
                for thread in all_threads:
                    thread.join()

                Log.debug(f'步骤 {step_id} 第 {collection_count} 次内存数据采集完成')
            except Exception as e:
                Log.error(f'步骤 {step_id} 第 {collection_count} 次内存数据采集失败: {e}')

            # 计算采集耗时
            collection_elapsed = time.time() - collection_start_time
            # 等待时间 = 间隔时间 - 采集耗时，如果采集耗时超过间隔时间，则立即进行下一次采集
            wait_time = max(0, interval_seconds - collection_elapsed)

            # 等待下一次采集或停止事件
            if stop_event.wait(timeout=wait_time):
                # 被停止事件唤醒，退出循环
                break

        Log.info(f'步骤 {step_id} 内存数据采集线程结束，共采集 {collection_count} 次')

    def _stop_memory_collection(self, step_id: int):
        """
        停止指定步骤的内存采集线程（私有方法）

        Args:
            step_id: 步骤ID
        """
        if step_id in self.memory_collection_threads:
            thread_info = self.memory_collection_threads[step_id]
            thread_info['stop_event'].set()  # 设置停止事件
            thread_info['thread'].join(timeout=5)  # 等待线程结束，最多5秒

            if thread_info['thread'].is_alive():
                Log.warning(f'步骤 {step_id} 的内存采集线程未能及时停止')

            del self.memory_collection_threads[step_id]
            Log.info(f'步骤 {step_id} 的内存采集线程已停止')
        else:
            Log.warning(f'步骤 {step_id} 没有活跃的内存采集线程')

    def _collect_smaps_data(self, pid: int, process_name: str, showmap_dir: str, timestamp: str):
        """采集单个进程的smaps数据

        Args:
            pid: 进程ID
            process_name: 进程名称
            showmap_dir: smaps目录路径
            timestamp: 时间戳
        """
        try:
            # 清理进程名，移除路径和特殊字符
            clean_process_name = os.path.basename(process_name).replace('/', '_').replace(' ', '_')
            filename = f'{clean_process_name}_{pid}_{timestamp}.txt'
            filepath = os.path.join(showmap_dir, filename)

            cmd = f'hidumper --mem-smaps {pid}'
            Log.debug(f'采集smaps数据: {cmd}')
            result = self.driver.shell(cmd)

            # 保存到本地文件
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(result)

            Log.debug(f'smaps数据已保存: {filepath}')

        except Exception as e:
            Log.warning(f'采集smaps数据失败 (PID: {pid}): {e}')

    def _collect_gpu_data(self, gpu_mem_dir: str, timestamp: str):
        """采集GPU数据（需要root权限）

        Args:
            gpu_mem_dir: GPU内存目录路径
            timestamp: 时间戳
        """
        try:
            filename = f'gpuMen_{timestamp}.txt'
            filepath = os.path.join(gpu_mem_dir, filename)

            cmd = 'cat /proc/gpu_memory'
            Log.debug(f'采集GPU数据: {cmd}')
            result = self.driver.shell(cmd)

            # 保存到本地文件
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(result)

            Log.debug(f'GPU数据已保存: {filepath}')
        except Exception as e:
            Log.warning(f'采集GPU数据失败（可能需要root权限）: {e}')

    def _collect_dma_data(self, dmabuf_dir: str, timestamp: str):
        """采集DMA数据（需要root权限）

        Args:
            dmabuf_dir: DMA目录路径
            timestamp: 时间戳
        """
        try:
            filename = f'process_dmabuff_info_{timestamp}.txt'
            filepath = os.path.join(dmabuf_dir, filename)

            cmd = 'cat /proc/process_dmabuf_info'
            Log.debug(f'采集DMA数据: {cmd}')
            result = self.driver.shell(cmd)

            # 保存到本地文件
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(result)

            Log.debug(f'DMA数据已保存: {filepath}')
        except Exception as e:
            Log.warning(f'采集DMA数据失败（可能需要root权限）: {e}')

    # ==================== 私有方法：Snapshot采集 ====================

    def _collect_snapshot_once(self, step_id: int, report_path: str):
        """采集一次 snapshot 数据（在步骤开始时执行）

        Args:
            step_id: 步骤ID
            report_path: 报告路径
        """
        try:
            # 创建 snapshot 目录
            meminfo_step_dir = os.path.join(report_path, 'meminfo', f'step{step_id}')
            snapshot_dir = os.path.join(meminfo_step_dir, 'dynamic_snapshot')
            self._ensure_directories_exist(snapshot_dir)

            # 只取 UI 主线程的 pid（使用应用进程列表中的第一个作为主线程）
            process_ids, process_names = self.process_manager.get_app_pids()
            if not process_ids:
                Log.warning('snapshot 采集失败：未找到应用进程')
                return

            ui_pid = process_ids[0]
            ui_process_name = process_names[0] if process_names else str(ui_pid)

            Log.info(f'步骤 {step_id} snapshot 采集目标进程: pid={ui_pid}, name={ui_process_name}')

            self._collect_snapshot_data(ui_pid, ui_process_name, snapshot_dir)

            Log.info(f'步骤 {step_id} snapshot 采集完成（仅 UI 主线程）')
        except Exception as e:
            Log.error(f'步骤 {step_id} snapshot 采集失败: {e}')

    def _collect_snapshot_data(self, pid: int, process_name: str, snapshot_dir: str):
        """采集单个进程的heap snapshot数据

        Args:
            pid: 进程ID（同时也是线程ID）
            process_name: 进程名称
            snapshot_dir: snapshot目录路径
        """
        try:
            # 设备上的 snapshot 文件目录
            device_snapshot_dir = '/data/log/reliability/resource_leak/memory_leak'

            # 执行 hidumper --mem-jsheap pid -T pid 命令
            # 其中 pid 和 tid 相同，均为应用进程 id
            # 该命令不会直接输出，而是生成文件在设备目录下
            cmd = f'hidumper --mem-jsheap {pid} -T {pid}'
            Log.debug(f'采集snapshot数据: {cmd}')
            self.driver.shell(cmd)

            # 等待文件生成（hidumper 命令可能需要一些时间）
            time.sleep(30)

            # 查找设备目录中匹配的文件
            # 文件命名格式：hidumper-jsheap-进程号-JS线程号-时间戳
            # 由于时间戳是动态的，我们需要列出目录并匹配模式
            # 如果文件未生成，等待1秒后重试，最多重试5次
            list_cmd = f'ls {device_snapshot_dir}/hidumper-jsheap-{pid}-{pid}-* 2>/dev/null || true'
            result = self.driver.shell(list_cmd)

            # 解析文件列表，获取最新的文件
            # ls 输出可能包含完整路径或相对路径，需要统一处理
            files = []
            for _line in result.splitlines():
                line = _line.strip()
                if not line or 'hidumper-jsheap' not in line:
                    continue
                # 如果是完整路径，直接使用；如果是相对路径，拼接完整路径
                if line.startswith('/'):
                    files.append(line)
                else:
                    files.append(os.path.join(device_snapshot_dir, line))

            if not files:
                Log.warning(f'未找到匹配的snapshot文件 (PID: {pid})')
                return

            # 按文件名排序，获取最新的文件（文件名包含时间戳，排序后最后一个是最新的）
            files.sort()
            latest_file = files[-1]

            # 清理进程名，移除路径和特殊字符
            clean_process_name = os.path.basename(process_name).replace('/', '_').replace(' ', '_')
            # 从设备文件名中提取时间戳部分
            device_filename = os.path.basename(latest_file)
            local_filename = f'{clean_process_name}_{device_filename}.heapsnapshot'
            local_filepath = os.path.join(snapshot_dir, local_filename)

            # 使用 driver.pull_file 拉取文件
            Log.debug(f'拉取snapshot文件: {latest_file} -> {local_filepath}')
            self.driver.pull_file(latest_file, local_filepath)

            # 验证文件是否成功保存
            if os.path.exists(local_filepath):
                Log.debug(f'snapshot数据已保存: {local_filepath}')
                # 删除设备上的原文件
                try:
                    self.driver.shell(f'rm {latest_file}')
                    Log.debug(f'已删除设备上的snapshot文件: {latest_file}')
                except Exception as e:
                    Log.warning(f'删除设备上的snapshot文件失败: {latest_file}, 错误: {e}')
            else:
                Log.warning(f'snapshot文件拉取失败: {local_filepath}')

        except Exception as e:
            Log.warning(f'采集snapshot数据失败 (PID: {pid}): {e}')
