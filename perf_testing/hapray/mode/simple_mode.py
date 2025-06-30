import os
import json
import logging
import re
import glob
import shutil
import sqlite3

import pandas as pd

from hapray.core.common.exe_utils import ExeUtils


def create_simple_mode_structure(report_dir, perf_path, trace_path, package_name, pids):
    """
    SIMPLE模式下创建目录结构、testInfo.json、pids.json、steps.json
    """
    # 检查输入文件是否存在
    if not os.path.exists(perf_path):
        raise FileNotFoundError(f"Performance data file not found: {perf_path}")
    if not os.path.exists(trace_path):
        raise FileNotFoundError(f"Trace file not found: {trace_path}")

    hiperf_dir = os.path.join(report_dir, "hiperf", "step1")
    htrace_dir = os.path.join(report_dir, "htrace", "step1")
    report_report_dir = os.path.join(report_dir, "report")
    target_db_file = None

    if (
            not os.path.exists(hiperf_dir)
            and not os.path.exists(htrace_dir)
            and not os.path.exists(report_report_dir)
    ):
        os.makedirs(hiperf_dir)
        os.makedirs(htrace_dir)
        os.makedirs(report_report_dir)
        logging.info(
            "hiperf htrace report directory create success: %s and %s and %s", hiperf_dir, htrace_dir, report_dir
        )

        # 查找并移动ps_ef.txt文件到hiperf/step1/目录
        ps_ef_files = glob.glob(os.path.join(os.path.dirname(perf_path), "ps_ef.txt"))
        if ps_ef_files:
            source_ps_ef_file = ps_ef_files[0]
            target_ps_ef_file = os.path.join(hiperf_dir, "ps_ef.txt")
            shutil.copy2(source_ps_ef_file, target_ps_ef_file)
            logging.info("Copied %s to %s", source_ps_ef_file, target_ps_ef_file)

        # 查找并移动.htrace文件到htrace/step1/目录，重命名为trace.htrace

        source_htrace_file = trace_path
        target_htrace_file = os.path.join(htrace_dir, "trace.htrace")
        shutil.copy2(source_htrace_file, target_htrace_file)
        logging.info("Copied %s to %s", source_htrace_file, target_htrace_file)

        # 创建testInfo.json
        test_info = {
            "app_id": package_name,
            "app_name": "",
            "app_version": "",
            "scene": "",
            "device": {
                "sn": "",
                "model": "",
                "type": "",
                "platform": "HarmonyOS NEXT",
                "version": "",
                "others": {},
            },
            "timestamp": 0,
        }
        with open(os.path.join(report_dir, "testInfo.json"), "w", encoding="utf-8") as f:
            json.dump(test_info, f)
        logging.info(
            "testInfo.json create success: %s", os.path.join(report_dir, 'testInfo.json')
        )
        # 创建steps.json
        steps_json = [
            {
                "name": "step1",
                "description": "1.临时步骤1",
                "stepIdx": 1
            }
        ]
        with open(os.path.join(report_dir, "hiperf", "steps.json"), "w", encoding="utf-8") as f:
            json.dump(steps_json, f)
        logging.info(
            "steps.json create success: %s", os.path.join(hiperf_dir, 'steps.json')
        )
    if os.path.exists(perf_path):
        # 查找并移动.data文件到hiperf/step1/目录，重命名为perf.data
        source_data_file = perf_path
        target_data_file = os.path.join(hiperf_dir, "perf.data")
        shutil.copy2(source_data_file, target_data_file)
        logging.info("Copied %s to %s", source_data_file, target_data_file)
        target_db_file = target_data_file.replace(".data", ".db")
        if not os.path.exists(target_db_file) and os.path.exists(target_data_file):
            if not ExeUtils.convert_data_to_db(target_data_file, target_db_file):
                logging.error("Failed to convert perf to db for %s", target_data_file)
    # 创建pids.json
    pids_json = parse_processes(
        target_db_file or "", os.path.join(hiperf_dir, "ps_ef.txt"), package_name, pids
    )
    with open(os.path.join(hiperf_dir, "pids.json"), "w", encoding="utf-8") as f:
        json.dump(pids_json, f)
    logging.info(
        "pids.json create success: %s", os.path.join(report_dir, 'pids.json')
    )


def parse_processes(target_db_file: str, file_path: str, package_name: str, pids: list):
    """
    解析进程文件，返回包含目标包名的进程pid和进程名列表。
    :param target_db_file: 性能数据库文件路径
    :param file_path: 进程信息文件路径
    :param package_name: 目标包名
    :param pids: 用户提供的进程ID列表
    :return: dict { 'pids': List[int], 'process_names': List[str] }
    """
    if not package_name:
        raise ValueError("包名不能为空")
    result = {"pids": [], "process_names": []}
    if os.path.exists(target_db_file) and target_db_file:
        # 连接trace数据库
        perf_conn = sqlite3.connect(target_db_file)
        try:
            # 获取所有perf样本
            perf_query = "SELECT DISTINCT process_id, thread_name FROM perf_thread WHERE thread_name LIKE ?"
            params = (f"%{package_name}%",)
            perf_pids = pd.read_sql_query(perf_query, perf_conn, params=params)
            for _, row in perf_pids.iterrows():
                result["pids"].append(row['process_id'])
                result["process_names"].append(row['thread_name'])
        except Exception as e:
            logging.error("从db中获取pids时发生异常: %s", str(e))
        finally:
            perf_conn.close()
    if os.path.exists(file_path):
        result = {"pids": [], "process_names": []}
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                lines = [line.strip() for line in f if line.strip()]
            process_regex = re.compile(
                r"^\s*(\S+)\s+(\d+)\s+(\d+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(.*)$"
            )
            for line in lines[1:]:
                match = process_regex.match(line)
                if not match:
                    continue
                pid = int(match.group(2))
                cmd = match.group(8)
                if package_name in cmd:
                    process_name = cmd[5:] if cmd.startswith("init ") else cmd
                    result["pids"].append(pid)
                    result["process_names"].append(process_name)
        except Exception as err:
            logging.error("处理文件失败: %s", err)
    if pids != []:
        process_names = []
        for pid in pids:
            process_names.append(package_name)
        result["pids"] = pids
        result["process_names"] = process_names

    return result
