import base64
import glob
import gzip
import json
import logging
import os
import re
import shutil
import sqlite3
import zlib
from pathlib import Path
from typing import Optional

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
    app_name = kwargs.get('app_name', '')
    app_version = kwargs.get('app_version', '')
    rom_version = kwargs.get('rom_version', '')
    scene = kwargs.get('scene', '')

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
            'app_name': app_name,
            'app_version': app_version,
            'scene': scene,
            'device': {
                'sn': '',
                'model': '',
                'type': '',
                'platform': 'HarmonyOS NEXT',
                'version': rom_version,
                'others': {},
            },
            'timestamp': 0,
        }
        with open(os.path.join(report_dir, 'testInfo.json'), 'w', encoding='utf-8') as f:
            json.dump(test_info, f)
        logging.info('testInfo.json create success: %s', os.path.join(report_dir, 'testInfo.json'))

        # 处理steps.json文件
        target_steps_file = os.path.join(report_dir, 'steps.json')
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

    # 检查并移动log文件夹：如果当前输出目录的父目录的父目录存在log文件夹，将其移动到输出目录下
    _move_log_folder_if_exists(report_dir)


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

    # 如果perf文件同目录下存在原始的 hiperf_report.html，复制到step目录
    _copy_hiperf_html_file(perf_path, hiperf_step_dir)

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


def _copy_hiperf_html_file(perf_path: str, hiperf_step_dir: str) -> Optional[str]:
    """如果perf文件同目录下存在原始的hiperf_report.html，复制到step目录。

    火焰图HTML由hiperf工具在数据采集阶段生成，包含完整的符号数据（1077+库）。
    update命令应直接复用此原始HTML，而不是通过perf -i重新生成（仅产生12个库的缩略数据）。

    Args:
        perf_path: 原始perf.data文件路径
        hiperf_step_dir: 目标step目录

    Returns:
        复制后的HTML文件路径，未找到则返回None
    """
    perf_dir = os.path.dirname(perf_path)
    source_html = os.path.join(perf_dir, 'hiperf_report.html')
    if os.path.isfile(source_html):
        target_html = os.path.join(hiperf_step_dir, 'hiperf_report.html')
        # Strip any previously-embedded symbol recovery panel (from prior runs)
        with open(source_html, 'rb') as f:
            data = f.read()
        _SR_EMBED_MARKER = b'<!-- hapray-symbol-recovery-embedded -->'
        idx = data.find(_SR_EMBED_MARKER)
        if idx != -1:
            close_body = data.rfind(b'</body>')
            if close_body != -1 and idx < close_body:
                data = data[:idx] + data[close_body:]
            else:
                data = data[:idx]
        with open(target_html, 'wb') as f:
            f.write(data)
        logging.info('✓ 复制原始的 hiperf_report.html: %s -> %s', source_html, target_html)
        return target_html
    logging.debug('未找到原始的 hiperf_report.html: %s', source_html)
    return None


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


def _move_log_folder_if_exists(report_dir: str):
    """
    检查并移动log文件夹：如果当前输出目录的父目录的父目录存在log文件夹，将其移动到输出目录下

    Args:
        report_dir: 输出目录路径
    """
    try:
        # 获取输出目录的父目录的父目录
        grandparent_dir = os.path.dirname(os.path.dirname(report_dir))

        # 检查祖父目录是否存在
        if not os.path.exists(grandparent_dir):
            logging.debug('祖父目录不存在，跳过log文件夹检查: %s', grandparent_dir)
            return

        # 检查祖父目录下是否存在log文件夹
        log_source_path = os.path.join(grandparent_dir, 'log')
        if not os.path.exists(log_source_path):
            logging.debug('源log文件夹不存在，跳过移动: %s', log_source_path)
            return

        # 目标路径
        log_target_path = os.path.join(report_dir, 'log')

        # 如果目标路径已存在，先移除
        if os.path.exists(log_target_path):
            logging.warning('目标log文件夹已存在，将被覆盖: %s', log_target_path)
            shutil.rmtree(log_target_path)

        # 移动log文件夹
        shutil.move(log_source_path, log_target_path)
        logging.info('✓ 已将log文件夹从 %s 移动到 %s', log_source_path, log_target_path)

    except Exception as e:
        logging.error('移动log文件夹失败: %s', str(e))


