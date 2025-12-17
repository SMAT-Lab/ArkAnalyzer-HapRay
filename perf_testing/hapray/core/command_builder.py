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

from xdevice import platform_logger

from hapray.core.command_templates import (
    COLLECTION_MODE_MEMORY_ONLY,
    COLLECTION_MODE_PERF_ONLY,
    COLLECTION_MODE_TRACE_PERF,
    COLLECTION_MODE_TRACE_PERF_MEMORY,
    FTRACE_PLUGIN_CONFIG,
    NATIVE_MEMORY_CONFIG,
    PERF_CMD_TEMPLATE,
    TRACE_PERF_CMD_TEMPLATE,
)
from hapray.core.config.config import Config

Log = platform_logger('CommandBuilder')


class CommandBuilder:
    """命令构建类，负责构建性能采集命令"""

    def __init__(self, process_manager):
        """
        初始化CommandBuilder

        Args:
            process_manager: 进程管理器实例
        """
        self.process_manager = process_manager

    def determine_collection_mode(self, trace_enabled: bool, memory_enabled: bool) -> str:
        """
        根据启用的功能确定采集模式

        Args:
            trace_enabled: 是否启用trace采集
            memory_enabled: 是否启用内存采集

        Returns:
            采集模式字符串
        """
        if trace_enabled and memory_enabled:
            return COLLECTION_MODE_TRACE_PERF_MEMORY
        if memory_enabled:
            return COLLECTION_MODE_MEMORY_ONLY
        if trace_enabled:
            return COLLECTION_MODE_TRACE_PERF
        return COLLECTION_MODE_PERF_ONLY

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
        trace_enabled = Config.get('trace.enable', True)
        memory_enabled = Config.get('memory.enable', False)

        self._validate_memory_collection_constraints(memory_enabled, sample_all)

        pids_args = self.process_manager.build_processes_args(sample_all)
        memory_pids = self.process_manager.get_memory_pids() if memory_enabled else []

        collection_mode = self.determine_collection_mode(trace_enabled, memory_enabled)
        return self._build_command_by_mode(collection_mode, output_path, duration, pids_args, memory_pids)

    def _validate_memory_collection_constraints(self, memory_enabled: bool, sample_all: bool):
        """验证内存采集约束"""
        if memory_enabled and sample_all:
            Log.warning(
                'Memory collection enabled but sample_all=True. Memory collection will use application-level only.'
            )
            Log.warning('Consider setting sample_all=False for consistent data collection.')

    def _build_command_by_mode(
        self, mode: str, output_path: str, duration: int, pids_args: str, memory_pids: list[int]
    ) -> str:
        """
        根据采集模式构建命令（策略模式）

        Args:
            mode: 采集模式
            output_path: 输出文件路径
            duration: 采集时长
            pids_args: 进程参数字符串
            memory_pids: 内存采集的进程ID列表

        Returns:
            命令字符串

        Raises:
            ValueError: 未知的采集模式
        """
        strategies = {
            COLLECTION_MODE_MEMORY_ONLY: lambda: self._build_native_memory_command(output_path, duration, memory_pids),
            COLLECTION_MODE_TRACE_PERF: lambda: self._build_trace_perf_command(
                output_path, duration, self._build_perf_command(pids_args, duration)
            ),
            COLLECTION_MODE_TRACE_PERF_MEMORY: lambda: self._build_trace_perf_memory_command(
                output_path, duration, self._build_perf_command(pids_args, duration), memory_pids
            ),
            COLLECTION_MODE_PERF_ONLY: lambda: self._build_perf_command(
                pids_args, duration, 'hiperf record', f'-o {output_path}'
            ),
        }

        strategy = strategies.get(mode)
        if not strategy:
            raise ValueError(f'Unknown collection mode: {mode}')

        return strategy()

    def _build_perf_command(self, pids: str, duration: int, cmd: str = '', output_arg: str = '') -> str:
        """
        构建基础性能采集命令

        Args:
            pids: 进程参数字符串
            duration: 采集时长
            cmd: 命令前缀（默认为空）
            output_arg: 输出参数（默认为空）

        Returns:
            格式化的性能采集命令
        """
        return PERF_CMD_TEMPLATE.format(
            cmd=cmd, pids=pids, output_path=output_arg, duration=duration, event=Config.get('hiperf.event')
        )

    def _build_trace_perf_command(self, output_path: str, duration: int, record_args: str) -> str:
        """
        构建trace+性能组合命令

        Args:
            output_path: 输出文件路径
            duration: 采集时长
            record_args: 性能记录参数

        Returns:
            格式化的命令字符串
        """
        # 为 TRACE_PERF_CMD_TEMPLATE 添加缩进的 ftrace 配置
        indented_ftrace_config = self._indent_ftrace_config()
        return TRACE_PERF_CMD_TEMPLATE.format(
            output_path=output_path, duration=duration, record_args=record_args, ftrace_config=indented_ftrace_config
        )

    def _indent_ftrace_config(self) -> str:
        """为 ftrace 配置添加缩进以匹配 TRACE_PERF_CMD_TEMPLATE 的格式"""
        # TRACE_PERF_CMD_TEMPLATE 中需要一级缩进（一个空格）
        # 注释行不需要缩进，其他行需要缩进
        lines = FTRACE_PLUGIN_CONFIG.split('\n')
        indented_lines = []
        for line in lines:
            if line.strip().startswith('#'):
                # 注释行不缩进
                indented_lines.append(line)
            elif line.strip():
                # 非空行添加缩进
                indented_lines.append(' ' + line)
            else:
                # 空行保持原样
                indented_lines.append(line)
        return '\n'.join(indented_lines)

    def _build_native_memory_command(self, output_path: str, duration: int, pids: list[int]) -> str:
        """
        构建Native Memory采集命令（应用级）

        Args:
            output_path: 设备上的输出文件路径（不含.htrace扩展名）
            duration: 采集时长（秒）
            pids: 要监控的进程ID列表

        Returns:
            通过stdin传递配置的命令字符串

        Raises:
            ValueError: 如果没有提供进程ID
        """
        if not pids:
            Log.error('No PIDs provided for memory collection')
            raise ValueError('Memory collection requires process IDs')

        expand_pids_lines = self._build_expand_pids_lines(pids)
        max_stack_depth = Config.get('memory.max_stack_depth', 100)

        Log.info(f'Memory collection: {len(pids)} process(es) - PIDs: {pids}')

        return NATIVE_MEMORY_CONFIG.format(
            output_path=output_path, duration=duration, max_stack_depth=max_stack_depth, expand_pids=expand_pids_lines
        )

    def _build_trace_perf_memory_command(
        self, output_path: str, duration: int, record_args: str, pids: list[int]
    ) -> str:
        """
        构建trace+性能+内存组合采集命令（应用级）

        Args:
            output_path: 设备上的输出文件路径（不含.htrace扩展名）
            duration: 采集时长（秒）
            record_args: 性能记录参数
            pids: 内存监控的进程ID列表

        Returns:
            通过stdin传递配置的命令字符串

        Raises:
            ValueError: 如果没有提供进程ID
        """
        if not pids:
            Log.error('No PIDs provided for memory collection')
            raise ValueError('Memory collection requires process IDs')

        expand_pids_lines = self._build_expand_pids_lines(pids)
        ftrace_config = self._build_ftrace_plugin_config()
        hiperf_config = self._build_hiperf_plugin_config(output_path, record_args)
        nativehook_config = self._build_nativehook_plugin_config(expand_pids_lines)

        return self._build_combined_command(output_path, duration, ftrace_config, hiperf_config, nativehook_config)

    def _build_expand_pids_lines(self, pids: list[int]) -> str:
        """构建 expand_pids 配置行"""
        return '\n'.join([f'    expand_pids: {pid}' for pid in pids])

    def _build_ftrace_plugin_config(self) -> str:
        """构建 ftrace 插件配置字符串"""
        return FTRACE_PLUGIN_CONFIG

    def _build_hiperf_plugin_config(self, output_path: str, record_args: str) -> str:
        """构建 hiperf 插件配置字符串"""
        return f"""# hiperf plugin configuration
plugin_configs {{
  plugin_name: "hiperf-plugin"
  config_data {{
    is_root: false
    outfile_name: "{output_path}"
    record_args: "{record_args}"
  }}
}}"""

    def _build_nativehook_plugin_config(self, expand_pids_lines: str) -> str:
        """构建 nativehook 插件配置字符串"""
        max_stack_depth = Config.get('memory.max_stack_depth', 100)
        return f"""# nativehook plugin configuration
 plugin_configs {{
  plugin_name: "nativehook"
  sample_interval: 5000
  config_data {{
    save_file: false
    smb_pages: 16384
    max_stack_depth: {max_stack_depth}
    string_compressed: true
    fp_unwind: true
    blocked: true
    callframe_compress: true
    record_accurately: true
    offline_symbolization: true
    startup_mode: false
    malloc_free_matching_interval: 10
{expand_pids_lines}
  }}
 }}"""

    def _build_combined_command(
        self, output_path: str, duration: int, ftrace_config: str, hiperf_config: str, nativehook_config: str
    ) -> str:
        """构建组合命令"""
        return f"""hiprofiler_cmd \\
  -c - \\
  -o {output_path}.htrace \\
  -t {duration} \\
  -s \\
  -k \\
<<CONFIG
# Session configuration
request_id: 1
session_config {{
  buffers {{
    pages: 16384
  }}
}}

{ftrace_config}

{hiperf_config}
{nativehook_config}
CONFIG"""
