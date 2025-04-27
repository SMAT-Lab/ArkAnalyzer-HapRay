import os
import time
from xdevice.__main__ import main_process

from aw.config.config import Config


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

    testcases = load_all_testcases()
    with open(os.path.join(root_path, 'testcase.txt')) as file:
        for line in file:
            case_name = line.strip()
            if not testcases[case_name]:
                continue
            for round in range(5):
                case_dir = testcases[case_name]
                output = os.path.join(reports_path, time_str, f'{case_name}_round{round}')
                main_process(f'run -l {case_name} -tcpath {case_dir} -rp {output}')


if __name__ == "__main__":
    main()
