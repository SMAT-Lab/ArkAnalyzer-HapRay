"""
工具执行器 - 负责执行工具并管理执行状态
"""

import os
import subprocess
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any, Optional

from core.base_tool import ToolResult
from core.config_manager import ConfigManager
from core.logger import get_logger

logger = get_logger(__name__)


class ToolExecutor:
    """工具执行器"""

    def __init__(self):
        self.config = ConfigManager()
        self.running_tasks: dict[str, subprocess.Popen] = {}
        self.task_callbacks: dict[str, Callable] = {}

    def execute_tool(
        self,
        plugin_id: str,
        executable_path: str,
        script_path: Optional[str] = None,
        params: dict[str, Any] = None,
        plugin_root_dir: Optional[str] = None,
        callback: Optional[Callable[[str], None]] = None,
        action_mapping: Optional[dict[str, Any]] = None,
    ) -> ToolResult:
        """
        执行工具（统一入口，支持 Python、Node.js 和 exe）

        Args:
            plugin_id: 插件ID
            executable_path: 可执行文件路径（python/node/exe）
            script_path: 脚本路径（可选，对于 exe 通常不需要）
            params: 参数字典
            plugin_root_dir: 插件根目录（用作工作目录 cwd）
            callback: 输出回调函数
            action_mapping: action 映射配置，格式：
                {
                    "type": "position" | "remove" | "map",
                    "mappings": {  # 仅当 type 为 "map" 时存在
                        "action_name": ["command", "args", ...]
                    }
                }

        Returns:
            ToolResult: 执行结果
        """
        if params is None:
            params = {}

        try:
            # 直接执行 exe 文件
            cmd = [executable_path]
            if script_path:
                cmd.append(script_path)

            # 处理 action 映射
            if 'action' in params:
                action = params.pop('action')
                if action_mapping:
                    mapping_type = action_mapping.get('type')
                    if mapping_type == 'position':
                        # action 作为位置参数直接添加
                        cmd.append(action)
                    elif mapping_type == 'remove':
                        # action 被移除，不传递
                        pass
                    elif mapping_type == 'map':
                        # action 映射到特定的命令序列
                        mapping_cmd = action_mapping.get('command', [])
                        # 支持占位符替换，如 {command} 会被 params 中的 command 值替换
                        for item in mapping_cmd:
                            if isinstance(item, str) and item.startswith('{') and item.endswith('}'):
                                # 占位符，从 params 中获取值
                                placeholder_key = item[1:-1]
                                placeholder_value = params.pop(placeholder_key, None)
                                if placeholder_value:
                                    cmd.append(str(placeholder_value))
                            else:
                                cmd.append(str(item))
                else:
                    # 没有配置，默认作为位置参数（向后兼容）
                    cmd.append(action)

            # 添加参数
            for key, value in params.items():
                if value is None or value == '':
                    continue
                # 处理参数名转换（GUI中的参数名可能包含下划线，需要转换为命令行格式）
                param_name = key.replace('_', '-')
                if isinstance(value, bool):
                    if value:
                        cmd.append(f'--{param_name}')
                elif isinstance(value, list):
                    cmd.extend([f'--{param_name}'] + [str(v) for v in value])
                else:
                    cmd.extend([f'--{param_name}', str(value)])

            logger.info(f'执行命令: {" ".join(cmd)}')

            # 确定工作目录：使用插件根目录，如果未提供则使用当前工作目录
            working_dir = plugin_root_dir if plugin_root_dir else os.getcwd()
            if working_dir:
                working_dir = str(Path(working_dir).resolve())

            logger.info(f'工作目录: {working_dir}')

            # 执行命令
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8',
                cwd=working_dir,
                bufsize=1,
            )

            self.running_tasks[plugin_id] = process
            if callback:
                self.task_callbacks[plugin_id] = callback

            # 实时读取输出
            output_lines = []
            error_lines = []

            def read_output():
                if process.stdout:
                    for line in iter(process.stdout.readline, ''):
                        if not line:
                            break
                        output_lines.append(line)
                        if callback:
                            callback(line.rstrip())

            def read_error():
                if process.stderr:
                    for line in iter(process.stderr.readline, ''):
                        if not line:
                            break
                        error_lines.append(line)
                        if callback:
                            callback(line.rstrip())

            output_thread = threading.Thread(target=read_output, daemon=True)
            error_thread = threading.Thread(target=read_error, daemon=True)
            output_thread.start()
            error_thread.start()

            # 等待完成
            return_code = process.wait()
            output_thread.join(timeout=1)
            error_thread.join(timeout=1)

            del self.running_tasks[plugin_id]
            if plugin_id in self.task_callbacks:
                del self.task_callbacks[plugin_id]

            output = ''.join(output_lines)
            error_output = ''.join(error_lines)

            if return_code == 0:
                # 尝试从参数中提取输出路径
                output_path = None
                if 'output' in params:
                    output_path = params['output']
                elif 'output_dir' in params:
                    output_path = params['output_dir']

                return ToolResult(
                    success=True,
                    message='执行成功',
                    output_path=output_path,
                    data={'output': output},
                )
            return ToolResult(success=False, message='执行失败', error=error_output or output)

        except Exception as e:
            logger.error(f'执行工具失败: {e}', exc_info=True)
            return ToolResult(success=False, message=f'执行失败: {str(e)}', error=str(e))

    def cancel_task(self, plugin_id: str) -> bool:
        """取消正在执行的任务"""
        if plugin_id in self.running_tasks:
            process = self.running_tasks[plugin_id]
            try:
                process.terminate()
                process.wait(timeout=5)
            except (subprocess.TimeoutExpired, ProcessLookupError):
                process.kill()
            del self.running_tasks[plugin_id]
            if plugin_id in self.task_callbacks:
                del self.task_callbacks[plugin_id]
            return True
        return False

    def is_running(self, plugin_id: str) -> bool:
        """检查任务是否正在运行"""
        return plugin_id in self.running_tasks
