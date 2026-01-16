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

        logging.info('')
        logging.info('#' * 60)
        logging.info('# 处理 Step %d', step_num)
        logging.info('#' * 60)

        # 创建step目录
        os.makedirs(hiperf_step_dir, exist_ok=True)
        logging.info('创建目录: %s', hiperf_step_dir)

        # 先处理trace文件（如果有），确保trace.db在pids.json生成前就绪
        if trace_paths and i < len(trace_paths):
            htrace_step_dir = os.path.join(htrace_base_dir, f'step{step_num}')
            os.makedirs(htrace_step_dir, exist_ok=True)
            logging.info('创建目录: %s', htrace_step_dir)
            _process_trace_file(trace_paths[i], htrace_step_dir)

            # 如果是.htrace文件，需要立即转换为.db，以便parse_processes可以查询
            trace_htrace = os.path.join(htrace_step_dir, 'trace.htrace')
            trace_db = os.path.join(htrace_step_dir, 'trace.db')
            if os.path.exists(trace_htrace) and not os.path.exists(trace_db):
                logging.info('立即转换 trace.htrace -> trace.db，以便生成 pids.json')
                if not ExeUtils.convert_data_to_db(trace_htrace, trace_db):
                    logging.error('❌ 转换失败: %s', trace_htrace)
                else:
                    logging.info('✓ 转换成功: %s', trace_db)
        else:
            logging.info('没有 trace 文件，跳过 trace 处理')

        # 处理perf文件（此时trace.db已经存在，parse_processes可以从中查询）
        if i < len(perf_paths):
            _process_perf_file(perf_paths[i], hiperf_step_dir, target_db_files, package_name, pids)
        else:
            # 没有perf文件，但可能有trace文件，仍然需要创建pids.json
            logging.info('没有 perf 文件，但需要创建 pids.json（可能从 trace.db 查询）')
            _create_pids_json(None, hiperf_step_dir, package_name, pids)

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
        target_steps_file = os.path.join(report_report_dir, 'steps.json')
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


def parse_processes(target_db_file: str, file_path: str, scene_dir: str, step_name: str, package_name: str, pids: list):
    """
    解析进程PID，优先级：用户提供 > trace.db > perf.db > ps_ef.txt
    """
    if not package_name:
        raise ValueError('包名不能为空')

    # 如果用户提供了 pids（非空列表），直接使用
    # 注意：pids 默认值是 []，所以 if pids 可以正确区分"用户提供"和"未提供"
    if pids and pids != []:
        logging.info('使用用户提供的pids: %s', pids)
        return {'pids': pids, 'process_names': [package_name] * len(pids)}

    # 尝试从 trace.db 查询（优先，因为内存分析需要）
    trace_db = os.path.join(scene_dir, 'htrace', step_name, 'trace.db')
    result = _query_db(trace_db, 'process', 'pid', 'name', package_name)
    if result['pids']:
        logging.info('从trace.db获取到%d个进程: %s', len(result['pids']), result['pids'])
        return result

    # 尝试从 perf.db 查询
    if target_db_file and os.path.exists(target_db_file):
        result = _query_db(target_db_file, 'perf_thread', 'process_id', 'thread_name', package_name)
        if result['pids']:
            logging.info('从perf.db获取到%d个进程: %s', len(result['pids']), result['pids'])
            return result

    # 尝试从 ps_ef.txt 解析
    if os.path.exists(file_path):
        result = _parse_ps_ef(file_path, package_name)
        if result['pids']:
            logging.info('从ps_ef.txt获取到%d个进程: %s', len(result['pids']), result['pids'])
            return result

    logging.error('❌ 未能获取任何PID！package_name=%s', package_name)
    return {'pids': [], 'process_names': []}


def _query_db(db_file: str, table: str, pid_col: str, name_col: str, package_name: str):
    """从数据库查询进程"""
    if not os.path.exists(db_file):
        return {'pids': [], 'process_names': []}

    try:
        conn = sqlite3.connect(db_file)
        query = f'SELECT DISTINCT {pid_col}, {name_col} FROM {table} WHERE {name_col} LIKE ?'
        df = pd.read_sql_query(query, conn, params=(f'%{package_name}%',))
        conn.close()

        pids = df[pid_col].tolist()
        names = df[name_col].tolist()
        return {'pids': pids, 'process_names': names}
    except Exception as e:
        logging.error('查询%s失败: %s', db_file, e)
        return {'pids': [], 'process_names': []}


