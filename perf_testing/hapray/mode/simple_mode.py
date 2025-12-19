import glob
import json
import logging
import os
import re
import shutil
import sqlite3

import pandas as pd

from hapray.core.common.exe_utils import ExeUtils


def create_simple_mode_structure(report_dir, perf_paths, trace_paths, package_name, **kwargs):
    """
    SIMPLE模式下创建目录结构、testInfo.json、pids.json、steps.json
    支持多个perf和trace文件，每个文件对应一个step目录

    注意：memory 数据从 trace.htrace 中获取，不再需要单独的 memory 目录

    Args:
        report_dir: 报告目录
        perf_paths: perf文件路径列表
        trace_paths: trace文件路径列表
        package_name: 包名
        **kwargs: 可选参数
            pids: 进程ID列表，默认为空列表
            steps_file_path: 可选的steps.json文件路径，如果提供则使用该文件
    """
    pids = kwargs.get('pids', [])
    steps_file_path = kwargs.get('steps_file_path', '')

    # 检查输入文件是否存在
    for perf_path in perf_paths:
        if not os.path.exists(perf_path):
            raise FileNotFoundError(f'Performance data file not found: {perf_path}')
    for trace_path in trace_paths:
        if not os.path.exists(trace_path):
            raise FileNotFoundError(f'Trace file not found: {trace_path}')

    # 确保perf和trace文件数量一致，如果trace_paths为空则只使用perf文件数量
    max_files = max(len(perf_paths), len(trace_paths)) if trace_paths else len(perf_paths)

    # 创建基础目录
    report_report_dir = os.path.join(report_dir, 'report')
    target_db_files = []

    # 创建基础目录结构（不再创建 memory 目录）
    hiperf_base_dir = os.path.join(report_dir, 'hiperf')
    htrace_base_dir = os.path.join(report_dir, 'htrace') if trace_paths else None

    _create_base_directories(report_report_dir, hiperf_base_dir, htrace_base_dir)

    # 处理多个文件，每个文件对应一个step目录
    for i in range(max_files):
        step_num = i + 1
        hiperf_step_dir = os.path.join(hiperf_base_dir, f'step{step_num}')

        # 创建step目录
        os.makedirs(hiperf_step_dir, exist_ok=True)

        # 处理perf文件
        if i < len(perf_paths):
            _process_perf_file(perf_paths[i], hiperf_step_dir, target_db_files, package_name, pids)
        else:
            _create_pids_json(None, hiperf_step_dir, package_name, pids)

        # 处理trace文件（仅当提供了trace文件时）
        if trace_paths and i < len(trace_paths):
            htrace_step_dir = os.path.join(htrace_base_dir, f'step{step_num}')
            os.makedirs(htrace_step_dir, exist_ok=True)
            _process_trace_file(trace_paths[i], htrace_step_dir)

        # 创建testInfo.json
        test_info = {
            'app_id': package_name,
            'app_name': '',
            'app_version': '',
            'scene': '',
            'device': {
                'sn': '',
                'model': '',
                'type': '',
                'platform': 'HarmonyOS NEXT',
                'version': '',
                'others': {},
            },
            'timestamp': 0,
        }
        with open(os.path.join(report_dir, 'testInfo.json'), 'w', encoding='utf-8') as f:
            json.dump(test_info, f)
        logging.info('testInfo.json create success: %s', os.path.join(report_dir, 'testInfo.json'))

        # 处理steps.json文件
        target_steps_file = os.path.join(hiperf_base_dir, 'steps.json')
        if steps_file_path and os.path.exists(steps_file_path):
            # 如果提供了steps.json文件路径，则复制该文件
            shutil.copy2(steps_file_path, target_steps_file)
            logging.info('Copied existing steps.json from %s to %s', steps_file_path, target_steps_file)
        else:
            # 否则根据文件数量动态生成步骤
            steps_json = []
            for j in range(max_files):
                step_num = j + 1
                steps_json.append(
                    {'name': f'step{step_num}', 'description': f'{step_num}.临时步骤{step_num}', 'stepIdx': step_num}
                )

            with open(target_steps_file, 'w', encoding='utf-8') as f:
                json.dump(steps_json, f)
            logging.info('Auto-generated steps.json create success: %s', target_steps_file)


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
        raise ValueError('包名不能为空')
    result = {'pids': [], 'process_names': []}
    if target_db_file and os.path.exists(target_db_file):
        # 连接trace数据库
        perf_conn = sqlite3.connect(target_db_file)
        try:
            # 获取所有perf样本
            perf_query = 'SELECT DISTINCT process_id, thread_name FROM perf_thread WHERE thread_name LIKE ?'
            params = (f'%{package_name}%',)
            perf_pids = pd.read_sql_query(perf_query, perf_conn, params=params)
            for _, row in perf_pids.iterrows():
                result['pids'].append(row['process_id'])
                result['process_names'].append(row['thread_name'])
        except Exception as e:
            logging.error('从db中获取pids时发生异常: %s', str(e))
        finally:
            perf_conn.close()
    if os.path.exists(file_path):
        result = {'pids': [], 'process_names': []}
        try:
            with open(file_path, encoding='utf-8') as f:
                lines = [line.strip() for line in f if line.strip()]
            process_regex = re.compile(r'^\s*(\S+)\s+(\d+)\s+(\d+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(.*)$')
            for line in lines[1:]:
                match = process_regex.match(line)
                if not match:
                    continue
                pid = int(match.group(2))
                cmd = match.group(8)
                if package_name in cmd:
                    process_name = cmd[5:] if cmd.startswith('init ') else cmd
                    result['pids'].append(pid)
                    result['process_names'].append(process_name)
        except Exception as err:
            logging.error('处理文件失败: %s', err)
    if pids != []:
        process_names = []
        for _ in pids:
            process_names.append(package_name)
        result['pids'] = pids
        result['process_names'] = process_names

    return result


