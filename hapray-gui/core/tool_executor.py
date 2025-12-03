"""
工具执行器 - 负责执行工具并管理执行状态
"""

import os
import re
import subprocess
import sys
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
            # 检查可执行文件路径
            logger.info(f'调试信息 - 当前Python: {sys.executable}')
            logger.info(f'调试信息 - executable_path: {executable_path}')
            logger.info(f'调试信息 - script_path: {script_path}')
            logger.info(f'调试信息 - plugin_root_dir: {plugin_root_dir}')
            logger.info(f'调试信息 - params: {params}')
            logger.info(f'调试信息 - 工作目录: {os.getcwd()}')

            if not executable_path:
                error_msg = '无法获取可执行文件路径'
                logger.error(error_msg)
                return ToolResult(success=False, message=error_msg, error=error_msg)

            # 验证可执行文件是否存在
            if not Path(executable_path).exists():
                error_msg = f'可执行文件不存在: {executable_path}'
                logger.error(error_msg)
                return ToolResult(success=False, message=error_msg, error=error_msg)

            # 直接执行 exe 文件
            cmd = [executable_path]
            if script_path:
                if not Path(script_path).exists():
                    error_msg = f'脚本文件不存在: {script_path}'
                    logger.error(error_msg)
                    return ToolResult(success=False, message=error_msg, error=error_msg)
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
                # 保持参数名不变，不做下划线到中划线的转换
                param_name = key
                if isinstance(value, bool):
                    # 特殊处理：trace 和 perf 参数，false 时添加 --no-trace/--no-perf
                    if param_name == 'trace':
                        if not value:
                            cmd.append('--no-trace')
                    elif param_name == 'perf':
                        if not value:
                            cmd.append('--no-perf')
                    elif value:
                        # 其他 bool 参数，true 时添加参数
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

            # 为 Windows 平台准备环境变量
            env = os.environ.copy()
            if sys.platform == 'win32':
                # 在 Windows 上强制使用 UTF-8 编码
                env['PYTHONIOENCODING'] = 'utf-8'

            # 获取插件配置并作为环境变量传递（键值对形式）
            plugin_config = self.config.get(f'plugins.{plugin_id}.config', {})
            # 将每个配置项作为独立的环境变量传递
            if plugin_config:
                for config_key, config_value in plugin_config.items():
                    # 将配置键转换为环境变量名（大写，下划线分隔）
                    # 格式: KEY
                    env_key = config_key.upper().replace('-', '_')

                    # 将配置值转换为字符串
                    if isinstance(config_value, bool):
                        env_value = 'true' if config_value else 'false'
                    elif config_value is None:
                        env_value = ''
                    else:
                        env_value = str(config_value)
                    env[env_key] = env_value
                    logger.debug(f'设置环境变量: {env_key}={env_value}')

            # 执行命令
            try:
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding='utf-8',
                    errors='replace',  # 使用replace模式处理编码错误
                    cwd=working_dir,
                    bufsize=1,
                    env=env,  # 传递环境变量
                )
            except FileNotFoundError as e:
                error_msg = f'文件未找到错误: {e}. 命令: {" ".join(cmd)}, 工作目录: {working_dir}'
                logger.error(error_msg)
                return ToolResult(success=False, message=error_msg, error=str(e))
            except Exception as e:
                error_msg = f'启动进程失败: {e}. 命令: {" ".join(cmd)}, 工作目录: {working_dir}'
                logger.error(error_msg)
                return ToolResult(success=False, message=error_msg, error=str(e))

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
                elif 'report_dir' in params:
                    output_path = params['report_dir']

                # 如果参数中没有输出路径，尝试从输出中提取
                if not output_path:
                    output_path = self._extract_output_path_from_output(output, working_dir)

                # 将相对路径转换为绝对路径
                if output_path:
                    # 如果是相对路径，相对于工作目录解析
                    path_obj = Path(output_path)
                    if not path_obj.is_absolute():
                        path_obj = Path(working_dir) / path_obj
                    output_path = str(path_obj.resolve())

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

    def _extract_output_path_from_output(self, output: str, working_dir: str) -> Optional[str]:
        """
        从工具输出中提取输出路径

        支持的格式：
        - "Reports will be saved to: /path/to/output"
        - "Output directory: /path/to/output"
        - "输出目录: /path/to/output"
        - "结果保存到: /path/to/output"
        """
        # 定义匹配模式
        patterns = [
            r'Reports will be saved to:\s*(.+)',
            r'Output (?:directory|path):\s*(.+)',
            r'输出(?:目录|路径):\s*(.+)',
            r'结果保存到:\s*(.+)',
            r'保存(?:到|至):\s*(.+)',
        ]

        for pattern in patterns:
            match = re.search(pattern, output, re.IGNORECASE | re.MULTILINE)
            if match:
                path = match.group(1).strip()
                # 移除可能的引号
                path = path.strip('"\'')
                logger.info(f'从输出中提取到路径: {path}')
                return path

        return None

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
