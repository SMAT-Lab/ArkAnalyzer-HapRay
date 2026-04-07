#!/usr/bin/env python3
"""
内存模式火焰图分析器：从 HTML 火焰图文件中提取符号地址并进行符号恢复
"""

import base64
import gzip
import json
import re
import sqlite3
import zlib
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from core.utils.logger import get_logger

logger = get_logger(__name__)


class MemoryFlameGraphAnalyzer:
    """从内存模式火焰图 HTML 文件中提取符号地址"""

    def __init__(self, html_dir: str, so_dir: str, output_dir: str):
        """
        初始化内存模式火焰图分析器

        Args:
            html_dir: 包含火焰图 HTML 文件的目录
            so_dir: SO 文件目录
            output_dir: 输出目录
        """
        self.html_dir = Path(html_dir)
        self.so_dir = Path(so_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        if not self.html_dir.exists():
            raise FileNotFoundError(f'HTML 目录不存在: {html_dir}')
        if not self.so_dir.exists():
            raise FileNotFoundError(f'SO 目录不存在: {so_dir}')

    def extract_json_from_html(self, html_file: Path) -> Optional[str]:
        """
        从 HTML 文件中提取 JSON 数据

        Args:
            html_file: HTML 文件路径

        Returns:
            解压缩后的 JSON 字符串，如果失败返回 None
        """
        try:
            with open(html_file, 'rb') as f:
                html_content = f.read().decode('utf-8', errors='ignore')

            # 查找 <script id="record_data"> 或 <script id="record_bz_data"> 标签
            patterns = [
                r'<script[^>]*id=["\']record_data["\'][^>]*>(.*?)</script>',
                r'<script[^>]*id=["\']record_bz_data["\'][^>]*>(.*?)</script>',
            ]

            for pattern in patterns:
                match = re.search(pattern, html_content, re.DOTALL | re.IGNORECASE)
                if match:
                    data_content_raw = match.group(1).strip()

                    # 检查是否是压缩/编码的数据
                    if not data_content_raw.startswith('{') and not data_content_raw.startswith('['):
                        # 尝试 base64 解码
                        try:
                            decoded = base64.b64decode(data_content_raw)

                            # 检查是否是 gzip
                            if decoded[:2] == b'\x1f\x8b':
                                decompressed = gzip.decompress(decoded)
                                json_str = decompressed.decode('utf-8', errors='ignore')
                                logger.info(f'  ✅ 从 {html_file.name} 提取 JSON (gzip 压缩)')
                                return json_str
                            # 检查是否是 zlib
                            elif decoded[:2] in (b'x\x9c', b'x\xda', b'x\x01'):
                                decompressed = zlib.decompress(decoded)
                                json_str = decompressed.decode('utf-8', errors='ignore')
                                logger.info(f'  ✅ 从 {html_file.name} 提取 JSON (zlib 压缩)')
                                return json_str
                            else:
                                # 直接解码为 UTF-8
                                json_str = decoded.decode('utf-8', errors='ignore')
                                logger.info(f'  ✅ 从 {html_file.name} 提取 JSON (base64 编码)')
                                return json_str
                        except Exception as e:
                            logger.warning(f'  ⚠️  解码失败: {e}')
                            continue
                    else:
                        # 已经是 JSON 格式
                        logger.info(f'  ✅ 从 {html_file.name} 提取 JSON (未压缩)')
                        return data_content_raw

            logger.warning(f'  ⚠️  未找到 JSON 数据块: {html_file.name}')
            return None

        except Exception as e:
            logger.error(f'  ❌ 读取 HTML 文件失败: {html_file.name}, 错误: {e}')
            return None

    def extract_symbols_from_json(self, json_str: str) -> Tuple[Set[str], Dict[str, int]]:
        """
        从 JSON 字符串中提取所有符号地址和统计信息

        Args:
            json_str: JSON 字符串

        Returns:
            (符号地址集合, 符号统计信息字典) 元组
            符号地址格式如 "libxxx.so+0x1234"
            统计信息字典格式: {symbol: value}，value 可能是调用次数或内存占用
        """
        symbols = set()
        symbol_stats = {}  # {symbol: value} 用于存储统计信息

        try:
            data = json.loads(json_str)

            # 首先尝试从 recordSampleInfo 中提取统计信息（这是主要数据源）
            if 'recordSampleInfo' in data and 'SymbolMap' in data:
                record_sample_info = data.get('recordSampleInfo', [])
                symbol_map = data.get('SymbolMap', {})
                
                logger.info('  从 recordSampleInfo 提取统计信息...')
                
                # 遍历 recordSampleInfo 提取统计信息
                for sample_info in record_sample_info:
                    if isinstance(sample_info, dict) and 'processes' in sample_info:
                        for process in sample_info['processes']:
                            if isinstance(process, dict) and 'threads' in process:
                                for thread in process['threads']:
                                    if isinstance(thread, dict) and 'libs' in thread:
                                        for lib in thread['libs']:
                                            if isinstance(lib, dict) and 'functions' in lib:
                                                for func in lib['functions']:
                                                    if isinstance(func, dict) and 'symbol' in func:
                                                        symbol_id = func.get('symbol')
                                                        counts = func.get('counts', [])
                                                        
                                                        # 从 SymbolMap 中获取符号地址（尝试多种键类型）
                                                        symbol_info = None
                                                        if symbol_id in symbol_map:
                                                            symbol_info = symbol_map[symbol_id]
                                                        elif str(symbol_id) in symbol_map:
                                                            symbol_info = symbol_map[str(symbol_id)]
                                                        elif int(symbol_id) in symbol_map:
                                                            symbol_info = symbol_map[int(symbol_id)]
                                                        
                                                        if symbol_info and isinstance(symbol_info, dict):
                                                            symbol_str = symbol_info.get('symbol', '')
                                                            # 提取 libxxx.so+0x... 格式
                                                            match = re.search(r'(lib[\w_]+\.so\+0x[0-9a-fA-F]+)', symbol_str, re.IGNORECASE)
                                                            if match:
                                                                symbol = match.group(1)
                                                                symbols.add(symbol)
                                                                
                                                                # 提取统计信息（counts 数组格式: [call_count, event_count, ...]）
                                                                if counts and len(counts) >= 2:
                                                                    # counts[1] 是 event_count
                                                                    try:
                                                                        event_count = int(counts[1]) if isinstance(counts[1], (int, float)) else 0
                                                                        if event_count > 0:
                                                                            # 累加统计信息（同一个符号可能出现多次）
                                                                            symbol_stats[symbol] = symbol_stats.get(symbol, 0) + event_count
                                                                    except (ValueError, TypeError):
                                                                        pass

                if symbol_stats:
                    logger.info(f'  ✅ 从 recordSampleInfo 提取了 {len(symbol_stats)} 个符号的统计信息')

            # 也尝试从其他字段中提取符号（作为补充，用于提取没有统计信息的符号）
            def extract_from_value(value, parent_value=None):
                """递归提取符号地址（补充提取，不覆盖已有统计信息）"""
                if isinstance(value, dict):
                    symbol = None
                    
                    # 检查 symbol 字段
                    if 'symbol' in value:
                        symbol_str = value['symbol']
                        if isinstance(symbol_str, str) and '.so+0x' in symbol_str:
                            # 提取 libxxx.so+0x... 格式
                            match = re.search(r'(lib[\w_]+\.so\+0x[0-9a-fA-F]+)', symbol_str, re.IGNORECASE)
                            if match:
                                symbol = match.group(1)
                                symbols.add(symbol)

                    # 检查 f 字段（可能是压缩格式）
                    if 'f' in value:
                        f_value = value['f']
                        if isinstance(f_value, str) and '.so+0x' in f_value:
                            match = re.search(r'(lib[\w_]+\.so\+0x[0-9a-fA-F]+)', f_value, re.IGNORECASE)
                            if match:
                                symbol = match.group(1)
                                symbols.add(symbol)

                    # 提取统计信息（value 字段，作为补充）
                    if 'value' in value and symbol and symbol not in symbol_stats:
                        try:
                            value_count = int(value['value'])
                            if value_count > 0:
                                symbol_stats[symbol] = symbol_stats.get(symbol, 0) + value_count
                        except (ValueError, TypeError):
                            pass

                    # 递归处理所有值
                    for v in value.values():
                        extract_from_value(v, value)

                elif isinstance(value, list):
                    for item in value:
                        extract_from_value(item, parent_value)

                elif isinstance(value, str) and '.so+0x' in value:
                    # 直接是字符串，可能包含符号地址
                    matches = re.findall(r'(lib[\w_]+\.so\+0x[0-9a-fA-F]+)', value, re.IGNORECASE)
                    symbols.update(matches)

            # 补充提取其他符号（如果 recordSampleInfo 中没有）
            extract_from_value(data)

        except json.JSONDecodeError as e:
            logger.error(f'  ❌ JSON 解析失败: {e}')
        except Exception as e:
            logger.error(f'  ❌ 提取符号失败: {e}')

        return symbols, symbol_stats

    def collect_all_symbols(self) -> Tuple[Dict[str, Set[str]], Dict[str, int]]:
        """
        从所有 HTML 文件中收集符号地址和统计信息

        Returns:
            (html_symbols_dict, total_symbol_stats) 元组
            html_symbols_dict: 字典，键为 HTML 文件名，值为该文件中的符号地址集合
            total_symbol_stats: 字典，键为符号地址，值为统计值（调用次数或内存占用）
        """
        html_files = list(self.html_dir.glob('*.html'))
        if not html_files:
            logger.warning(f'⚠️  未找到 HTML 文件: {self.html_dir}')

        all_symbols = {}
        total_symbols = set()
        total_symbol_stats = {}  # 合并所有文件的统计信息

        logger.info(f'📁 扫描 HTML 文件: {len(html_files)} 个文件')
        for html_file in html_files:
            logger.info(f'  处理: {html_file.name}')
            json_str = self.extract_json_from_html(html_file)
            if json_str:
                symbols, symbol_stats = self.extract_symbols_from_json(json_str)
                all_symbols[html_file.name] = symbols
                total_symbols.update(symbols)
                
                # 合并统计信息
                for symbol, value in symbol_stats.items():
                    total_symbol_stats[symbol] = total_symbol_stats.get(symbol, 0) + value
                
                logger.info(f'    找到 {len(symbols)} 个唯一符号地址')
                if symbol_stats:
                    logger.info(f'    提取了 {len(symbol_stats)} 个符号的统计信息')
                    # 显示一些统计信息示例
                    sorted_stats = sorted(symbol_stats.items(), key=lambda x: x[1], reverse=True)[:5]
                    logger.info(f'    统计信息示例（前5个）:')
                    for sym, count in sorted_stats:
                        logger.info(f'      {sym}: event_count={count}')

        logger.info(f'✅ 总共找到 {len(total_symbols)} 个唯一符号地址')
        if total_symbol_stats:
            logger.info(f'✅ 提取了 {len(total_symbol_stats)} 个符号的统计信息')
            # 显示统计信息范围
            if total_symbol_stats:
                max_count = max(total_symbol_stats.values())
                min_count = min(total_symbol_stats.values())
                logger.info(f'   统计信息范围: event_count 从 {min_count} 到 {max_count}')
                logger.info(f'   top-n 功能可以正常工作 ✅')
        else:
            logger.warning('⚠️  未找到统计信息，所有符号的 event_count 将设为 1')
            logger.warning('   这意味着 top-n 功能无法正常工作（所有符号的统计值相同）')
            logger.warning('   建议：移除 --top-n 参数，分析所有符号')

        return all_symbols, total_symbol_stats

    def create_perf_db_from_symbols(self, symbols: Set[str], symbol_stats: Dict[str, int] = None) -> Path:
        """
        从符号地址集合创建类似 perf.db 的 SQLite 数据库

        Args:
            symbols: 符号地址集合
            symbol_stats: 符号统计信息字典，格式 {symbol: value}，用于设置 event_count

        Returns:
            perf.db 文件路径
        """
        perf_db_file = self.output_dir / 'memory_flamegraph_perf.db'

        # 如果已存在，先删除
        if perf_db_file.exists():
            perf_db_file.unlink()

        logger.info(f'📊 创建 perf.db: {perf_db_file}')
        conn = sqlite3.connect(str(perf_db_file))
        cursor = conn.cursor()

        # 创建 perf_files 表（EventCountAnalyzer 需要）
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS perf_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_id INTEGER,
                serial_id INTEGER,
                symbol TEXT,
                path TEXT
            )
        ''')

        # 创建 data_dict 表（EventCountAnalyzer 需要）
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS data_dict (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                data TEXT
            )
        ''')

        # 创建 perf_callchain 表（EventCountAnalyzer 需要）
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS perf_callchain (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                callchain_id INTEGER,
                depth INTEGER,
                ip INTEGER,
                vaddr_in_file INTEGER,
                offset_to_vaddr INTEGER,
                file_id INTEGER,
                symbol_id INTEGER,
                name INTEGER,
                source_file_id INTEGER,
                line_number INTEGER
            )
        ''')

        # 创建 perf_sample 表（用于存储采样数据）
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS perf_sample (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                callchain_id INTEGER,
                file_id INTEGER,
                symbol TEXT,
                event_count INTEGER DEFAULT 1,
                call_count INTEGER DEFAULT 1
            )
        ''')

        # 创建 missing_symbols 表（用于存储缺失符号）
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS missing_symbols (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                address TEXT NOT NULL,
                so_file TEXT,
                offset INTEGER,
                call_count INTEGER DEFAULT 1,
                event_count INTEGER DEFAULT 1,
                UNIQUE(address)
            )
        ''')

        # 为每个符号创建 file_id 和 name_id（从符号中提取库名）
        file_id_map = {}  # {so_file: file_id}
        name_id_map = {}  # {symbol: name_id}
        file_id_counter = 1
        name_id_counter = 1
        callchain_id_counter = 1

        # 插入符号地址到各个表
        for symbol in symbols:
            # 解析地址：libxxx.so+0x1234
            match = re.match(r'(lib[\w_]+\.so)\+0x([0-9a-fA-F]+)', symbol, re.IGNORECASE)
            if match:
                so_file = match.group(1)
                offset = int(match.group(2), 16)

                # 获取统计信息（如果有）
                event_count = symbol_stats.get(symbol, 1) if symbol_stats else 1
                call_count = 1  # 内存模式下通常没有调用次数信息

                # 获取或创建 file_id
                if so_file not in file_id_map:
                    file_id_map[so_file] = file_id_counter
                    file_id_counter += 1

                    # 插入到 perf_files 表
                    cursor.execute('''
                        INSERT INTO perf_files (file_id, symbol, path)
                        VALUES (?, ?, ?)
                    ''', (file_id_map[so_file], so_file, so_file))

                file_id = file_id_map[so_file]

                # 获取或创建 name_id（用于 data_dict）
                if symbol not in name_id_map:
                    name_id_map[symbol] = name_id_counter
                    name_id_counter += 1

                    # 插入到 data_dict 表（存储符号地址）
                    cursor.execute('''
                        INSERT INTO data_dict (id, data)
                        VALUES (?, ?)
                    ''', (name_id_map[symbol], symbol))

                name_id = name_id_map[symbol]

                # 创建 callchain_id（每个符号一个调用链）
                callchain_id = callchain_id_counter
                callchain_id_counter += 1

                # 插入到 perf_callchain 表（简化：每个符号一个调用链节点，depth=0）
                cursor.execute('''
                    INSERT INTO perf_callchain (
                        callchain_id, depth, ip, vaddr_in_file, offset_to_vaddr,
                        file_id, symbol_id, name, source_file_id, line_number
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    callchain_id,  # callchain_id
                    0,  # depth
                    offset,  # ip (使用偏移量)
                    offset,  # vaddr_in_file
                    0,  # offset_to_vaddr
                    file_id,  # file_id
                    -1,  # symbol_id (-1 表示缺失符号)
                    name_id,  # name (指向 data_dict)
                    None,  # source_file_id
                    None,  # line_number
                ))

                # 插入到 perf_sample 表（使用统计信息）
                cursor.execute('''
                    INSERT INTO perf_sample (callchain_id, file_id, symbol, event_count, call_count)
                    VALUES (?, ?, ?, ?, ?)
                ''', (callchain_id, file_id, symbol, event_count, call_count))

                # 插入到 missing_symbols 表（使用统计信息）
                cursor.execute('''
                    INSERT OR IGNORE INTO missing_symbols (address, so_file, offset, call_count, event_count)
                    VALUES (?, ?, ?, ?, ?)
                ''', (symbol, so_file, offset, call_count, event_count))

        conn.commit()
        conn.close()

        logger.info(f'✅ 创建 perf.db 完成，包含 {len(symbols)} 个符号地址')
        logger.info(f'   创建了 {len(file_id_map)} 个文件映射')
        logger.info(f'   创建了 {len(name_id_map)} 个地址映射')
        return perf_db_file

    def process_all_html_files(self) -> Tuple[Path, Dict[str, Set[str]]]:
        """
        处理所有 HTML 文件，提取符号并创建 perf.db

        Returns:
            (perf_db_file, html_symbols_dict) 元组
        """
        logger.info('=' * 80)
        logger.info('内存模式火焰图分析：提取符号地址')
        logger.info('=' * 80)

        # 收集所有符号和统计信息
        html_symbols, total_symbol_stats = self.collect_all_symbols()

        # 合并所有符号
        all_symbols = set()
        for symbols in html_symbols.values():
            all_symbols.update(symbols)

        if not all_symbols:
            logger.error('❌ 未找到任何符号地址')
            raise ValueError('未找到任何符号地址')

        # 创建 perf.db（传入统计信息）
        perf_db_file = self.create_perf_db_from_symbols(all_symbols, total_symbol_stats)

        return perf_db_file, html_symbols