def _create_base_directories(report_report_dir, hiperf_base_dir, htrace_base_dir):
    """创建基础目录结构

    注意：不再创建 memory 目录，memory 数据从 trace.htrace 中获取
    htrace_base_dir 可以为 None，表示不创建 htrace 目录
    """
    if not os.path.exists(report_report_dir):
        os.makedirs(report_report_dir)
        os.makedirs(hiperf_base_dir)
        if htrace_base_dir:
            os.makedirs(htrace_base_dir)
            logging.info('Base directories created: %s, %s, %s', hiperf_base_dir, htrace_base_dir, report_report_dir)
        else:
            logging.info('Base directories created: %s, %s (htrace skipped)', hiperf_base_dir, report_report_dir)


def _process_perf_file(perf_path, hiperf_step_dir, target_db_files, package_name, pids):
    """处理单个perf文件"""
    if not os.path.exists(perf_path):
        logging.warning('Perf file not found: %s', perf_path)
        return

    # 复制perf文件
    target_data_file = os.path.join(hiperf_step_dir, 'perf.data')
    shutil.copy2(perf_path, target_data_file)
    logging.info('Copied %s to %s', perf_path, target_data_file)

    # 检查是否存在对应的.db文件并处理
    current_db_file = _handle_perf_db_file(perf_path, hiperf_step_dir, target_data_file, target_db_files)

    # 复制ps_ef.txt文件
    _copy_ps_ef_file(perf_path, hiperf_step_dir)

    # 创建pids.json
    _create_pids_json(current_db_file, hiperf_step_dir, package_name, pids)


def _process_trace_file(trace_path, htrace_step_dir):
    """处理单个trace文件"""
    target_htrace_file = os.path.join(htrace_step_dir, 'trace.htrace')
    shutil.copy2(trace_path, target_htrace_file)
    logging.info('Copied %s to %s', trace_path, target_htrace_file)


def _handle_perf_db_file(perf_path, hiperf_step_dir, target_data_file, target_db_files):
    """
    处理perf数据库文件：
    1. 如果perf_path同目录下存在.db文件，直接复制到目标路径并改名为perf.db
    2. 如果不存在.db文件，则转换perf.data为perf.db，等待转换完成

    Args:
        perf_path: 原始perf文件路径
        hiperf_step_dir: 目标step目录
        target_data_file: 目标perf.data文件路径
        target_db_files: 数据库文件列表

    Returns:
        str: 数据库文件路径，如果失败返回None
    """
    # 检查原始perf文件同目录下是否存在对应的.db文件
    perf_dir = os.path.dirname(perf_path)
    perf_basename = os.path.splitext(os.path.basename(perf_path))[0]
    source_db_file = os.path.join(perf_dir, f'{perf_basename}.db')

    target_db_file = os.path.join(hiperf_step_dir, 'perf.db')

    if os.path.exists(source_db_file):
        # 如果存在.db文件，直接复制到目标路径
        shutil.copy2(source_db_file, target_db_file)
        logging.info('Copied existing DB file %s to %s', source_db_file, target_db_file)
        target_db_files.append(target_db_file)
        return target_db_file

    # 如果不存在.db文件，需要转换perf.data为perf.db
    logging.info('No existing DB file found, converting %s to %s', target_data_file, target_db_file)
    return _convert_perf_to_db(target_data_file, target_db_files)


def _convert_perf_to_db(target_data_file, target_db_files):
    """
    转换perf文件为数据库文件，等待转换完成

    Args:
        target_data_file: perf.data文件路径
        target_db_files: 数据库文件列表

    Returns:
        str: 数据库文件路径，如果失败返回None
    """
    target_db_file = target_data_file.replace('.data', '.db')

    if not os.path.exists(target_data_file):
        logging.error('Source perf.data file not found: %s', target_data_file)
        return None

    # 执行转换，ExeUtils.convert_data_to_db是同步的，会等待转换完成
    logging.info('Starting conversion from %s to %s', target_data_file, target_db_file)

    if ExeUtils.convert_data_to_db(target_data_file, target_db_file):
        target_db_files.append(target_db_file)
        logging.info('Successfully converted and verified DB file: %s', target_db_file)
        return target_db_file

    logging.error('Failed to convert perf to db for %s', target_data_file)
    return None


def _copy_ps_ef_file(perf_path, hiperf_step_dir):
    """复制ps_ef.txt文件"""
    ps_ef_files = glob.glob(os.path.join(os.path.dirname(perf_path), 'ps_ef.txt'))
    if ps_ef_files:
        source_ps_ef_file = ps_ef_files[0]
        target_ps_ef_file = os.path.join(hiperf_step_dir, 'ps_ef.txt')
        shutil.copy2(source_ps_ef_file, target_ps_ef_file)
        logging.info('Copied %s to %s', source_ps_ef_file, target_ps_ef_file)


def _create_pids_json(current_db_file, hiperf_step_dir, package_name, pids):
    """创建pids.json文件"""
    ps_ef_file_path = os.path.join(hiperf_step_dir, 'ps_ef.txt')
    pids_json = parse_processes(current_db_file, ps_ef_file_path, package_name, pids)
    with open(os.path.join(hiperf_step_dir, 'pids.json'), 'w', encoding='utf-8') as f:
        json.dump(pids_json, f)
    logging.info('pids.json create success: %s', os.path.join(hiperf_step_dir, 'pids.json'))
