# coding: utf-8
import os
import time
import subprocess
from importlib.resources import files
from pathlib import Path

from hypium import UiDriver


class CommonUtils(object):
    def __init__(self):
        pass

    @staticmethod
    def exe(cmd):
        pi = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
        return pi.stdout

    @staticmethod
    def exe_cmd(cmd, timeout=120000):
        ret = 'error'
        try:
            ret = subprocess.check_output(cmd, timeout=timeout, stderr=subprocess.STDOUT, shell=True)
            return ret.decode('gbk', 'ignore').encode('utf-8')
        except subprocess.CalledProcessError as e:
            print(f'cmd->{cmd} excute error output={e.output}')
        except subprocess.TimeoutExpired as e:
            print(f'cmd->{cmd} excute error output={e.output}')
        return ret

    @staticmethod
    def swipes_up_load(driver: UiDriver, swip_num: int, sleep: int, timeout=300):
        for _ in range(swip_num):
            CommonUtils.swipe(driver.device_sn, 630, 1904, 630, 954, timeout)
            time.sleep(sleep)

    @staticmethod
    def swipes_down_load(driver: UiDriver, swip_num: int, sleep: int, timeout=300):
        for _ in range(swip_num):
            CommonUtils.swipe(driver.device_sn, 630, 816, 630, 1766, timeout)
            time.sleep(sleep)

    @staticmethod
    def swipes_left_load(driver: UiDriver, swip_num: int, sleep: int, timeout=300):
        for _ in range(swip_num):
            CommonUtils.swipe(driver.device_sn, 1008, 1360, 504, 1360, timeout)
            time.sleep(sleep)

    @staticmethod
    def swipes_right_load(driver: UiDriver, swip_num: int, sleep: int, timeout=300):
        for _ in range(swip_num):
            CommonUtils.swipe(driver.device_sn, 504, 1360, 1008, 1360, timeout)
            time.sleep(sleep)

    @staticmethod
    def swipe(sn, x1, y1, x2, y2, _time=300):
        CommonUtils.exe_cmd(f'hdc -t {sn} shell uinput -T -m {str(x1)} {str(y1)} {str(x2)} {str(y2)} {str(_time)} ')

    @staticmethod
    def load_all_testcases() -> dict:
        all_testcases = dict()
        testcases_path = files("hapray.testcases")
        for second_dir in os.listdir(testcases_path):
            second_path = os.path.join(testcases_path, second_dir)

            if not os.path.isdir(second_path):
                continue
            for third_file in os.listdir(second_path):
                third_path = os.path.join(second_path, third_file)

                if os.path.isdir(third_path) or not third_file.endswith('.py'):
                    continue
                case_name = os.path.splitext(third_file)[0]
                all_testcases[case_name] = second_path
        return all_testcases

    @staticmethod
    def get_project_root() -> Path:
        """获取项目根目录"""
        return Path(__file__).parent.parent.parent.parent
