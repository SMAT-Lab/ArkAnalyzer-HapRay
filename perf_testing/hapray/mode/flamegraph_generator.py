"""
火焰图生成模块 - 从 perf.db 获取火焰图数据并生成HTML报告
"""
import base64
import json
import logging
import os
import sqlite3
import zlib
from pathlib import Path
from typing import Optional


def _build_flame_tree(cursor, target_processes):
    """
    构建火焰图树形结构

    Args:
        cursor: SQLite cursor
        target_processes: 目标进程ID列表，None表示全部

    Returns:
        dict: 火焰图树形结构
    """
    tree = {'name': 'root', 'value': 0, 'children': []}

    # 检查perf_callchain表是否存在
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='perf_callchain'")
    if not cursor.fetchone():
        logging.warning('perf_callchain table not found')
        return tree

    # 加载 file_id -> path 映射
    file_path_map = {}
    try:
        cursor.execute('SELECT id, path FROM perf_files WHERE path IS NOT NULL')
        for row in cursor.fetchall():
            file_path_map[row[0]] = row[1]
    except Exception:
        pass

    # 查询callchain数据（使用ip+path作为节点名，避免pc.name是INT而非函数名）
    cursor.execute("""
        SELECT
            ps.id as sample_id,
            ps.callchain_id,
            ps.event_count,
            pc.depth,
            pc.ip,
            pc.file_id,
            pc.symbol_id
        FROM perf_sample ps
        JOIN perf_callchain pc ON ps.callchain_id = pc.callchain_id
        ORDER BY ps.callchain_id, pc.depth DESC
    """)
    rows = cursor.fetchall()

    # 构建火焰图
    callchains = {}
    for row in rows:
        sample_id = row[0]
        callchain_id = row[1]
        event_count = row[2]
        depth = row[3]
        ip = row[4]
        file_id = row[5]
        symbol_id = row[6]

        if callchain_id not in callchains:
            callchains[callchain_id] = {
                'event_count': event_count,
                'frames': [],
            }

        # 构建有意义的节点名：优先用 文件路径+偏移，回退用十六进制地址
        file_path = file_path_map.get(file_id) if file_id is not None else None
        if ip:
            ip_str = f'0x{ip:x}'
            if file_path:
                # 取文件名末尾作为标识
                name = f'{file_path}+{ip_str}'
            else:
                name = ip_str
        else:
            name = 'unknown'

        callchains[callchain_id]['frames'].append({
            'depth': depth,
            'ip': ip_str if ip else 'unknown',
            'name': name,
            'file_id': file_id,
            'symbol_id': symbol_id,
        })

    for data in callchains.values():
        frames = data['frames']
        if not frames:
            continue

        current = tree
        for frame in sorted(frames, key=lambda x: x['depth'], reverse=True):
            name = frame['name']
            found = None
            for child in current['children']:
                if child['name'] == name:
                    found = child
                    break

            if found:
                found['value'] += data['event_count']
                current = found
            else:
                new_node = {
                    'name': name,
                    'value': data['event_count'],
                    'children': [],
                }
                current['children'].append(new_node)
                current = new_node

    logging.info('Built flame tree with %d unique callchains', len(callchains))
    return tree


def _tree_to_list(node, max_depth=100, current_depth=0):
    """将树形结构转换为火焰图列表格式"""
    result = []
    name = node.get('name', '...')
    value = node.get('value', 0)
    result.append({'name': name, 'value': value})

    if current_depth < max_depth:
        children = node.get('children', [])
        for child in children:
            result.extend(_tree_to_list(child, max_depth, current_depth + 1))

    return result


