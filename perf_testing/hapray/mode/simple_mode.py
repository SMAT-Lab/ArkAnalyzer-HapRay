import os
import json
import logging
import re


def create_simple_mode_structure(report_dir, package_name):
    """
    SIMPLE模式下创建目录结构、testInfo.json、pids.json、steps.json
    """
    hiperf_dir = os.path.join(report_dir, "hiperf", "step1")
    htrace_dir = os.path.join(report_dir, "htrace", "step1")
    report_report_dir = os.path.join(report_dir, "report")
    if (
            not os.path.exists(hiperf_dir)
            and not os.path.exists(htrace_dir)
            and not os.path.exists(report_report_dir)
    ):
        os.makedirs(hiperf_dir)
        os.makedirs(htrace_dir)
        os.makedirs(report_report_dir)
        logging.info(
            f"hiperf htrace report directory create success: {hiperf_dir} and {htrace_dir} and {report_dir}"
        )
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
        with open(os.path.join(report_dir, "testInfo.json"), "w") as f:
            json.dump(test_info, f)
        logging.info(
            f"testInfo.json create success: {os.path.join(report_dir, 'testInfo.json')}"
        )
        # 创建steps.json
        steps_json = [
            {
                "name": "step1",
                "description": "1.临时步骤1",
                "stepIdx": 1
            }
        ]
        with open(os.path.join(report_dir, "hiperf", "steps.json"), "w") as f:
            json.dump(steps_json, f)
        logging.info(
            f"steps.json create success: {os.path.join(hiperf_dir, 'steps.json')}"
        )
    # 创建pids.json
    pids_json = parse_processes(
        os.path.join(hiperf_dir, "ps_ef.txt"), package_name
    )
    with open(os.path.join(hiperf_dir, "pids.json"), "w") as f:
        json.dump(pids_json, f)
    logging.info(
        f"pids.json create success: {os.path.join(report_dir, 'pids.json')}"
    )


def parse_processes(file_path: str, package_name: str):
    """
    解析进程文件，返回包含目标包名的进程pid和进程名列表。
    :param file_path: 进程信息文件路径
    :param package_name: 目标包名
    :return: dict { 'pids': List[int], 'process_names': List[str] }
    """
    if not file_path or not package_name:
        raise ValueError("文件路径和包名不能为空")

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip()]

        if len(lines) <= 1:
            return {}

        process_regex = re.compile(
            r"^\s*(\S+)\s+(\d+)\s+(\d+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(.*)$"
        )
        result = {"pids": [], "process_names": []}

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
        return result
    except Exception as err:
        logging.error(f"处理文件失败: {err}")
        return {}
