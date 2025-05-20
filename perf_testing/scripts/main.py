import os
import time
from concurrent.futures import ThreadPoolExecutor

import yaml
from xdevice.__main__ import main_process

from hapray.core.PerfTestCase import PerfTestCase
from hapray.core.config.config import Config, ConfigError
from hapray.core.common.CommonUtils import CommonUtils
from hapray.core.common.FolderUtils import merge_folders, scan_folders, delete_folder


def main():
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
                                    print('perf.data文件不全重试第'+str(i)+'次'+output)
                                    main_process(f'run -l {case_name} -tcpath {case_dir} -rp {output}')

                    merge_folder_path = os.path.join(reports_path, time_str, case_name)
                    # 生成 HapRay 报告
                    future = executor.submit(
                        PerfTestCase.generate_hapray_report,
                        list(scene_round_dirs),  # 避免共享变量被修改
                        merge_folder_path
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