def _build_callchain_hierarchy(cursor):
    """
    从 perf.db 的 callchain 数据构建 进程→线程→库→函数 层级结构

    Returns:
        dict: 包含 processes_list, symbol_map, file_list,
              process_name_map, thread_name_map, total_event_count
              数据不足时返回 None
    """
    # 1. file_id → file_path 映射
    file_path_map = {}
    try:
        cursor.execute('SELECT id, path FROM perf_files WHERE path IS NOT NULL')
        for row in cursor.fetchall():
            file_path_map[row[0]] = row[1]
    except Exception:
        pass

    # 2. perf_files.id → symbol 映射（pc.name 是 INT，指向 perf_files.id）
    file_symbol_map = {}
    try:
        cursor.execute('SELECT id, symbol FROM perf_files WHERE symbol IS NOT NULL AND symbol != ""')
        for row in cursor.fetchall():
            file_symbol_map[row[0]] = row[1]
    except Exception:
        pass

    # 3. 加载所有 callchain 帧
    try:
        cursor.execute("""
            SELECT callchain_id, depth, ip, file_id, name
            FROM perf_callchain
            ORDER BY callchain_id, depth ASC
        """)
    except Exception:
        logging.warning('perf_callchain table not found')
        return None

    callchain_frames = {}
    for row in cursor.fetchall():
        cc_id = row[0]
        if cc_id not in callchain_frames:
            callchain_frames[cc_id] = []
        callchain_frames[cc_id].append({
            'depth': row[1],
            'ip': row[2],
            'file_id': row[3],
            'name': row[4],
        })

    if not callchain_frames:
        logging.warning('No callchain data found in perf.db')
        return None

    # 4. 加载采样数据（含线程/进程关系）
    try:
        cursor.execute("""
            SELECT ps.id, ps.callchain_id, ps.thread_id, ps.event_count, ps.event_type_id,
                   pt.process_id, pt.thread_name
            FROM perf_sample ps
            LEFT JOIN perf_thread pt ON ps.thread_id = pt.thread_id
        """)
    except Exception as e:
        logging.warning('Failed to query samples with thread info: %s', e)
        return None

    samples = cursor.fetchall()
    if not samples:
        logging.warning('No samples found in perf.db')
        return None

    # 5. 进程名称映射
    # 先从 process 表获取（通常只有 swapper）
    process_names = {}
    try:
        cursor.execute('SELECT pid, name FROM process WHERE name IS NOT NULL')
        for row in cursor.fetchall():
            process_names[row[0]] = row[1]
    except Exception:
        pass

    # 再从 perf_thread 补齐：thread_id == process_id 的主线程名即为进程名
    try:
        cursor.execute('SELECT thread_id, thread_name FROM perf_thread WHERE thread_id = process_id AND thread_name IS NOT NULL')
        for row in cursor.fetchall():
            process_names[row[0]] = row[1]
    except Exception:
        pass

    # 6. 构建层级结构
    symbol_map = {}
    sym_key_to_id = {}
    file_list = []
    file_to_idx = {}
    proc_map = {}

    for sample in samples:
        _callchain_id = sample[1]
        thread_id = sample[2]
        event_count = sample[3]
        event_type_id = sample[4]
        process_id = sample[5]
        thread_name = sample[6] or ''

        # 只处理 CPU cycles 事件（event_type_id 可能是 0 或 1）
        if event_type_id is not None and event_type_id not in (0, 1):
            continue
        if process_id is None:
            continue

        frames = callchain_frames.get(_callchain_id, [])
        if not frames:
            continue

        process_name = process_names.get(process_id, '')

        for frame in frames:
            name_id = frame['name']
            frame_file_id = frame['file_id']
            ip = frame['ip']

            # 解析函数名
            symbol_name = ''
            if name_id is not None and name_id >= 0 and name_id in file_symbol_map:
                symbol_name = file_symbol_map[name_id]

            if not symbol_name:
                # 回退：file_path+0x{ip}
                fpath = file_path_map.get(frame_file_id) if frame_file_id is not None else None
                if ip:
                    ip_str = f'0x{ip:x}'
                    symbol_name = f'{fpath}+{ip_str}' if fpath else ip_str
                else:
                    symbol_name = 'unknown'

            if not symbol_name:
                continue

            # 文件路径
            frame_path = file_path_map.get(frame_file_id) if frame_file_id is not None else ''

            # 文件索引
            if frame_path not in file_to_idx:
                file_to_idx[frame_path] = len(file_list)
                file_list.append(frame_path)
            file_idx = file_to_idx[frame_path]

            # SymbolMap 条目
            sym_key = (symbol_name, frame_path)
            if sym_key not in sym_key_to_id:
                sid = str(len(symbol_map))
                sym_key_to_id[sym_key] = sid
                symbol_map[sid] = {'symbol': symbol_name, 'file': file_idx}
            sid = sym_key_to_id[sym_key]

            # 进程
            if process_id not in proc_map:
                proc_map[process_id] = {
                    'pid': process_id, 'processName': process_name, 'eventCount': 0, 'threads': {},
                }
            proc = proc_map[process_id]
            proc['eventCount'] += event_count

            # 线程
            if thread_id not in proc['threads']:
                proc['threads'][thread_id] = {
                    'tid': thread_id, 'threadName': thread_name, 'eventCount': 0, 'sampleCount': 0, 'libs': {},
                }
            thread = proc['threads'][thread_id]
            thread['eventCount'] += event_count
            if event_count > 0:
                thread['sampleCount'] += 1

            # 库
            if file_idx not in thread['libs']:
                thread['libs'][file_idx] = {'fileId': file_idx, 'eventCount': 0, 'functions': {}}
            lib = thread['libs'][file_idx]
            lib['eventCount'] += event_count

            # 函数 counts: [call_count, self_cost, total_cost]
            if sid not in lib['functions']:
                lib['functions'][sid] = {'symbol': int(sid), 'counts': [0, 0, 0]}
            fn = lib['functions'][sid]
            fn['counts'][0] += 1                    # call_count
            fn['counts'][2] += event_count          # total_cost
            if frame['depth'] == 0:
                fn['counts'][1] += event_count      # self_cost（仅叶子帧）

    if not proc_map:
        logging.warning('No process hierarchy built from callchain data')
        return None

    # 7. 构建层级列表
    processes_list = []
    new_process_name_map = {}
    new_thread_name_map = {}

    for pid in sorted(proc_map):
        proc = proc_map[pid]
        new_process_name_map[str(pid)] = proc['processName']

        threads_list = []
        for tid in sorted(proc['threads']):
            th = proc['threads'][tid]
            new_thread_name_map[str(tid)] = th['threadName']

            libs_list = []
            for file_idx in sorted(th['libs']):
                lb = th['libs'][file_idx]
                libs_list.append({
                    'fileId': lb['fileId'],
                    'eventCount': lb['eventCount'],
                    'functions': sorted(lb['functions'].values(), key=lambda x: x['counts'][1], reverse=True),
                })

            threads_list.append({
                'tid': th['tid'],
                'eventCount': th['eventCount'],
                'sampleCount': th['sampleCount'],
                'libs': libs_list,
            })

        processes_list.append({
            'pid': proc['pid'],
            'eventCount': proc['eventCount'],
            'threads': threads_list,
        })

    total_event_count = sum(p['eventCount'] for p in processes_list)

    logging.info(
        'Built callchain hierarchy: %d processes, %d threads, %d symbols, %d files',
        len(processes_list), len(new_thread_name_map),
        len(symbol_map), len(file_list))

    return {
        'processes_list': processes_list,
        'symbol_map': symbol_map,
        'file_list': file_list,
        'process_name_map': new_process_name_map,
        'thread_name_map': new_thread_name_map,
        'total_event_count': total_event_count,
    }