def _decode_record_data(raw: str) -> Optional[str]:
    """解码 record_data 内容，支持黄区（纯 JSON）和蓝区（base64+gzip/zlib）。

    黄区：raw 以 { 或 [ 开头 → 直接作为 JSON 返回。
    蓝区：raw 是 base64 编码 → 按 magic bytes 区分 gzip/zlib 解压。

    Args:
        raw: record_data 原始字符串

    Returns:
        解码后的 JSON 字符串，失败返回 None
    """
    stripped = raw.strip()
    if not stripped:
        return None

    # 黄区：纯 JSON
    if stripped.startswith('{') or stripped.startswith('['):
        return stripped

    # 蓝区：base64 编码 + 可能压缩
    try:
        decoded = base64.b64decode(stripped)
    except Exception as e:
        logging.warning('record_data is not valid base64: %s', e)
        return None

    # 通过 magic bytes 判断压缩格式
    if decoded[:2] == b'\x1f\x8b':  # gzip
        try:
            return gzip.decompress(decoded).decode('utf-8')
        except Exception as e:
            logging.warning('gzip decompress failed: %s', e)
            return None
    elif decoded[:2] in (b'x\x9c', b'x\xda', b'x\x01'):  # zlib
        try:
            return zlib.decompress(decoded).decode('utf-8')
        except Exception as e:
            logging.warning('zlib decompress failed: %s', e)
            return None
    else:
        # 无压缩，直接尝试 UTF-8 解码
        try:
            return decoded.decode('utf-8')
        except Exception as e:
            logging.warning('base64 decoded data is not valid UTF-8: %s', e)
            return None


def extract_perf_json_from_flame_html(html_path: str) -> Optional[str]:
    """从已有的 hiperf_report.html 中提取嵌入式 perf.json 数据。

    支持两种格式的火焰图 HTML：
    - 黄区：record_data 中直接存放纯 JSON
    - 蓝区：record_data 中存放 base64(gzip/zlib(perf.json))

    Args:
        html_path: hiperf_report.html 文件路径

    Returns:
        perf.json 原始 JSON 字符串，提取失败返回 None
    """
    html_path = Path(html_path)
    if not html_path.is_file():
        logging.error('Flame HTML file not found: %s', html_path)
        return None

    try:
        html = html_path.read_text(encoding='utf-8', errors='replace')
    except OSError as e:
        logging.error('Failed to read flame HTML %s: %s', html_path, e)
        return None

    # 匹配 record_data script 标签（兼容 type="json" 和 type="application/gzip+json;base64"）
    m = re.search(
        r'<script\s+id="record_data"[^>]*>\s*(.+?)\s*</script>',
        html,
        re.DOTALL,
    )
    if not m:
        logging.error('No record_data found in flame HTML: %s', html_path)
        return None

    raw = m.group(1).strip()
    if not raw:
        logging.error('Empty record_data in flame HTML: %s', html_path)
        return None

    json_str = _decode_record_data(raw)
    if json_str is None:
        logging.error('Failed to decode record_data from %s', html_path)
        return None

    # 验证是有效的 JSON
    try:
        json.loads(json_str)
    except json.JSONDecodeError as e:
        logging.error('Decoded record_data is not valid JSON from %s: %s', html_path, e)
        return None

    logging.info(
        'Extracted perf.json from flame HTML: %s (%.1f KB, mode=%s)',
        html_path,
        len(json_str) / 1024,
        '黄区(plain JSON)' if raw.startswith('{') or raw.startswith('[') else '蓝区(compressed)',
    )
    return json_str


def restore_perf_json_from_flame_html(report_dir: str, html_path: str) -> bool:
    """从外部 hiperf_report.html 提取 perf.json 并写回 report 目录。

    遍历 report_dir 下的所有 hiperf/stepN/ 目录，对第一个缺少 perf.json
    的 step 写入提取的数据。

    Args:
        report_dir: 报告根目录（包含 hiperf/ 子目录）
        html_path: 外部 hiperf_report.html 文件路径

    Returns:
        是否成功写入
    """
    json_str = extract_perf_json_from_flame_html(html_path)
    if json_str is None:
        return False

    # 找第一个缺少 perf.json 的 step 目录
    hiperf_root = Path(report_dir) / 'hiperf'
    if not hiperf_root.is_dir():
        logging.error('No hiperf directory under report_dir: %s', report_dir)
        return False

    step_dirs = sorted(hiperf_root.glob('step*/'))
    if not step_dirs:
        logging.error('No step directories under %s', hiperf_root)
        return False

    # 写入所有 step（通常只有一个 step，但支持多 step）
    written = False
    for step_dir in step_dirs:
        perf_json_path = step_dir / 'perf.json'
        # 如果 perf.json 已存在则跳过（已有数据，可能是 perf -i 产生）
        if perf_json_path.is_file():
            logging.info('perf.json already exists at %s, skip overwrite', perf_json_path)
            continue
        try:
            perf_json_path.write_text(json_str, encoding='utf-8')
            logging.info('Restored perf.json from flame HTML -> %s', perf_json_path)
            written = True
        except OSError as e:
            logging.error('Failed to write perf.json to %s: %s', perf_json_path, e)

    if not written:
        # 所有 step 都已存在 perf.json，写入第一个 step
        first_step = step_dirs[0]
        perf_json_path = first_step / 'perf.json'
        try:
            perf_json_path.write_text(json_str, encoding='utf-8')
            logging.info('All steps already have perf.json; overwrote first step: %s', perf_json_path)
            written = True
        except OSError as e:
            logging.error('Failed to write perf.json to %s: %s', perf_json_path, e)

    return written


