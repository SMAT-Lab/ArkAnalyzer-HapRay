import argparse
import os
import re
import sys
import time
import shutil
from concurrent.futures import ThreadPoolExecutor
import logging
from logging.handlers import RotatingFileHandler

import yaml
from xdevice.__main__ import main_process

from hapray.core.PerfTestCase import PerfTestCase
from hapray.core.config.config import Config, ConfigError
from hapray.core.common.CommonUtils import CommonUtils
from hapray.core.common.FolderUtils import scan_folders, delete_folder
from hapray.core.common.FrameAnalyzer import FrameAnalyzer


def configure_logging(log_file='HapRay.log'):
    """配置日志系统，同时输出到控制台和文件"""
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    # 清除现有的处理器
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    # 创建格式化器
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

    # 控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # 文件处理器（如果指定了日志文件）
    file_handler = RotatingFileHandler(
        log_file, mode="a", maxBytes=10 * 1024 * 1024, backupCount=10,
        encoding="UTF-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)


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
        logging.error(ENV_ERR_STR)
        return

    parser = argparse.ArgumentParser(description='处理命令行参数')
    parser.add_argument('--so_dir', default=None, help='debug包中的so文件存放目录')
    parser.add_argument('--run_testcases', nargs='+', default=None, help='指定要测试的用例')
    args = parser.parse_args()

    _ = Config()
    root_path = os.getcwd()
    reports_path = os.path.join(root_path, 'reports')
    if not os.path.exists(reports_path):
        os.makedirs(reports_path)
    configure_logging(os.path.join(reports_path, 'HapRay.log'))

    time_str = time.strftime('%Y%m%d%H%M%S', time.localtime(time.time()))

    all_testcases = CommonUtils.load_all_testcases()
    config_path = os.path.join(root_path, 'config.yaml')

    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            raw_data = yaml.safe_load(f)
            with ThreadPoolExecutor(max_workers=4) as executor:
                futures = []
                run_testcases = raw_data['run_testcases']
                if run_testcases is None:
                    run_testcases = []
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
                                    logging.info('perf.data文件不全重试第' + str(i) + '次' + output)
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

                    # 在所有操作完成后进行卡顿帧分析
                    logging.info(f"Starting frame drops analysis for {case_name}...")
                    if FrameAnalyzer.analyze_frame_drops(merge_folder_path):
                        logging.info(f"Successfully analyzed frame drops for {case_name}")
                    else:
                        logging.error(f"Failed to analyze frame drops for {case_name}")

                # 等待所有报告生成任务完成
                for future in futures:
                    future.result()



    except FileNotFoundError:
        raise ConfigError(f"not found file: {config_path}")
    except yaml.YAMLError as e:
        raise ConfigError(f"YAML parse error: {str(e)}")


if __name__ == "__main__":
    main()