def generate_perf_json_from_db(perf_db_path, output_path, package_name):
    """
    从 perf.db 生成火焰图所需的 perf.json 文件

    优先从 callchain 数据构建进程→线程→库→函数的层级结构，
    使得火焰图能正确显示调用堆栈。callchain 数据不足时回退到
    仅输出扁平元数据。

    Args:
        perf_db_path: perf.db 文件路径
        output_path: 输出的 perf.json 文件路径
        package_name: 应用包名，用于过滤进程

    Returns:
        bool: 是否成功生成
    """
    db_path = Path(perf_db_path)
    if not db_path.exists():
        logging.error('perf.db not found: %s', perf_db_path)
        return False

    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        # 采样总数
        cursor.execute('SELECT COUNT(*) FROM perf_sample')
        sample_count = cursor.fetchone()[0]
        logging.info('Total samples in perf.db: %d', sample_count)

        if sample_count == 0:
            logging.warning('No samples found in perf.db')
            conn.close()
            return False

        # 事件类型
        cursor.execute('SELECT DISTINCT event_type_id FROM perf_sample WHERE event_type_id IS NOT NULL')
        event_types = cursor.fetchall()
        record_sample_info = []
        if event_types:
            for row in event_types:
                record_sample_info.append({
                    'eventConfigName': f'Event-{row[0]}',
                    'eventType': 'cpu-cycles',
                    'index': row[0],
                })
        else:
            record_sample_info.append({
                'eventConfigName': 'cpu-cycles',
                'eventType': 'cpu-cycles',
                'index': 0,
            })

        # 尝试从 callchain 数据构建完整层级结构
        hierarchy = _build_callchain_hierarchy(cursor)

        if hierarchy is not None:
            logging.info('Using callchain hierarchy for perf.json')
            rsi = record_sample_info[0] if record_sample_info else {}
            rsi['eventCount'] = hierarchy['total_event_count']
            rsi['processes'] = hierarchy['processes_list']

            flame_data = {
                'recordSampleInfo': record_sample_info,
                'SymbolMap': hierarchy['symbol_map'],
                'symbolsFileList': hierarchy['file_list'],
                'processNameMap': hierarchy['process_name_map'],
                'threadNameMap': hierarchy['thread_name_map'],
                'totalRecordSamples': sample_count,
                'deviceType': 'HarmonyOS',
                'osVersion': '',
                'deviceTime': '',
                'deviceCommandLine': '',
            }
        else:
            logging.warning('Callchain hierarchy not available, falling back to flat metadata')
            flame_data = {
                'recordSampleInfo': record_sample_info,
                'SymbolMap': [],
                'symbolsFileList': [],
                'processNameMap': {},
                'threadNameMap': {},
                'totalRecordSamples': sample_count,
                'deviceType': 'HarmonyOS',
                'osVersion': '',
                'deviceTime': '',
                'deviceCommandLine': '',
            }

            # 进程映射
            try:
                cursor.execute('SELECT id, name FROM process WHERE name IS NOT NULL')
                for proc_id, proc_name in cursor.fetchall():
                    flame_data['processNameMap'][str(proc_id)] = proc_name
            except Exception:
                logging.warning('Failed to query process table')

            # 线程映射
            try:
                cursor.execute('SELECT thread_id, thread_name FROM perf_thread WHERE thread_name IS NOT NULL')
                for thread_id, thread_name in cursor.fetchall():
                    flame_data['threadNameMap'][str(thread_id)] = thread_name
            except sqlite3.OperationalError:
                logging.warning('perf_thread table not found, skipping thread names')

            # 符号文件列表
            try:
                cursor.execute('SELECT DISTINCT path FROM perf_files WHERE path IS NOT NULL')
                flame_data['symbolsFileList'] = [row[0] for row in cursor.fetchall()]
            except sqlite3.OperationalError:
                logging.warning('perf_files table not found, skipping file list')

            # 符号映射（扁平模式）
            try:
                cursor.execute("""
                    SELECT symbol, path FROM perf_files
                    WHERE symbol IS NOT NULL AND symbol != ''
                """)
                for sym_name, file_path in cursor.fetchall():
                    flame_data['SymbolMap'].append({
                        'name': sym_name,
                        'file': file_path or '',
                    })
            except sqlite3.OperationalError as e:
                logging.warning('SymbolMap query failed: %s', str(e))

        conn.close()

        # 写入文件
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(str(output_file), 'w', encoding='utf-8') as f:
            json.dump(flame_data, f, indent=2)

        logging.info('Generated perf.json: %s', output_path)
        logging.info('  - Events: %d', len(flame_data['recordSampleInfo']))
        logging.info('  - Processes: %d', len(flame_data['processNameMap']))
        logging.info('  - Threads: %d', len(flame_data['threadNameMap']))
        logging.info('  - Symbols: %d', len(flame_data['SymbolMap']))
        logging.info('  - Files: %d', len(flame_data['symbolsFileList']))
        if hierarchy:
            logging.info('  - Hierarchy: %s', 'enabled')
        return True

    except Exception as e:
        logging.exception('Failed to generate perf.json: %s', str(e))
        return False