def update_load_excel_with_recovered_symbols(case_dir: str) -> bool:
    """符号恢复后，更新负载分析 Excel 中的偏移符号为恢复后的函数名。

    读取 hiperf/stepN/symbol_recovery_replacements.json 中的映射，
    应用到 report/ecol_load_perf_*.xlsx 以及 .symbol_recovery/stepN/*_analysis.xlsx 的符号列。

    Args:
        case_dir: 用例目录（包含 report/ 和 hiperf/ 子目录）

    Returns:
        是否成功更新了至少一个 Excel
    """
    # 收集所有 step 的 replacements
    replacements: dict[str, str] = {}
    case_path = Path(case_dir)
    for step_dir in sorted(case_path.glob('hiperf/step*/')):
        manifest = step_dir / 'symbol_recovery_replacements.json'
        if not manifest.is_file():
            continue
        try:
            data = json.loads(manifest.read_text(encoding='utf-8', errors='replace'))
            if not isinstance(data, list):
                continue
            for entry in data:
                if isinstance(entry, dict):
                    orig = str(entry.get('original', '')).strip()
                    repl = str(entry.get('replaced', '')).strip()
                    if orig and repl:
                        replacements[orig] = repl
        except (OSError, json.JSONDecodeError) as e:
            logging.debug('Failed to read replacements %s: %s', manifest, e)

    if not replacements:
        logging.info('No symbol recovery replacements found for %s', case_dir)
        return False

    # 收集所有候选 Excel：report/ecol_load_perf_*.xlsx + .symbol_recovery/stepN/*.xlsx
    excels: list[Path] = []
    report_dir = case_path / 'report'
    if report_dir.is_dir():
        excels.extend(sorted(report_dir.glob('ecol_load_perf_*.xlsx')))
    for sr_step_dir in sorted(case_path.glob('.symbol_recovery/step*/')):
        excels.extend(sorted(sr_step_dir.glob('*.xlsx')))

    if not excels:
        logging.info('No load analysis Excel files found for %s', case_dir)
        return False

    updated_any = False
    for excel_path in excels:
        try:
            df = pd.read_excel(str(excel_path), sheet_name=None)
            # 尝试在有符号列的 sheet 中查找并替换
            for sheet_name, sheet_df in df.items():
                cols = [str(c) for c in sheet_df.columns]
                # 优先找地址/符号列（中英文），回退找函数名列
                symbol_col = next(
                    (c for c in cols if 'Symbol' in c or 'symbol' in c.lower()
                     or '地址' in c or 'address' in c.lower()
                     or '函数名' in c or 'function' in c.lower()),
                    None,
                )
                if not symbol_col:
                    continue

                orig_count = 0
                replaced_count = 0
                for idx in sheet_df.index:
                    val = str(sheet_df.at[idx, symbol_col]).strip()
                    if val in replacements:
                        sheet_df.at[idx, symbol_col] = replacements[val]
                        replaced_count += 1
                        orig_count += 1

                if replaced_count > 0:
                    logging.info(
                        'Replaced %d symbols in sheet %s of %s',
                        replaced_count, sheet_name, excel_path.name,
                    )
                else:
                    # 尝试匹配规范化后的地址
                    for idx in sheet_df.index:
                        val = str(sheet_df.at[idx, symbol_col]).strip()
                        # 尝试 libxxx.so+0x1234 -> libxxx.so+0x1234 匹配
                        normalized = _normalize_excel_symbol(val)
                        if normalized in replacements:
                            sheet_df.at[idx, symbol_col] = replacements[normalized]
                            replaced_count += 1
                    if replaced_count > 0:
                        logging.info(
                            'Replaced %d symbols (normalized match) in sheet %s of %s',
                            replaced_count, sheet_name, excel_path.name,
                        )

            # 写回 Excel
            if replaced_count > 0:
                with pd.ExcelWriter(str(excel_path), engine='openpyxl') as writer:
                    for sheet_name, sheet_df in df.items():
                        sheet_df.to_excel(writer, sheet_name=sheet_name, index=False)
                logging.info('Updated load analysis Excel with recovered symbols: %s', excel_path)
                updated_any = True

        except Exception as e:
            logging.error('Failed to update Excel %s: %s', excel_path, e)

    return updated_any


def _normalize_excel_symbol(val: str) -> str:
    """标准化 Excel 中的符号格式，使其能与替换映射匹配。"""
    val = val.strip()
    # 已经是 normalized 格式: libxxx.so+0x1234
    if re.match(r'^[^/\\]+\.so\+0x[0-9a-fA-F]+$', val):
        return val
    # 尝试从完整路径中提取
    m = re.search(r'([^/\\]+\.so)\+?(0x[0-9a-fA-F]+)$', val)
    if m:
        return f'{m.group(1)}+{m.group(2).lower()}'
    return val
