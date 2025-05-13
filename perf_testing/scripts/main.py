import os
import time

import yaml
from xdevice.__main__ import main_process

from hapray.core.PerfTestCase import PerfTestCase
from hapray.core.config.config import Config, ConfigError
from hapray.core.common.CommonUtils import CommonUtils
from scripts.merge_folders import merge_folders


def main():
    _ = Config()
    root_path = os.getcwd()
    reports_path = os.path.join(root_path, 'reports')
    time_str = time.strftime('%Y%m%d%H%M%S', time.localtime(time.time()))

    all_testcases = CommonUtils.load_all_testcases()
    config_path = os.path.join(root_path, '../', 'config.yaml')
    scene_round_dirs = []
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            raw_data = yaml.safe_load(f)
            for case_name in raw_data['run_testcases']:
                if case_name not in all_testcases:
                    continue
                for round in range(5):
                    case_dir = all_testcases[case_name]
                    output = os.path.join(reports_path, time_str, f'{case_name}_round{round}')
                    main_process(f'run -l {case_name} -tcpath {case_dir} -rp {output}')
                    scene_round_dirs.append(output)
                merge_folder_path = os.path.join(reports_path, time_str, case_name)
                merge_folders(scene_round_dirs, merge_folder_path)
                # 生成 HapRay 报告
                PerfTestCase._generate_hapray_report(scene_round_dirs, merge_folder_path)
                scene_round_dirs.clear()
    except FileNotFoundError:
        raise ConfigError(f"not found file: {config_path}")
    except yaml.YAMLError as e:
        raise ConfigError(f"YAML parse error: {str(e)}")


if __name__ == "__main__":
    main()