def _parse_ps_ef(file_path: str, package_name: str):
    """从ps_ef.txt解析进程"""
    try:
        with open(file_path, encoding='utf-8') as f:
            lines = [line.strip() for line in f if line.strip()]

        regex = re.compile(r'^\s*\S+\s+(\d+)\s+\d+\s+\S+\s+\S+\s+\S+\s+\S+\s+(.*)$')
        pids, names = [], []

        for line in lines[1:]:
            match = regex.match(line)
            if match and package_name in match.group(2):
                pids.append(int(match.group(1)))
                names.append(match.group(2))

        return {'pids': pids, 'process_names': names}
    except Exception as e:
        logging.error('解析ps_ef.txt失败: %s', e)
        return {'pids': [], 'process_names': []}


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
    logging.info('=' * 60)
    logging.info('开始处理 perf 文件: %s', perf_path)
    logging.info('=' * 60)

    if not os.path.exists(perf_path):
        logging.warning('Perf file not found: %s', perf_path)
        return

    # 复制perf文件
    target_data_file = os.path.join(hiperf_step_dir, 'perf.data')
    shutil.copy2(perf_path, target_data_file)
    logging.info('✓ 复制 perf.data: %s -> %s', perf_path, target_data_file)

    # 检查是否存在对应的.db文件并处理
    current_db_file = _handle_perf_db_file(perf_path, hiperf_step_dir, target_data_file, target_db_files)
    logging.info('perf.db 文件: %s', current_db_file if current_db_file else '未生成')

    # 复制ps_ef.txt文件
    _copy_ps_ef_file(perf_path, hiperf_step_dir)

    # 创建pids.json
    logging.info('-' * 60)
    logging.info('准备创建 pids.json')
    logging.info('-' * 60)
    _create_pids_json(current_db_file, hiperf_step_dir, package_name, pids)
    logging.info('=' * 60)


def _process_trace_file(trace_path, htrace_step_dir):
    """处理单个trace文件

    如果输入是.db文件，直接复制为trace.db
    如果输入是.htrace文件，复制为trace.htrace（后续会转换为trace.db）
    """
    logging.info('=' * 60)
    logging.info('开始处理 trace 文件: %s', trace_path)
    logging.info('=' * 60)

    if trace_path.endswith('.db'):
        # 如果输入是.db文件，直接复制为trace.db
        target_db_file = os.path.join(htrace_step_dir, 'trace.db')
        shutil.copy2(trace_path, target_db_file)
        logging.info('✓ 复制 trace.db: %s -> %s', trace_path, target_db_file)
    else:
        # 如果输入是.htrace文件，复制为trace.htrace
        target_htrace_file = os.path.join(htrace_step_dir, 'trace.htrace')
        shutil.copy2(trace_path, target_htrace_file)
        logging.info('✓ 复制 trace.htrace: %s -> %s', trace_path, target_htrace_file)
        logging.info('  注意：trace.htrace 需要在后续转换为 trace.db')

    logging.info('=' * 60)


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
    logging.info('检查 perf.db 文件...')

    # 检查原始perf文件同目录下是否存在对应的.db文件
    perf_dir = os.path.dirname(perf_path)
    perf_basename = os.path.splitext(os.path.basename(perf_path))[0]
    source_db_file = os.path.join(perf_dir, f'{perf_basename}.db')

    target_db_file = os.path.join(hiperf_step_dir, 'perf.db')

    if os.path.exists(source_db_file):
        # 如果存在.db文件，直接复制到目标路径
        shutil.copy2(source_db_file, target_db_file)
        logging.info('✓ 复制已有的 perf.db: %s -> %s', source_db_file, target_db_file)
        target_db_files.append(target_db_file)
        return target_db_file

    # 如果不存在.db文件，需要转换perf.data为perf.db
    logging.info('未找到已有的 perf.db，需要转换 perf.data -> perf.db')
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
        logging.error('❌ perf.data 文件不存在: %s', target_data_file)
        return None

    # 执行转换，ExeUtils.convert_data_to_db是同步的，会等待转换完成
    logging.info('开始转换 perf.data -> perf.db...')
    logging.info('  源文件: %s', target_data_file)
    logging.info('  目标文件: %s', target_db_file)

    if ExeUtils.convert_data_to_db(target_data_file, target_db_file):
        target_db_files.append(target_db_file)
        logging.info('✓ 转换成功，perf.db 已生成: %s', target_db_file)
        return target_db_file

    logging.error('❌ 转换失败: %s', target_data_file)
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
    logging.info('开始创建 pids.json...')
    logging.info('  current_db_file: %s', current_db_file)
    logging.info('  hiperf_step_dir: %s', hiperf_step_dir)
    logging.info('  package_name: %s', package_name)
    logging.info('  用户提供的pids: %s', pids)

    # 从 hiperf_step_dir 推导出 scene_dir 和 step_name
    # hiperf_step_dir = /path/to/report/hiperf/step1
    step_name = os.path.basename(hiperf_step_dir)  # step1
    hiperf_base_dir = os.path.dirname(hiperf_step_dir)  # /path/to/report/hiperf
    scene_dir = os.path.dirname(hiperf_base_dir)  # /path/to/report

    logging.info('  推导出的 scene_dir: %s', scene_dir)
    logging.info('  推导出的 step_name: %s', step_name)

    ps_ef_file_path = os.path.join(hiperf_step_dir, 'ps_ef.txt')
    pids_json = parse_processes(current_db_file, ps_ef_file_path, scene_dir, step_name, package_name, pids)

    pids_json_path = os.path.join(hiperf_step_dir, 'pids.json')
    with open(pids_json_path, 'w', encoding='utf-8') as f:
        json.dump(pids_json, f, indent=2)

    logging.info('✓ pids.json 创建成功: %s', pids_json_path)
    logging.info('  写入的内容: %s', pids_json)

    if not pids_json.get('pids'):
        logging.error('❌ 警告：pids.json 中的 pids 为空！')
        logging.error('   这将导致内存分析无法获取数据！')
