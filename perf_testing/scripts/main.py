import argparse
import os
import re
import sys
import time
import shutil
import functools
from concurrent.futures import ThreadPoolExecutor
import logging
from logging.handlers import RotatingFileHandler

import yaml
from xdevice.__main__ import main_process
from hapray.core.PerfTestCase import PerfTestCase
from hapray.core.common.ExcelUtils import create_summary_excel
from hapray.core.config.config import Config, ConfigError
from hapray.core.common.CommonUtils import CommonUtils
from hapray.core.common.FolderUtils import scan_folders, delete_folder
from hapray.core.common.FrameAnalyzer import FrameAnalyzer
from hapray.optimization_detector.optimization_detector import OptimizationDetector

ENV_ERR_STR = """
The hdc or node command is not in PATH. 
Please Download Command Line Tools for HarmonyOS(https://developer.huawei.com/consumer/cn/download/), 
then add the following directories to PATH.
    $command_line_tools/tool/node/ (for Windows)
    $command_line_tools/tool/node/bin (for Mac/Linux)
    $command_line_tools/sdk/default/openharmony/toolchains (for ALL)
"""
VERSION = '1.0.0'


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


class HapRayCmd:
    def __init__(self):
        actions = ["perf", "opt"]
        actions_desc = " | ".join(actions)
        parser = argparse.ArgumentParser(
            description="Code-oriented Performance Analysis for OpenHarmony Apps",
            usage=f"{sys.argv[0]} [action] [<args>]\nActions: {actions_desc}",
            add_help=False)

        parser.add_argument("action",
                            choices=actions,
                            nargs='?',
                            default="perf",
                            help="Action to perform (perf: performance testing, opt: so optimization detection)")
        args = parser.parse_args(sys.argv[1:2])
        # dispatch function with same name of the action
        getattr(self, args.action)(sys.argv[2:])
    
    @staticmethod
    def perf(args):
        if not check_env():
            logging.error(ENV_ERR_STR)
            return

        parser = argparse.ArgumentParser(
            description='%(prog)s: Code-oriented Performance Analysis for OpenHarmony Apps',
            prog='ArkAnalyzer-HapRay')
        parser.add_argument(
            '-v', '--version',
            action='version',
            version=f'%(prog)s {VERSION}',
            help="Show program's version number and exit"
        )
        parser.add_argument('--so_dir', default=None, help='Directory to load symbolicated .so files')
        parser.add_argument('--run_testcases', nargs='+', default=None, help='Specify test cases to run')
        args = parser.parse_args(args)

        root_path = os.getcwd()
        reports_path = os.path.join(root_path, 'reports', time.strftime('%Y%m%d%H%M%S', time.localtime(time.time())))
        if not os.path.exists(reports_path):
            os.makedirs(reports_path)
        configure_logging(os.path.join(reports_path, 'HapRay.log'))

        if args.run_testcases is not None:
            Config.set('run_testcases', args.run_testcases)

        all_testcases = CommonUtils.load_all_testcases()
        config_path = os.path.join(root_path, 'config.yaml')
        if os.path.exists(config_path):
            _ = Config(config_path)

        if args.run_testcases is not None:
            Config.set('run_testcases', args.run_testcases)

        if args.so_dir is not None:
            Config.set('so_dir', args.so_dir)
   
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = []
            run_testcases = Config.get('run_testcases', [])
            if len(run_testcases) == 0:
                logging.error('no run_testcases')

            for case_name in run_testcases:
                if case_name not in all_testcases:
                    continue
                so_dir = Config.get('so_dir', None)
                scene_round_dirs = []
                for round in range(5):
                    case_dir = all_testcases[case_name]
                    output = os.path.join(reports_path, f'{case_name}_round{round}')
                    main_process(f'run -l {case_name} -tcpath {case_dir} -rp {output}')
                    for i in range(5):
                        if scan_folders(output):
                            scene_round_dirs.append(output)
                            break
                        else:
                            if delete_folder(output):
                                logging.info('perf.data文件不全重试第' + str(i) + '次' + output)
                                main_process(f'run -l {case_name} -tcpath {case_dir} -rp {output}')

                merge_folder_path = os.path.join(reports_path, case_name)
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

            # 生成汇总excel
            logging.info(f"Starting create summary excel ...")
            if create_summary_excel(reports_path):
                logging.info(f"Successfully  create summary excel")
            else:
                logging.error(f"Failed to  create summary excel ")

    @staticmethod
    def opt(args):
        # Your implementation here
        logging.info(f"Running optimization detector with args:{' '.join(args)}")
        parser = argparse.ArgumentParser(description="Analyze binary files for optimization flags")
        parser.add_argument("--input", "-i", help="Directory containing binary files to analyze")
        parser.add_argument("--output", "-o", default="binary_analysis_report.xlsx",
                            help="Output Excel file path(default: binary_analysis_report.xlsx)")
        parser.add_argument("--checkpoint", default="analysis_checkpoint.json",
                            help="Checkpoint file for resumable analysis (default: analysis_checkpoint.json)")
        parser.add_argument("--jobs", "-j", type=int, default=1,
                            help="Number of parallel jobs (default: 1)")
        args = parser.parse_args(args)

        detector = OptimizationDetector(args.jobs)
        detector.detect_optimization(args.input, args.output, args.checkpoint)


if __name__ == "__main__":
    configure_logging('HapRay.log')
    HapRayCmd()
