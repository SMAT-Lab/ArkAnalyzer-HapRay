import os
import re
import time
import shutil
from concurrent.futures import ThreadPoolExecutor

import yaml
from xdevice.__main__ import main_process

from hapray.core.PerfTestCase import PerfTestCase, Log
from hapray.core.config.config import Config, ConfigError
from hapray.core.common.CommonUtils import CommonUtils
from hapray.core.common.FolderUtils import merge_folders, scan_folders, delete_folder

def check_env() -> bool:
    if shutil.which('hdc') and shutil.which('node'):
        return True
    return False

ENV_ERR_STR = """
The hdc or node command is not in PATH. 
Please Download Command Line Tools for HarmonyOS(https://developer.huawei.com/consumer/cn/download/), 
then add the following directories to PATH.
    $command_line_tools/tool/node/ (for Windows)
    $command_line_tools/tool/node/bin (for Mac/Linux)
    $command_line_tools/sdk/default/openharmony/toolchains (for ALL)
"""

def main():
    if not check_env():
        Log.error(ENV_ERR_STR)
        return
    
    _ = Config()
    root_path = os.getcwd()
    reports_path = os.path.join(root_path, 'reports')
    time_str = time.strftime('%Y%m%d%H%M%S', time.localtime(time.time()))

    all_testcases = CommonUtils.load_all_testcases()
    config_path = os.path.join(root_path, 'config.yaml')

    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            raw_data = yaml.safe_load(f)
            with ThreadPoolExecutor(max_workers=4) as executor:
                futures = []
                for case_name in raw_data['run_testcases']:
                    if case_name not in all_testcases:
                        continue
                    so_path_key = re.sub(r'_[^_]*$', '', case_name)
                    if so_path_key in raw_data['so_path']:
                        so_path = raw_data['so_path'][so_path_key][0]
                    else:
                        so_path = None
                    scene_round_dirs = []
                    for round in range(5):
                        case_dir = all_testcases[case_name]
                        output = os.path.join(reports_path, time_str, f'{case_name}_round{round}')
                        main_process(f'run -l {case_name} -tcpath {case_dir} -rp {output}')
                        for i in range(5):
                            if scan_folders(output):
                                scene_round_dirs.append(output)
                                break
                            else:
                                if delete_folder(output):
                                    print('perf.data文件不全重试第' + str(i) + '次' + output)
                                    main_process(f'run -l {case_name} -tcpath {case_dir} -rp {output}')

                    merge_folder_path = os.path.join(reports_path, time_str, case_name)
                    # 生成 HapRay 报告
                    future = executor.submit(
                        PerfTestCase.generate_hapray_report,
                        list(scene_round_dirs),  # 避免共享变量被修改
                        merge_folder_path,
                        so_path  # debug包中的so文件存放地址
                    )
                    futures.append(future)
                # 等待所有报告生成任务完成
                for future in futures:
                    future.result()

    except FileNotFoundError:
        raise ConfigError(f"not found file: {config_path}")
    except yaml.YAMLError as e:
        raise ConfigError(f"YAML parse error: {str(e)}")


if __name__ == "__main__":
    main()
