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

from hapray.core.collection.command_templates import (
    FTRACE_PLUGIN_CONFIG,
    HIPROFILER_CMD_TEMPLATE,
    MEMORY_PLUGIN_CONFIG,
    PERF_PLUGIN_CONFIG,
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
        pids_args = self.process_manager.build_processes_args(sample_all)

        perf_enabled = Config.get('hiperf.enable', True)
        trace_enabled = Config.get('trace.enable', True)
        memory_enabled = Config.get('memory.enable', False)
        # 构建各个配置
        ftrace_config = self._build_ftrace_config() if trace_enabled else ''
        perf_config = self._build_perf_config(pids_args, output_path, duration) if perf_enabled else ''
        memory_config = self._build_memory_config() if memory_enabled else ''

        # 统一使用 HIPROFILER_CMD_TEMPLATE
        return HIPROFILER_CMD_TEMPLATE.format(
            output_path=output_path,
            duration=duration,
            ftrace_config=ftrace_config,
            perf_config=perf_config,
            memory_config=memory_config,
        )

    def _build_ftrace_config(self) -> str:
        """构建并缩进 ftrace 配置"""
        return self._indent_config(FTRACE_PLUGIN_CONFIG)

    def _build_perf_config(self, pids: str, output_path: str, duration: int) -> str:
        """构建并缩进 perf 配置"""
        perf_config = PERF_PLUGIN_CONFIG.format(
            pids=pids, output_path=output_path, duration=duration, event=Config.get('hiperf.event')
        )
        return self._indent_config(perf_config)

    def _build_memory_config(self) -> str:
        """构建并缩进 memory 配置"""
        try:
            memory_pids = self.process_manager.get_memory_pids()
        except Exception as e:
            Log.error(f'Failed to get memory pids: {e}')
            memory_pids = []
            return ''

        if not memory_pids:
            Log.error('No PIDs provided for memory collection')
            raise ValueError('Memory collection requires process IDs')

        expand_pids_lines = self._build_expand_pids_lines(memory_pids)
        max_stack_depth = Config.get('memory.max_stack_depth', 100)

        Log.info(f'Memory collection: {len(memory_pids)} process(es) - PIDs: {memory_pids}')

        memory_config = MEMORY_PLUGIN_CONFIG.format(max_stack_depth=max_stack_depth, expand_pids=expand_pids_lines)
        return self._indent_config(memory_config)

    def _indent_config(self, config: str) -> str:
        """为配置添加缩进以匹配 HIPROFILER_CMD_TEMPLATE 的格式"""
        # HIPROFILER_CMD_TEMPLATE 中需要一级缩进（一个空格）
        # 注释行不需要缩进，其他行需要缩进
        lines = config.split('\n')
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

    def _build_expand_pids_lines(self, pids: list[int]) -> str:
        """构建 expand_pids 配置行"""
        return '\n'.join([f'    expand_pids: {pid}' for pid in pids])