def generate_hiperf_report(perf_db_path, output_dir, package_name):
    """
    生成最终的火焰图报告（perf.json + hiperf_report.html）

    Args:
        perf_db_path: perf.db 文件路径
        output_dir: 输出目录
        package_name: 应用包名

    Returns:
        str: 生成的 HTML 文件路径，失败返回 None
    """
    try:
        # 首先生成 perf.json
        perf_json_path = Path(str(output_dir)) / 'perf.json'
        if not generate_perf_json_from_db(
            perf_db_path, str(perf_json_path), package_name
        ):
            logging.error('Failed to generate perf.json')
            return None

        # 读取 perf.json 数据
        with open(str(perf_json_path), 'r', encoding='utf-8') as f:
            perf_data = json.load(f)

        # 查找模板文件
        try:
            from hapray.core.common.exe_utils import ExeUtils
            _web = ExeUtils.get_tools_dir('web', require=False)
            template_path = Path(_web) / 'hiperf_report_template.html' if _web else None
        except Exception:
            template_path = None

        if not template_path or not template_path.exists():
            # Fallback: check in perf_testing/resource/web
            _base = Path(__file__).resolve().parent.parent.parent
            template_path = _base / 'resource' / 'web' / 'hiperf_report_template.html'

        if not template_path or not template_path.exists():
            logging.error('Template not found: %s', template_path)
            return None
        if not template_path.exists():
            logging.error('Template not found: %s', template_path)
            return None

        with open(str(template_path), 'r', encoding='utf-8') as f:
            template_html = f.read()

        # 压缩和编码 perf.json
        json_str = json.dumps(perf_data, ensure_ascii=False)
        compressed = zlib.compress(json_str.encode('utf-8'), level=9)
        b64_data = base64.b64encode(compressed).decode('ascii')

        # 写入输出文件：先写模板，再追加压缩数据（与 perf_analyzer 方式一致）
        report_path = Path(str(output_dir)) / 'hiperf_report.html'
        with open(str(report_path), 'w', encoding='utf-8') as f:
            f.write(template_html)
            f.write(f'<script id="record_data" type="application/gzip+json;base64">{b64_data}</script>')

        logging.info('Generated hiperf_report.html: %s', report_path)
        return str(report_path)

    except Exception as e:
        logging.error('Failed to generate hiperf_report: %s', str(e))
        return None
