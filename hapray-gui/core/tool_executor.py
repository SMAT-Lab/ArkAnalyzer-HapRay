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

    def execute_python_tool(
        self,
        tool_name: str,
        script_path: str,
        params: dict[str, Any],
        working_dir: Optional[str] = None,
        callback: Optional[Callable[[str], None]] = None,
    ) -> ToolResult:
        """
        执行Python工具

        Args:
            tool_name: 工具名称
            script_path: Python脚本路径
            params: 参数字典
            working_dir: 工作目录
            callback: 输出回调函数
        """
        try:
            tool_config = self.config.get_tool_config(tool_name)
            python_cmd = tool_config.get('python', 'python')

            # 构建命令
            cmd = [python_cmd, script_path]

            # 特殊处理perf_testing工具，它使用action参数
            if tool_name == '动态测试' and 'action' in params:
                action = params.pop('action')
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

            # 准备环境变量，添加工具目录到 PYTHONPATH
            env = os.environ.copy()
            if working_dir:
                tool_dir = Path(working_dir).resolve()
                pythonpath = env.get('PYTHONPATH', '')
                if pythonpath:
                    env['PYTHONPATH'] = f'{tool_dir}{os.pathsep}{pythonpath}'
                else:
                    env['PYTHONPATH'] = str(tool_dir)

            # 执行命令
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8',
                cwd=working_dir,
                env=env,
                bufsize=1,
            )

            self.running_tasks[tool_name] = process
            if callback:
                self.task_callbacks[tool_name] = callback

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
                            callback(f'ERROR: {line.rstrip()}')

            output_thread = threading.Thread(target=read_output, daemon=True)
            error_thread = threading.Thread(target=read_error, daemon=True)
            output_thread.start()
            error_thread.start()

            # 等待完成
            return_code = process.wait()
            output_thread.join(timeout=1)
            error_thread.join(timeout=1)

            del self.running_tasks[tool_name]
            if tool_name in self.task_callbacks:
                del self.task_callbacks[tool_name]

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

    def execute_exe_tool(
        self,
        tool_name: str,
        exe_path: str,
        params: dict[str, Any],
        working_dir: Optional[str] = None,
        callback: Optional[Callable[[str], None]] = None,
    ) -> ToolResult:
        """
        执行可执行文件工具（PyInstaller 打包的 exe）

        Args:
            tool_name: 工具名称
            exe_path: exe 文件路径
            params: 参数字典
            working_dir: 工作目录
            callback: 输出回调函数
        """
        try:
            # 构建命令（直接执行 exe，不需要 python 解释器）
            cmd = [exe_path]

            # 特殊处理perf_testing工具，它使用action参数
            if tool_name == '动态测试' and 'action' in params:
                action = params.pop('action')
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

            # 执行命令（exe 不需要设置 PYTHONPATH）
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8',
                cwd=working_dir,
                bufsize=1,
            )

            self.running_tasks[tool_name] = process
            if callback:
                self.task_callbacks[tool_name] = callback

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
                            callback(f'ERROR: {line.rstrip()}')

            output_thread = threading.Thread(target=read_output, daemon=True)
            error_thread = threading.Thread(target=read_error, daemon=True)
            output_thread.start()
            error_thread.start()

            # 等待完成
            return_code = process.wait()
            output_thread.join(timeout=1)
            error_thread.join(timeout=1)

            del self.running_tasks[tool_name]
            if tool_name in self.task_callbacks:
                del self.task_callbacks[tool_name]

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

    def execute_node_tool(
        self,
        tool_name: str,
        script_path: str,
        params: dict[str, Any],
        working_dir: Optional[str] = None,
        callback: Optional[Callable[[str], None]] = None,
    ) -> ToolResult:
        """
        执行Node.js工具

        Args:
            tool_name: 工具名称
            script_path: Node.js脚本路径
            params: 参数字典
            working_dir: 工作目录
            callback: 输出回调函数
        """
        try:
            tool_config = self.config.get_tool_config(tool_name)
            node_cmd = tool_config.get('node', 'node')

            # 构建命令 - 静态分析工具使用 hapray 命令格式
            cmd = [node_cmd, script_path]

            # 提取command参数（hap, perf, elf等）
            command = params.pop('command', 'hap')
            cmd.extend(['hapray', command])

            # 添加参数
            for key, value in params.items():
                if value is None or value == '':
                    continue
                # 处理参数名转换
                param_name = key.replace('_', '-')
                if isinstance(value, bool):
                    if value:
                        cmd.append(f'--{param_name}')
                elif isinstance(value, list):
                    cmd.extend([f'--{param_name}'] + [str(v) for v in value])
                else:
                    cmd.extend([f'--{param_name}', str(value)])

            logger.info(f'执行命令: {" ".join(cmd)}')

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

            self.running_tasks[tool_name] = process
            if callback:
                self.task_callbacks[tool_name] = callback

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
                            callback(f'ERROR: {line.rstrip()}')

            output_thread = threading.Thread(target=read_output, daemon=True)
            error_thread = threading.Thread(target=read_error, daemon=True)
            output_thread.start()
            error_thread.start()

            # 等待完成
            return_code = process.wait()
            output_thread.join(timeout=1)
            error_thread.join(timeout=1)

            del self.running_tasks[tool_name]
            if tool_name in self.task_callbacks:
                del self.task_callbacks[tool_name]

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

    def cancel_task(self, tool_name: str) -> bool:
        """取消正在执行的任务"""
        if tool_name in self.running_tasks:
            process = self.running_tasks[tool_name]
            try:
                process.terminate()
                process.wait(timeout=5)
            except (subprocess.TimeoutExpired, ProcessLookupError):
                process.kill()
            del self.running_tasks[tool_name]
            if tool_name in self.task_callbacks:
                del self.task_callbacks[tool_name]
            return True
        return False

    def is_running(self, tool_name: str) -> bool:
        """检查任务是否正在运行"""
        return tool_name in self.running_tasks
