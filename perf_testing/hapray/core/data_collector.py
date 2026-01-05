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

from hapray.core.capture_ui import CaptureUI
from hapray.core.command_builder import CommandBuilder
from hapray.core.command_templates import DIR_HIPERF, DIR_HTRACE, FILENAME_PERF_DATA, FILENAME_TRACE_HTRACE
from hapray.core.config.config import Config
from hapray.core.data_transfer import DataTransfer
from hapray.core.process_manager import ProcessManager

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

        # 内存采集线程管理
        self.memory_collection_threads: dict[int, dict] = {}  # step_id -> {'thread': thread, 'stop_event': event}

    def build_collection_command(self, output_path: str, duration: int, sample_all: bool) -> str:
        """
        根据采集参数构建采集命令

        Args:
            output_path: 设备上的输出文件路径
            duration: 采集时长（秒）
            sample_all: 是否采样所有进程

        Returns:
            格式化的采集命令字符串
        """
        return self.command_builder.build_collection_command(output_path, duration, sample_all)

    def run_perf_command(self, command: str, duration: int):
        """
        在设备上执行性能采集命令

        Args:
            command: 要执行的命令
            duration: 预期时长（秒）
        """
        Log.info(f'Starting performance collection for {duration}s')
        Log.info(f'Command: {command}')
        result = self.driver.shell(command, timeout=duration + 30)
        Log.info('Performance collection completed %s', result)

    def collect_step_start(self, step_id: int, report_path: str):
        """
        步骤开始时的数据采集

        Args:
            step_id: 步骤ID
            report_path: 报告路径
        """
        Log.info(f'开始步骤 {step_id} 的数据采集准备')

        perf_step_dir, trace_step_dir = self._get_step_directories(step_id, report_path)
        self._ensure_directories_exist(perf_step_dir, trace_step_dir)
        self.process_manager.save_process_info(perf_step_dir)

        # 检查UI采集开关
        if Config.get('ui.capture_enable', False):
            self.capture_ui_handler.capture_ui(step_id, report_path, 'start')

        self.start_collect_memory_data(step_id, report_path)  # 持续到步骤结束

        Log.info(f'步骤 {step_id} 开始采集准备完成')

    def collect_step_end(self, device_file: str, step_id: int, report_path: str, redundant_mode_status: bool):
        """
        步骤结束时的数据采集和保存

        注意：memory 数据已包含在 trace.htrace 中，不再单独保存

        Args:
            device_file: 设备上的文件路径
            step_id: 步骤ID
            report_path: 报告路径
            redundant_mode_status: 是否启用冗余模式
        """
        Log.info(f'开始步骤 {step_id} 的数据采集结束处理')

        perf_step_dir, trace_step_dir = self._get_step_directories(step_id, report_path)
        self._ensure_directories_exist(perf_step_dir, trace_step_dir)

        local_perf_path = os.path.join(perf_step_dir, Config.get('hiperf.data_filename', FILENAME_PERF_DATA))
        local_trace_path = os.path.join(trace_step_dir, FILENAME_TRACE_HTRACE)

        self.process_manager.save_process_info(perf_step_dir)
        self.data_transfer.transfer_perf_data(device_file, local_perf_path)
        self.data_transfer.transfer_trace_data(device_file, local_trace_path)
        self.data_transfer.transfer_redundant_data(trace_step_dir, redundant_mode_status)
        self.data_transfer.collect_coverage_data(perf_step_dir)

        # 检查UI采集开关
        if Config.get('ui.capture_enable', False):
            self.capture_ui_handler.capture_ui(step_id, report_path, 'end')

        self.stop_memory_collection(step_id)

        Log.info(f'步骤 {step_id} 数据采集结束处理完成')

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

    def start_collect_memory_data(
        self, step_id: int, report_path: str, interval_seconds: int = Config.get('memory.interval_seconds', 5)
    ):
        """
        启动内存采集后台线程

        Args:
            step_id: 步骤ID
            report_path: 报告路径
            interval_seconds: 采集间隔（秒）
        """
        # 如果该步骤已有活跃的采集线程，先停止它
        if step_id in self.memory_collection_threads:
            self.stop_memory_collection(step_id)

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

            cmd = 'cat /proc/process_dmabuff_info'
            Log.debug(f'采集DMA数据: {cmd}')
            result = self.driver.shell(cmd)

            # 保存到本地文件
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(result)

            Log.debug(f'DMA数据已保存: {filepath}')
        except Exception as e:
            Log.warning(f'采集DMA数据失败（可能需要root权限）: {e}')

    def stop_memory_collection(self, step_id: int):
        """
        停止指定步骤的内存采集线程

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

    def get_active_memory_collections(self) -> list[int]:
        """
        获取当前活跃的内存采集步骤ID列表

        Returns:
            活跃的步骤ID列表
        """
        return list(self.memory_collection_threads.keys())
