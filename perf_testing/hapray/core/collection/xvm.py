import logging
import os
import threading

from hapray.core.common import ExeUtils
from hapray.core.config.config import Config


class XVM:
    def __init__(self, driver, app_package: str):
        self.driver = driver
        self.app_package = app_package
        self.trace_thread = None
        self.trace_complete = threading.Event()

    def start_trace(self, duration: int = 5):
        if not Config.get('xvm.symbols', []):
            return

        self._install_xvm()

        # start trace in background thread
        self._trace_func_calls(duration, Config.get('xvm.symbols'))
        self.trace_complete.clear()  # Reset completion flag

    def stop_trace(self, perf_step_dir: str):
        if not Config.get('xvm.symbols', []) or not self.trace_thread:
            return

        # Wait for trace thread to complete with timeout
        self.trace_thread.join(timeout=Config.get('xvm.duration', 5) + 2)
        if self.trace_thread.is_alive():
            logging.warning('XVM trace thread did not complete within timeout')
        # Save results only if thread completed successfully
        self._save_xvm_result(os.path.join(perf_step_dir, 'xvmtrace_result.txt'))
        self.trace_thread = None

    def _install_xvm(self):
        """
        安装 XVM（私有方法）

        Args:
            无
        """
        if self._has_install_xvm():
            return
        local_path = os.path.join(ExeUtils.get_tools_dir('xvm'))
        self.driver.push_file(local_path, f'/data/app/el1/bundle/public/{self.app_package}')
        self.driver.shell(f'chmod +x /data/app/el1/bundle/public/{self.app_package}/xvm/bin/*')

    def _trace_func_calls(self, duration: int, symbols: list, output_file='xvmtrace_result.txt'):
        """
        追踪函数调用（私有方法）

        Args:
            duration: 追踪时长（秒）
            symbols: 要追踪的符号列表
            output_file: 输出文件名
        """
        symbols_arg = ' '.join(symbols)
        output_arg = f'/data/storage/el1/bundle/xvm/{output_file}'
        xvm_cmd = f'/data/storage/el1/bundle/xvm/bin/xvmtrace_hapray -d {duration} -o {output_arg} {symbols_arg}'
        pid = self._get_app_process_id()

        # Create thread for non-blocking execution
        def run_trace():
            try:
                cmd = f'nsenter -t {pid} -m -- {xvm_cmd}'
                logging.info('Starting XVM trace with command: %s', cmd)
                trace_output = self.driver.shell(cmd)
                logging.info('XVM trace completed. Output: %s', trace_output)
            except Exception as e:
                logging.error('XVM trace thread failed: %s', str(e))
            finally:
                self.trace_complete.set()

        self.trace_thread = threading.Thread(target=run_trace, name='XvmTracer')
        self.trace_thread.daemon = True
        self.trace_thread.start()

    def _save_xvm_result(self, local_path: str, output_file='xvmtrace_result.txt'):
        """
        保存 XVM 追踪结果（私有方法）

        Args:
            local_path: 本地保存路径
            output_file: 输出文件名
        """
        remote_path = f'/data/app/el1/bundle/public/{self.app_package}/xvm/{output_file}'
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        if not self.driver.has_file(remote_path):
            logging.warning('Failed to save XVM trace result from %s to %s', remote_path, local_path)
            return

        self.driver.pull_file(remote_path, local_path)
        logging.info('Saved XVM trace result to %s', local_path)

    def _get_app_process_id(self) -> int:
        """获取应用进程ID"""
        result = self.driver.shell(f'pidof {self.app_package}')
        return int(result.strip())

    def _has_install_xvm(self) -> bool:
        xvm_root = f'/data/app/el1/bundle/public/{self.app_package}/xvm'
        return self.driver.has_file(xvm_root)
