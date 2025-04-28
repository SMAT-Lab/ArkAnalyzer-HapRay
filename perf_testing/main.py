import os
import time

import yaml
from xdevice.__main__ import main_process

from aw.config.config import Config, ConfigError


def load_all_testcases() -> dict:
    all_testcases = dict()
    testcases_path = os.path.join(os.path.dirname(__file__), 'testcases')
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


def main():
    _ = Config()
    root_path = os.getcwd()
    reports_path = os.path.join(root_path, 'reports')
    time_str = time.strftime('%Y%m%d%H%M%S', time.localtime(time.time()))

    all_testcases = load_all_testcases()
    config_path = os.path.join(root_path, 'config.yaml')
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
    except FileNotFoundError:
        raise ConfigError(f"not found file: {config_path}")
    except yaml.YAMLError as e:
        raise ConfigError(f"YAML parse error: {str(e)}")


if __name__ == "__main__":
    main()
