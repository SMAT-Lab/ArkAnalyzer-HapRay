import argparse
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor

import yaml
from xdevice.__main__ import main_process

from hapray.core.PerfTestCase import PerfTestCase
from hapray.core.config.config import Config, ConfigError
from hapray.core.common.CommonUtils import CommonUtils
from hapray.core.common.FolderUtils import merge_folders, scan_folders, delete_folder


def main():
    parser = argparse.ArgumentParser(description='处理命令行参数')
    parser.add_argument('--so_dir', default=None, help='debug包中的so文件存放目录')
    parser.add_argument('--run_testcases', nargs='+', default=None, help='指定要测试的用例')
    args = parser.parse_args()

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
                run_testcases = raw_data['run_testcases']
                if args.run_testcases is not None:
                    if run_testcases is not None:
                        run_testcases = args.run_testcases + run_testcases
                    else:
                        run_testcases = args.run_testcases
                for case_name in run_testcases:
                    if case_name not in all_testcases:
                        continue
                    so_dir_key = re.sub(r'_[^_]*$', '', case_name)
                    if so_dir_key in raw_data['so_dir']:
                        so_dir = raw_data['so_dir'][so_dir_key][0]
                    else:
                        so_dir = None
                    if args.so_dir is not None:
                        so_dir = args.so_dir
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
                        so_dir  # debug包中的so文件存放地址
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
