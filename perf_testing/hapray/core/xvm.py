import os
import logging
import threading

from hapray.core.common import CommonUtils
from hapray.core.config.config import Config


class XVM:
    def __init__(self, testcase):
        self.testcase = testcase
        self.driver = self.testcase.driver
        self.trace_thread = None
        self.trace_complete = threading.Event()

    def start_trace(self, duration: int = 5):
        if not Config.get('xvm.symbols', []):
            return

        self.install_xvm()

        # start trace in background thread
        self.trace_func_calls(duration, Config.get('xvm.symbols'))
        self.trace_complete.clear()  # Reset completion flag

    def stop_trace(self, perf_step_dir: str):
        if not Config.get('xvm.symbols', []) or not self.trace_thread:
            return

        # Wait for trace thread to complete with timeout
        self.trace_thread.join(timeout=Config.get('xvm.duration', 5) + 2)
        if self.trace_thread.is_alive():
            logging.warning("XVM trace thread did not complete within timeout")
        # Save results only if thread completed successfully
        self.save_xvm_result(os.path.join(perf_step_dir, 'xvmtrace_result.txt'))
        self.trace_thread = None

    def install_xvm(self):
        if self._has_install_xvm():
            return
        local_path = os.path.join(CommonUtils.get_project_root(), 'hapray-toolbox/third-party/xvm')
        self.driver.push_file(local_path, f'/data/app/el1/bundle/public/{self.testcase.app_package}')
        self.driver.shell(f'chmod +x /data/app/el1/bundle/public/{self.testcase.app_package}/xvm/bin/*')

    def trace_func_calls(self, duration: int, symbols: list, output_file='xvmtrace_result.txt'):
        symbols_arg = ' '.join(symbols)
        output_arg = f'/data/storage/el1/bundle/xvm/{output_file}'
        xvm_cmd = f'/data/storage/el1/bundle/xvm/bin/xvmtrace_hapray -d {duration} -o {output_arg} {symbols_arg}'
        pid = self.testcase.get_app_process_id()

        # Create thread for non-blocking execution
        def run_trace():
            try:
                cmd = f'nsenter -t {pid} -m -- {xvm_cmd}'
                logging.info("Starting XVM trace with command: %s", cmd)
                trace_output = self.driver.shell(cmd)
                logging.info("XVM trace completed. Output: %s", trace_output)
            except Exception as e:
                logging.error("XVM trace thread failed: %s", str(e))
            finally:
                self.trace_complete.set()

        self.trace_thread = threading.Thread(target=run_trace, name="XvmTracer")
        self.trace_thread.daemon = True
        self.trace_thread.start()

    def save_xvm_result(self, local_path: str, output_file='xvmtrace_result.txt'):
        remote_path = f'/data/app/el1/bundle/public/{self.testcase.app_package}/xvm/{output_file}'
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        self.driver.pull_file(remote_path, local_path)
        logging.info("Saved XVM trace result to %s", local_path)

    def _has_install_xvm(self) -> bool:
        xvm_root = f'/data/app/el1/bundle/public/{self.testcase.app_package}/xvm'
        return self.driver.has_file(xvm_root)
