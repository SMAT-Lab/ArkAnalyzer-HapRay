import argparse
import os
import re
import sys
import time
import shutil
from concurrent.futures import ThreadPoolExecutor
from typing import List
import logging
from logging.handlers import RotatingFileHandler

from xdevice.__main__ import main_process
from hapray.core.common.ExcelUtils import create_summary_excel
from hapray.core.config.config import Config
from hapray.core.common.CommonUtils import CommonUtils
from hapray.core.common.FolderUtils import scan_folders, delete_folder
from hapray.core.report import ReportGenerator
from hapray.optimization_detector.optimization_detector import OptimizationDetector

ENV_ERR_STR = """
The hdc or node command is not in PATH. 
Please Download Command Line Tools for HarmonyOS(https://developer.huawei.com/consumer/cn/download/), 
then add the following directories to PATH.
    $command_line_tools/tool/node/ (for Windows)
    $command_line_tools/tool/node/bin (for Mac/Linux)
    $command_line_tools/sdk/default/openharmony/toolchains (for ALL)
"""
VERSION = '1.0.1'


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
        self._load_config()
        configure_logging('HapRay.log')
        
        actions = ["perf", "opt", "update"]
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
        action_args = []
        if len(sys.argv[1:2]) > 0 and sys.argv[1:2][0] not in actions:
            action_args.append('perf')
            sub_args = sys.argv[1:]
        else:
            action_args = sys.argv[1:2]
            sub_args = sys.argv[2:]
        args = parser.parse_args(action_args)
        # dispatch function with same name of the action
        getattr(self, args.action)(sub_args)

    def _load_config(self):
        root_path = os.getcwd()
        config_path = os.path.join(root_path, 'config.yaml')
        Config(config_path)

    @staticmethod
    def get_matched_cases(run_testcases: List[str], all_testcases: dict) -> List[str]:
        matched_cases = []
        for pattern in run_testcases:
            try:
                regex = re.compile(pattern)
                for case_name in all_testcases.keys():
                    if regex.match(case_name):
                        matched_cases.append(case_name)
            except re.error as e:
                logging.error(f"Invalid regex pattern: {pattern}, error: {e}")
                # 如果正则表达式无效，尝试作为普通字符串匹配
                if pattern in all_testcases:
                    matched_cases.append(pattern)
        return matched_cases

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
        parser.add_argument('--circles', action="store_true", help="Enable sample cpu circles")
        args = parser.parse_args(args)

        root_path = os.getcwd()
        reports_path = os.path.join(root_path, 'reports', time.strftime('%Y%m%d%H%M%S', time.localtime(time.time())))
        if not os.path.exists(reports_path):
            os.makedirs(reports_path)
        configure_logging(os.path.join(reports_path, 'HapRay.log'))

        if args.run_testcases is not None:
            Config.set('run_testcases', args.run_testcases)

        if args.circles:
            Config.set('hiperf.event', 'raw-cpu-cycles')

        all_testcases = CommonUtils.load_all_testcases()

        if args.run_testcases is not None:
            Config.set('run_testcases', args.run_testcases)

        if args.so_dir is not None:
            Config.set('so_dir', args.so_dir)

        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = []
            report_generator = ReportGenerator()
            run_testcases = Config.get('run_testcases', [])
            if len(run_testcases) == 0:
                logging.error('no run_testcases')
                return

            matched_cases = HapRayCmd.get_matched_cases(run_testcases, all_testcases)
            if not matched_cases:
                logging.error('No test cases matched the inputs.')
                return
            else:
                logging.info('Fond %s test cases to run', len(matched_cases))

            so_dir = Config.get('so_dir', None)
            if so_dir is not None:
                so_dir = os.path.abspath(args.so_dir)

            for case_name in matched_cases:
                scene_round_dirs = []
                for _round in range(5):
                    case_dir = all_testcases[case_name]
                    output = os.path.abspath(os.path.join(reports_path, f'{case_name}_round{_round}'))
                    main_process(f'run -l {case_name} -tcpath {case_dir} -rp {output}')
                    for i in range(5):
                        if scan_folders(output):
                            scene_round_dirs.append(output)
                            break
                        else:
                            if delete_folder(output):
                                logging.info('perf.data文件不全重试第' + str(i) + '次' + output)
                                main_process(f'run -l {case_name} -tcpath {case_dir} -rp {output}')

                merge_folder_path = os.path.abspath(os.path.join(reports_path, case_name))
                # 生成 HapRay 报告
                future = executor.submit(
                    report_generator.generate_report,
                    list(scene_round_dirs),
                    merge_folder_path,
                    so_dir)
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
        parser.add_argument("--jobs", "-j", type=int, default=1,
                            help="Number of parallel jobs (default: 1)")
        args = parser.parse_args(args)

        detector = OptimizationDetector(args.jobs)
        detector.detect_optimization(args.input, args.output)

    @staticmethod
    def update(args):
        parser = argparse.ArgumentParser(
            description='%(prog)s: Update existing performance report',
            prog='ArkAnalyzer-HapRay update')
        parser.add_argument('--report_dir', '-i', required=True, help='Directory containing the reports to update')
        parser.add_argument('--so_dir', default=None, help='Directory to load symbolicated .so files')
        args = parser.parse_args(args)

        report_dir = os.path.abspath(args.report_dir)
        so_dir = None if args.so_dir is None else os.path.abspath(args.so_dir)

        # 验证报告目录是否存在
        if not os.path.exists(report_dir):
            logging.error(f"Report directory not found: {report_dir}")
            return

        # 配置日志
        logging.info(f"Updating reports in: {report_dir}")
        logging.info(f"Using SO directory: {so_dir if so_dir else 'None'}")

        # 扫描报告目录中的所有测试用例目录
        testcase_dirs = []
        regex = re.compile(r'.*_round\d$')
        for entry in os.listdir(report_dir):
            if regex.match(entry):
                continue
            full_path = os.path.join(report_dir, entry)
            if os.path.isdir(full_path):
                # 检查是否包含报告目录结构
                if os.path.exists(os.path.join(full_path, 'hiperf')) and \
                        os.path.exists(os.path.join(full_path, 'htrace')):
                    testcase_dirs.append(full_path)
        
        if not testcase_dirs:
            if os.path.exists(os.path.join(report_dir, 'hiperf')) and \
                     os.path.exists(os.path.join(report_dir, 'htrace')):
                testcase_dirs.append(report_dir)

        if not testcase_dirs:
            logging.error("No valid test case reports found in the directory")
            return

        logging.info(f"Found {len(testcase_dirs)} test case reports to update")

        # 使用线程池并行处理报告更新
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = []
            report_generator = ReportGenerator()
            for case_dir in testcase_dirs:
                # 获取场景名称（目录名）
                scene_name = os.path.basename(case_dir)
                logging.info(f"Updating report for {scene_name}")

                future = executor.submit(lambda: report_generator.update_report(case_dir, so_dir))
                futures.append(future)

            # 等待所有报告更新完成
            for future in futures:
                try:
                    if future.result():
                        logging.info("Report updated successfully")
                    else:
                        logging.error("Failed to update report")
                except Exception as e:
                    logging.error(f"Error updating report: {str(e)}")

        # 重新生成汇总Excel
        logging.info("Creating summary excel...")
        if create_summary_excel(report_dir):
            logging.info("Summary excel created successfully")
        else:
            logging.error("Failed to create summary excel")


if __name__ == "__main__":
    HapRayCmd()
