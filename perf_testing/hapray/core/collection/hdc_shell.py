"""
Copyright (c) 2025 Huawei Device Co., Ltd.
Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You obtain a copy of the License at

 http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

import contextlib
import fcntl
import os
import subprocess
import threading
import time
from typing import Optional

# 常量定义
DEFAULT_HDC_PATH = 'hdc'
PROCESS_TERMINATE_WAIT_SECONDS = 1.0
PROCESS_TERMINATE_CHECK_INTERVAL = 0.1
PROCESS_WAIT_TIMEOUT = 2
OUTPUT_READ_TIMEOUT = 0.1
OUTPUT_READ_INTERVAL = 0.01
PROCESS_FINAL_WAIT_TIMEOUT = 5


class HDCShell:
    """HDC Shell 控制台模拟器 - 支持长时间任务和中断

    用于执行长时间运行的 HDC shell 命令，支持实时输出监控和进程控制。
    """

    def __init__(self, hdc_path: str = DEFAULT_HDC_PATH, device_id: Optional[str] = None):
        """
        初始化 HDC Shell

        Args:
            hdc_path: HDC工具路径，默认为 'hdc'
            device_id: 设备ID，如果指定则使用 -t 参数连接指定设备
        """
        self.hdc_path = hdc_path
        self.device_id = device_id
        self.current_process: Optional[subprocess.Popen] = None

    def execute_long_running_shell(self, shell_command: str, timeout: Optional[int] = None) -> str:
        """
        执行长时间运行的shell命令

        Args:
            shell_command: shell命令字符串
            timeout: 超时时间（秒），None 表示不超时

        Returns:
            命令输出
        """
        return self._execute_long_running_command(['shell', shell_command], timeout)

    def stop_long_running_command(self) -> bool:
        """
        停止正在运行的长时间命令

        先尝试优雅终止（SIGTERM），如果进程未响应则强制终止（SIGKILL）

        Returns:
            是否成功停止
        """
        # 保存进程引用，避免在操作过程中被设置为 None
        process = self.current_process
        if process is None:
            return False

        try:
            # 检查进程是否还在运行
            if process.poll() is None:
                # 先尝试优雅终止
                process.terminate()

                # 等待进程响应
                wait_count = int(PROCESS_TERMINATE_WAIT_SECONDS / PROCESS_TERMINATE_CHECK_INTERVAL)
                for _ in range(wait_count):
                    if process.poll() is not None:
                        break
                    time.sleep(PROCESS_TERMINATE_CHECK_INTERVAL)

                # 如果进程还在运行，强制终止
                if process.poll() is None:
                    process.kill()
                    print('本地进程未响应，已强制终止', flush=True)
                else:
                    print('本地进程已停止', flush=True)

                # 等待进程完全结束
                with contextlib.suppress(subprocess.TimeoutExpired):
                    process.wait(timeout=PROCESS_WAIT_TIMEOUT)

                return True
            # 进程已经结束
            print('本地进程已经结束', flush=True)
            return True

        except Exception as e:
            print(f'停止本地进程时出错: {e}', flush=True)
            return False
        finally:
            # 清理进程引用（只有在当前引用仍然匹配时才清理）
            if self.current_process is process:
                self.current_process = None

    def is_command_running(self) -> bool:
        """
        检查是否有命令正在运行

        Returns:
            是否有命令正在运行
        """
        # 检查本地进程
        if self.current_process is not None:
            try:
                if self.current_process.poll() is None:
                    return True
            except Exception:
                pass

        # 检查设备上的进程
        return self._check_device_process_running()

    def _build_command(self, args: list[str]) -> list[str]:
        """
        构建完整的 HDC 命令

        Args:
            args: 命令参数列表

        Returns:
            完整的命令列表
        """
        cmd = [self.hdc_path]
        if self.device_id:
            cmd.extend(['-t', self.device_id])
        cmd.extend(args)
        return cmd

    def _setup_non_blocking_io(self, file_descriptor) -> None:
        """
        设置文件描述符为非阻塞模式

        Args:
            file_descriptor: 文件描述符
        """
        try:
            flags = fcntl.fcntl(file_descriptor, fcntl.F_GETFL)
            fcntl.fcntl(file_descriptor, fcntl.F_SETFL, flags | os.O_NONBLOCK)
        except (OSError, AttributeError):
            # Windows 或某些系统可能不支持 fcntl
            pass

    def _read_remaining_output(self, process: subprocess.Popen) -> str:
        """
        读取进程的剩余输出

        Args:
            process: 进程对象

        Returns:
            剩余输出内容
        """
        try:
            if process.stdout:
                remaining_output = process.stdout.read()
                return remaining_output if remaining_output else ''
        except OSError:
            pass
        return ''

    def _handle_process_timeout(self, process: subprocess.Popen, timeout: int) -> None:
        """
        处理进程超时

        Args:
            process: 进程对象
            timeout: 超时时间（秒）
        """
        print(f'\n命令执行超时 ({timeout}秒)', flush=True)
        self._terminate_process(process, force_if_needed=True)

    def _terminate_process(self, process: subprocess.Popen, force_if_needed: bool = False) -> None:
        """
        终止进程

        Args:
            process: 进程对象
            force_if_needed: 如果进程未响应是否强制终止
        """
        if process.poll() is not None:
            return  # 进程已经结束

        try:
            process.terminate()
            if force_if_needed:
                time.sleep(0.5)
                if process.poll() is None:
                    process.kill()
        except (OSError, ProcessLookupError):
            # 进程可能已经结束
            pass

    def _wait_for_process_completion(self, process: subprocess.Popen) -> None:
        """
        等待进程完成

        Args:
            process: 进程对象
        """
        if process.poll() is None:
            with contextlib.suppress(subprocess.TimeoutExpired):
                process.wait(timeout=PROCESS_FINAL_WAIT_TIMEOUT)

    def _read_single_output_line(self, process: subprocess.Popen) -> Optional[str]:
        """
        读取单行输出

        Args:
            process: 进程对象

        Returns:
            输出行，如果没有输出则返回 None
        """
        try:
            if process.stdout:
                line = process.stdout.readline()
                return line if line else None
        except OSError:
            pass
        return None

    def _execute_long_running_command(self, args: list[str], timeout: Optional[int] = None) -> str:
        """
        执行长时间运行的命令，支持实时输出和中断

        Args:
            args: 命令参数列表
            timeout: 超时时间（秒），None 表示不超时

        Returns:
            命令输出
        """
        output_lines = []

        try:
            # 构建完整命令
            cmd = self._build_command(args)
            print(f'执行命令: {" ".join(cmd)}', flush=True)
            print('按 Ctrl+C 中断命令\n', flush=True)

            # 启动进程
            self.current_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,  # 将stderr合并到stdout
                text=True,
                bufsize=1,
                universal_newlines=True,
                shell=False,
            )

            # 设置非阻塞读取
            if self.current_process.stdout:
                self._setup_non_blocking_io(self.current_process.stdout)

            # 实时读取输出
            start_time = time.time()
            last_output_time = time.time()

            while True:
                # 检查进程是否结束
                return_code = self.current_process.poll()
                if return_code is not None:
                    # 读取剩余输出
                    remaining = self._read_remaining_output(self.current_process)
                    if remaining:
                        print(remaining, end='', flush=True)
                        output_lines.append(remaining)
                    break

                # 检查超时
                if timeout and (time.time() - start_time) > timeout:
                    self._handle_process_timeout(self.current_process, timeout)
                    break

                # 读取单行输出
                line = self._read_single_output_line(self.current_process)
                if line:
                    print(line, end='', flush=True)
                    output_lines.append(line)
                    last_output_time = time.time()
                # 如果没有输出，稍微等待一下
                elif time.time() - last_output_time > OUTPUT_READ_TIMEOUT:
                    time.sleep(OUTPUT_READ_INTERVAL)

            # 等待进程完全结束
            self._wait_for_process_completion(self.current_process)

            return ''.join(output_lines)

        except KeyboardInterrupt:
            print('\n命令被用户中断', flush=True)
            if self.current_process:
                self._terminate_process(self.current_process)
            return '命令被用户中断'

        except Exception as e:
            error_msg = f'命令执行错误: {e}'
            print(error_msg, flush=True)
            return error_msg

        finally:
            self.current_process = None

    def _check_device_process_running(self) -> bool:
        """
        检查设备上的 hiprofiler_cmd 进程是否正在运行

        Returns:
            设备上是否有 hiprofiler_cmd 进程在运行
        """
        try:
            find_cmd = self._build_command(['shell', 'ps -ef | grep hiprofiler_cmd | grep -v grep'])
            result = subprocess.run(find_cmd, capture_output=True, text=True, timeout=5, check=False)

            if result.returncode == 0 and result.stdout.strip():
                # 检查输出中是否真的包含 hiprofiler_cmd（排除 grep 命令本身）
                for line in result.stdout.strip().split('\n'):
                    if 'hiprofiler_cmd' in line and 'grep' not in line:
                        return True
        except Exception:
            pass

        return False


# 使用示例
def main():
    """使用示例"""
    shell = HDCShell()

    print('=== HDC Shell 控制台示例 ===\n')
    # 示例1: 在后台线程中执行命令，然后手动停止
    print('\n1. 在后台执行命令并手动停止:')

    def run_command():
        output = shell.execute_long_running_shell(
            'hiprofiler_cmd -o /data/local/tmp/hiprofiler_data1.htrace -t 10 -s -k --config /data/local/tmp/hiprofiler_cmd_config.txt',
            timeout=130,
        )
        print(f'命令输出: {output}')

    thread = threading.Thread(target=run_command, daemon=True)
    thread.start()

    # 等待60秒后停止命令
    time.sleep(60)
    print('\n5秒后停止命令...')
    if shell.is_command_running():
        shell.stop_long_running_command()
        print('命令已停止')
    else:
        print('没有正在运行的命令')

    print('\n程序结束')


if __name__ == '__main__':
    main()
