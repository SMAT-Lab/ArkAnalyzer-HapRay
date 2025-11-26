#!/usr/bin/env python3
"""
替换 perf HTML 报告中的缺失符号为 LLM 推断的函数名
"""

import base64
import gzip
import json
import re
import zlib
from pathlib import Path

import pandas as pd

from core.utils import config
from core.utils import common as util
from core.utils.logger import get_logger

logger = get_logger(__name__)


def format_function_name(function_name: str) -> str:
    """
    格式化函数名，添加 "Function: " 前缀
    
    Args:
        function_name: 原始函数名
    
    Returns:
        格式化后的函数名（如果为空则返回空字符串）
    """
    if not function_name or function_name == 'nan' or function_name == 'None':
        return ''
    # 如果已经有 "Function: " 前缀，不再添加
    if function_name.startswith('Function: '):
        return function_name
    return f'Function: {function_name}'


def load_function_mapping(excel_file):
    """从 Excel 文件加载地址到函数名的映射（精确匹配）
    
    由于地址来自 perf 采样，与分析时的地址一致，只需要精确匹配。
    """
    df = pd.read_excel(excel_file, engine='openpyxl')

    # 创建映射：地址 -> 函数名（添加 "Function: " 前缀）
    mapping = {}
    for _, row in df.iterrows():
        address = str(row.get('地址', '')).strip()
        function_name = str(row.get('LLM推断函数名', '')).strip()

        if address and function_name and function_name != 'nan' and function_name:
            # 格式化函数名，添加 "Function: " 前缀
            formatted_name = format_function_name(function_name)
            mapping[address] = formatted_name

    logger.info(f'✅ 加载了 {len(mapping)} 个函数名映射')
    return mapping


def load_excel_data_for_report(excel_file):
    """从 Excel 文件加载完整数据用于生成报告"""
    df = pd.read_excel(excel_file, engine='openpyxl')
    
    results = []
    for _, row in df.iterrows():
        # 处理 event_count 列名（可能有空格或没有空格）
        event_count = 0
        if '指令数(event_count)' in row:
            event_count = row.get('指令数(event_count)', 0)
        elif '指令数 (event_count)' in row:
            event_count = row.get('指令数 (event_count)', 0)
        
        # 处理字符串常量（可能是 NaN）
        strings_value = row.get('字符串常量', '')
        if pd.isna(strings_value):
            strings_value = ''
        else:
            strings_value = str(strings_value)
        
        # 处理指令数量（可能是 '指令数' 列）
        instruction_count = row.get('指令数', 0)
        if pd.isna(instruction_count):
            instruction_count = 0
        
        # 处理调用的函数（可能是逗号分隔的字符串）
        called_functions_str = str(row.get('调用的函数', ''))
        called_functions = []
        if called_functions_str and called_functions_str != 'nan':
            called_functions = [f.strip() for f in called_functions_str.split(',') if f.strip()]
        
        # 格式化函数名，添加 "Function: " 前缀
        function_name = str(row.get('LLM推断函数名', ''))
        if function_name and function_name != 'nan' and function_name != 'None':
            function_name = format_function_name(function_name)
        
        # 处理负载问题识别与优化建议（可能是 NaN）
        performance_analysis = row.get('负载问题识别与优化建议', '')
        if pd.isna(performance_analysis):
            performance_analysis = ''
        else:
            performance_analysis = str(performance_analysis)
        
        result = {
            'rank': row.get('排名', ''),
            'file_path': str(row.get('文件路径', '')),
            'address': str(row.get('地址', '')),
            'offset': str(row.get('偏移量', '')),
            'call_count': row.get('调用次数', 0),
            'instruction_count': int(instruction_count) if instruction_count else 0,
            'event_count': int(event_count) if event_count else 0,
            'strings': strings_value,
            'called_functions': called_functions,  # 添加调用的函数列表
            'llm_result': {
                'function_name': function_name,
                'functionality': str(row.get('LLM功能描述', '')),
                'performance_analysis': performance_analysis,  # 添加负载问题识别与优化建议
                'confidence': str(row.get('LLM置信度', '')),
            }
        }
        results.append(result)
    
    return results


def extract_symbol_from_address(address_str):
    """从地址字符串中提取符号部分（如 libxwebcore.so+0x50338a0 或 libtaobaoavsdk_bridge.so+0x1243ac）"""
    # 匹配 lib*.so+0x... 格式（支持下划线，如 libtaobaoavsdk_bridge.so）
    match = re.search(r'(lib[\w_]+\.so\+0x[0-9a-fA-F]+)', address_str, re.IGNORECASE)
    if match:
        return match.group(1)
    return None


def replace_symbols_in_html(html_content, function_mapping):
    """在 HTML 内容中替换缺失符号（优化版本，只处理 JSON 数据部分）"""

    # 统计信息
    replaced_count = {'count': 0}
    replacement_info = []

    # 提取地址部分（如 libxwebcore.so+0x50338a0 或 libtaobaoavsdk_bridge.so+0x1de430）
    def extract_address(full_path):
        """从完整路径中提取地址部分（支持任何 .so 文件，包括下划线）"""
        # 使用 [\w_]+ 来匹配包含下划线的库名，如 libtaobaoavsdk_bridge.so
        match = re.search(r'(lib[\w_]+\.so\+0x[0-9a-fA-F]+)', full_path, re.IGNORECASE)
        return match.group(1) if match else None

    # 优化：优先处理 <script id="record_data"> 标签中的 JSON 数据
    # 这是 Chart Statistics 使用的数据源
    record_data_pattern = r'(<script id="record_data"[^>]*>)(.*?)(</script>)'
    record_data_match = re.search(record_data_pattern, html_content, re.DOTALL | re.IGNORECASE)

    # 也检查 <script id="record_bz_data"> 标签（压缩的 JSON 数据）
    if not record_data_match:
        record_bz_data_pattern = r'(<script[^>]*id=["\']record_bz_data["\'][^>]*>)(.*?)(</script>)'
        record_data_match = re.search(record_bz_data_pattern, html_content, re.DOTALL | re.IGNORECASE)

    json_match = None
    data_content = None
    data_prefix = ''
    data_suffix = ''

    if record_data_match:
        logger.info('找到 <script id="record_data"> 数据块，优先处理这部分...')
        data_prefix = record_data_match.group(1)
        data_content_raw = record_data_match.group(2).strip()  # 原始数据内容
        data_suffix = record_data_match.group(3)

        # 检查数据是否被编码/压缩
        data_content = None
        is_compressed = False
        compression_format = None

        # 检查是否是 base64 编码
        if not data_content_raw.startswith('{') and not data_content_raw.startswith('['):
            logger.info('  检测到数据可能被编码/压缩，尝试解码...')
            try:
                # 尝试 base64 解码
                decoded = base64.b64decode(data_content_raw)
                logger.info(f'  ✅ Base64 解码成功，大小: {len(decoded) / 1024 / 1024:.2f} MB')

                # 检查是否是 gzip
                if decoded[:2] == b'\x1f\x8b':
                    logger.info('  ✅ 检测到 gzip 压缩，正在解压...')
                    decompressed = gzip.decompress(decoded)
                    data_content = decompressed.decode('utf-8', errors='ignore')
                    is_compressed = True
                    compression_format = 'gzip'
                    logger.info(f'  ✅ Gzip 解压成功，大小: {len(data_content) / 1024 / 1024:.2f} MB')
                # 检查是否是 zlib
                elif decoded[:2] in (b'x\x9c', b'x\xda', b'x\x01'):
                    logger.info('  ✅ 检测到 zlib 压缩，正在解压...')
                    decompressed = zlib.decompress(decoded)
                    data_content = decompressed.decode('utf-8', errors='ignore')
                    is_compressed = True
                    compression_format = 'zlib'
                    logger.info(f'  ✅ Zlib 解压成功，大小: {len(data_content) / 1024 / 1024:.2f} MB')
                else:
                    compression_format = None
                    # 直接尝试作为 UTF-8 字符串
                    try:
                        data_content = decoded.decode('utf-8', errors='ignore')
                        logger.info('  ✅ 解码为 UTF-8 字符串')
                    except Exception:
                        logger.info('  ⚠️  无法解码，使用原始数据')
                        data_content = data_content_raw
            except Exception as e:
                logger.info(f'  ⚠️  解码失败: {e}，使用原始数据')
                data_content = data_content_raw
        else:
            # 已经是 JSON 格式
            data_content = data_content_raw

        # 优化：只处理 SymbolMap 部分，而不是整个 JSON
        # 在 data_content 中查找 SymbolMap
        symbol_map_start = data_content.find('"SymbolMap"')
        if symbol_map_start == -1:
            symbol_map_start = data_content.find('"functionMap"')  # 可能是压缩格式

        if symbol_map_start != -1:
            logger.info('在 record_data 中找到 SymbolMap，只处理这部分...')
            # 找到 SymbolMap 的开始和结束位置
            brace_start = data_content.find('{', symbol_map_start)
            brace_count = 0
            symbol_map_end = brace_start

            # 优化：限制搜索范围，避免处理过大的数据
            max_search = min(len(data_content), brace_start + 10000000)  # 最多10MB
            logger.info(f'  搜索 SymbolMap 边界（范围: {max_search - brace_start} 字节）...')

            for i in range(brace_start, max_search):
                if data_content[i] == '{':
                    brace_count += 1
                elif data_content[i] == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        symbol_map_end = i + 1
                        break

                # 每处理 1MB 输出一次进度
                if (i - brace_start) % 1000000 == 0 and i > brace_start:
                    logger.info(f'    搜索进度: {(i - brace_start) / 1024 / 1024:.1f} MB')

            if brace_count != 0:
                logger.info('  ⚠️  警告: 未找到完整的 SymbolMap 边界，使用整个 record_data')
                symbol_map_end = len(data_content)

            # 只替换 SymbolMap 部分
            symbol_map_content = data_content[symbol_map_start:symbol_map_end]

            # 创建一个匹配对象
            class SymbolMapMatch:
                def __init__(
                    self,
                    full_start,
                    full_end,
                    prefix,
                    suffix,
                    content_before,
                    symbol_map,
                    content_after,
                ):
                    self._full_start = full_start
                    self._full_end = full_end
                    self._prefix = prefix
                    self._suffix = suffix
                    self._content_before = content_before
                    self._symbol_map = symbol_map
                    self._content_after = content_after

                def start(self):
                    return self._full_start

                def end(self):
                    return self._full_end

                def get_parts(self):
                    return (
                        self._prefix,
                        self._content_before,
                        self._symbol_map,
                        self._content_after,
                        self._suffix,
                    )

            json_match = SymbolMapMatch(
                record_data_match.start(),
                record_data_match.end(),
                data_prefix,
                data_suffix,
                data_content[:symbol_map_start],
                symbol_map_content,
                data_content[symbol_map_end:],
            )
            # 标记是否压缩和压缩格式，用于后续处理
            json_match._is_compressed = is_compressed
            json_match._compression_format = compression_format
        else:
            logger.info('在 record_data 中未找到 SymbolMap，处理整个 JSON...')

            # 回退到处理整个 JSON
            class RecordDataMatch:
                def __init__(self, start, end, prefix, content, suffix, compressed=False):
                    self._start = start
                    self._end = end
                    self._prefix = prefix
                    self._content = content
                    self._suffix = suffix
                    self._is_compressed = compressed

                def start(self):
                    return self._start

                def end(self):
                    return self._end

                def group(self, n):
                    if n == 1:
                        return self._prefix
                    if n == 2:
                        return self._content
                    return ''

            json_match = RecordDataMatch(
                record_data_match.start(),
                record_data_match.end(),
                data_prefix,
                data_content,
                data_suffix,
                is_compressed,
            )
            # 标记压缩格式
            json_match._compression_format = compression_format

    # 如果没找到 record_data，尝试查找其他 JSON 数据块
    if not json_match:
        # 查找包含 SymbolMap 的 JSON 对象
        # 先尝试查找内联的 JSON 对象（可能很大，需要找到完整的对象）
        # 查找 "SymbolMap" 的位置
        symbol_map_pos = html_content.find('"SymbolMap"')
        if symbol_map_pos != -1:
            # 向前查找 JSON 对象的开始
            json_start = symbol_map_pos
            while json_start > 0 and html_content[json_start] != '{':
                json_start -= 1
                if json_start < symbol_map_pos - 1000000:  # 最多向前查找1MB
                    break

            if json_start >= 0 and html_content[json_start] == '{':
                # 找到 JSON 对象的开始，现在找到结束位置（优化：添加进度提示）
                brace_count = 0
                json_end = json_start
                max_search = min(len(html_content), json_start + 10000000)  # 最多10MB
                logger.info(f'  搜索 JSON 对象边界（范围: {max_search - json_start} 字节）...')

                for i in range(json_start, max_search):
                    if html_content[i] == '{':
                        brace_count += 1
                    elif html_content[i] == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            json_end = i + 1
                            break

                    # 每处理 1MB 输出一次进度
                    if (i - json_start) % 1000000 == 0 and i > json_start:
                        logger.info(f'    搜索进度: {(i - json_start) / 1024 / 1024:.1f} MB')

                if brace_count != 0:
                    logger.info('  ⚠️  警告: 未找到完整的 JSON 对象边界')
                    json_end = min(len(html_content), json_start + 10000000)

                if json_end > json_start:
                    # 检查前面是否有赋值语句
                    prefix_start = max(0, json_start - 200)
                    prefix_text = html_content[prefix_start:json_start]

                    # 查找赋值语句
                    assign_match = re.search(
                        r'(window\.data\s*=\s*|(?:const|let|var)\s+json\s*=\s*)$',
                        prefix_text,
                        re.MULTILINE,
                    )
                    if assign_match:
                        # 找到赋值语句，创建匹配对象
                        class InlineJsonMatch:
                            def __init__(self, start, end, prefix, content):
                                self._start = start
                                self._end = end
                                self._prefix = prefix
                                self._content = content

                            def start(self):
                                return self._start

                            def end(self):
                                return self._end

                            def group(self, n):
                                if n == 1:
                                    return self._prefix
                                if n == 2:
                                    return self._content
                                return ''

                        json_match = InlineJsonMatch(
                            json_start,
                            json_end,
                            html_content[prefix_start:json_start],
                            html_content[json_start:json_end],
                        )

        # 如果还没找到，尝试其他格式
        if not json_match:
            json_patterns = [
                r'(window\.data\s*=\s*)(\{.*?"SymbolMap".*?\});',
                r'((?:const|let|var)\s+json\s*=\s*)(\{.*?"SymbolMap".*?\});',
            ]

            for pattern in json_patterns:
                match = re.search(pattern, html_content, re.DOTALL | re.IGNORECASE)
                if match:
                    json_match = match
                    break

    if json_match:
        logger.info('找到 JSON 数据块，只处理这部分...')

        # 判断是 SymbolMapMatch 还是其他类型
        if hasattr(json_match, 'get_parts'):
            # SymbolMapMatch 对象 - 只处理 SymbolMap 部分
            (
                data_prefix,
                content_before,
                symbol_map_content,
                content_after,
                data_suffix,
            ) = json_match.get_parts()
            data_content_to_replace = symbol_map_content
            is_symbol_map_only = True
        elif hasattr(json_match, '_content'):
            # RecordDataMatch 对象
            data_prefix = json_match._prefix
            data_content_to_replace = json_match._content
            data_suffix = json_match._suffix
            content_before = ''
            content_after = ''
            is_symbol_map_only = False
        elif hasattr(json_match, 'group'):
            # 正则匹配对象
            data_prefix = json_match.group(1) if json_match.group(1) else ''
            data_content_to_replace = json_match.group(2)
            data_suffix = ''
            content_before = ''
            content_after = ''
            is_symbol_map_only = False
        else:
            data_prefix = ''
            data_content_to_replace = html_content[json_match.start() : json_match.end()]
            data_suffix = ''
            content_before = ''
            content_after = ''
            is_symbol_map_only = False

        # 只在这个数据块中进行替换（支持所有 .so 文件）
        so_addresses = function_mapping  # 使用所有地址映射，不再只过滤 libxwebcore.so
        total_addresses = len(so_addresses)
        logger.info(f'  需要处理 {total_addresses} 个地址映射')
        logger.info(f'  JSON 数据块大小: {len(data_content_to_replace) / (1024 * 1024):.2f} MB')

        # 优化：先使用方法1批量替换 symbol 字段，这是最常见的格式
        logger.info('  步骤 1/3: 批量替换 symbol 字段...')

        def replace_in_symbol_field(match):
            prefix = match.group(1)  # "symbol": " 或 "f": "
            symbol_value = match.group(2)  # 符号值

            # 如果已经替换过，跳过
            if '[反推，仅供参考]' in symbol_value:
                return match.group(0)

            # 提取地址部分（可能是完整路径或简单地址）
            address = extract_address(symbol_value)
            if not address:
                return match.group(0)
            
            # 只进行精确匹配（地址来自 perf 采样，与分析时的地址一致）
            matched_function = None
            matched_address = None
            
            if address in so_addresses:
                matched_function = so_addresses[address]
                matched_address = address
            
            if matched_function and matched_address:
                replaced_count['count'] += 1
                if matched_address not in [r['original'] for r in replacement_info]:
                    replacement_info.append({'original': matched_address, 'replaced': matched_function})
                # 在替换后保留原始地址，便于追溯
                return f'{prefix}{matched_function} [反推，仅供参考] ({address})"'
            return match.group(0)

        # 匹配 symbol 字段（完整格式和压缩格式）
        symbol_pattern = r'("(?:symbol|f)"\s*:\s*")([^"]*lib[\w_]+\.so\+0x[0-9a-fA-F]+[^"]*)"'
        data_content_to_replace = re.sub(
            symbol_pattern, replace_in_symbol_field, data_content_to_replace, flags=re.IGNORECASE
        )
        logger.info(f'  步骤 1 完成，已替换 {replaced_count["count"]} 个符号')

        # 方法2: 替换完整路径格式（优化：只处理未被方法1替换的地址）
        logger.info('  步骤 2/3: 替换完整路径格式...')
        existing_replacements = {r['original'] for r in replacement_info}
        # 获取尚未替换的地址
        remaining_addresses = {
            addr: func_name for addr, func_name in so_addresses.items()
            if addr not in existing_replacements
        }
        if remaining_addresses:
            logger.info(f'  剩余 {len(remaining_addresses)} 个地址需要处理...')
            logger.info(
                f'  注意: 由于 JSON 数据块较大（{len(data_content_to_replace) / (1024 * 1024):.2f} MB），处理可能需要一些时间...'
            )
            total_patterns = len(remaining_addresses) * 3  # 每个地址3个模式
            pattern_count = 0

            for processed, (address, function_name) in enumerate(remaining_addresses.items(), 1):
                logger.info(f'    处理地址 {processed}/{len(remaining_addresses)}: {address[:50]}...')

                # 优化：使用更简单的模式，避免复杂的正则
                # 直接替换地址字符串（转义特殊字符）
                escaped_address = re.escape(address)

                # 模式1: 完整路径格式
                pattern_count += 1
                logger.info(f'      模式 1/3: 完整路径格式 ({pattern_count}/{total_patterns})...')
                pattern_full = rf'([^"]*/proc/[^"]*/)([^"]*libs/arm64/)({escaped_address})'

                def replace_full_path(m, fn=function_name, addr=address):
                    if '[反推，仅供参考]' in m.group(0):
                        return m.group(0)
                    replaced_count['count'] += 1
                    # 在替换后保留原始地址，便于追溯
                    return f'{m.group(1)}{m.group(2)}{fn} [反推，仅供参考] ({addr})'

                data_content_to_replace = re.sub(pattern_full, replace_full_path, data_content_to_replace)

                # 模式2: 简单格式（在引号内）
                pattern_count += 1
                logger.info(f'      模式 2/3: 简单格式 ({pattern_count}/{total_patterns})...')
                pattern_simple = rf'(")({escaped_address})(")'

                def replace_simple(m, fn=function_name, addr=address):
                    if '[反推，仅供参考]' in m.group(0):
                        return m.group(0)
                    replaced_count['count'] += 1
                    # 在替换后保留原始地址，便于追溯
                    return f'{m.group(1)}{fn} [反推，仅供参考] ({addr}){m.group(3)}'

                data_content_to_replace = re.sub(pattern_simple, replace_simple, data_content_to_replace)

                # 模式3: symbol 字段中的完整路径
                pattern_count += 1
                logger.info(f'      模式 3/3: symbol 字段 ({pattern_count}/{total_patterns})...')
                pattern_in_symbol = rf'("(?:symbol|f)"\s*:\s*")([^"]*{escaped_address}[^"]*)"'

                def replace_in_symbol_direct(m, fn=function_name, addr=address):
                    if '[反推，仅供参考]' in m.group(2):
                        return m.group(0)
                    replaced_count['count'] += 1
                    # 在替换后保留原始地址，便于追溯
                    return f'{m.group(1)}{fn} [反推，仅供参考] ({addr})"'

                data_content_to_replace = re.sub(pattern_in_symbol, replace_in_symbol_direct, data_content_to_replace)

                logger.info(f'    ✅ 地址 {processed} 处理完成（已替换 {replaced_count["count"]} 个符号）')

        logger.info(f'  步骤 2 完成，总共替换了 {replaced_count["count"]} 个符号')
        logger.info('  步骤 3/3: 完成替换')

        # 如果数据被压缩，需要重新压缩和编码
        # 检查 json_match 是否有 _is_compressed 属性
        is_compressed_flag = getattr(json_match, '_is_compressed', False) if json_match else False
        compression_format = getattr(json_match, '_compression_format', 'gzip') if json_match else 'gzip'

        if is_compressed_flag:
            logger.info('  重新压缩和编码数据...')
            try:
                # 如果是 SymbolMapMatch，需要压缩整个 JSON（包括 content_before 和 content_after）
                # 否则只压缩 data_content_to_replace
                if is_symbol_map_only:
                    # 构建完整的 JSON 内容用于压缩
                    full_json_content = content_before + data_content_to_replace + content_after
                    logger.info(
                        f'  压缩完整 JSON（包括 SymbolMap 前后内容），大小: {len(full_json_content) / 1024 / 1024:.2f} MB'
                    )
                else:
                    full_json_content = data_content_to_replace

                # 根据原始压缩格式选择压缩方法
                if compression_format == 'zlib':
                    logger.info('  使用 zlib 压缩...')
                    compressed = zlib.compress(full_json_content.encode('utf-8'))
                else:
                    logger.info('  使用 gzip 压缩...')
                    compressed = gzip.compress(full_json_content.encode('utf-8'))

                # Base64 编码
                encoded = base64.b64encode(compressed).decode('utf-8')

                # 更新 data_content_to_replace
                # 压缩后的数据是完整的 JSON（对于 SymbolMapMatch）或部分 JSON（对于其他模式）
                data_content_to_replace = encoded

                logger.info(f'  ✅ 重新压缩和编码完成，大小: {len(encoded) / 1024 / 1024:.2f} MB')
            except Exception:
                logger.exception('  ⚠️  重新压缩失败，使用未压缩的数据')

        # 替换回原文件
        start_pos = json_match.start() if hasattr(json_match, 'start') else 0
        end_pos = json_match.end() if hasattr(json_match, 'end') else len(html_content)

        if is_symbol_map_only:
            # SymbolMapMatch - 只替换 SymbolMap 部分
            # 如果压缩了，data_content_to_replace 是压缩后的整个 JSON
            if is_compressed_flag:
                # 压缩模式下，data_content_to_replace 已经是压缩后的整个 JSON
                # 需要替换整个 record_data 内容
                html_content = (
                    html_content[:start_pos]
                    + data_prefix
                    + data_content_to_replace
                    + data_suffix
                    + html_content[end_pos:]
                )
            else:
                # 未压缩模式，正常替换
                html_content = (
                    html_content[:start_pos]
                    + data_prefix
                    + content_before
                    + data_content_to_replace
                    + content_after
                    + data_suffix
                    + html_content[end_pos:]
                )
        elif hasattr(json_match, '_suffix'):
            # RecordDataMatch 对象，需要包含 suffix
            html_content = (
                html_content[:start_pos] + data_prefix + data_content_to_replace + data_suffix + html_content[end_pos:]
            )
        else:
            html_content = html_content[:start_pos] + data_prefix + data_content_to_replace + html_content[end_pos:]
    else:
        # 如果找不到 window.data，回退到全文件替换（但只替换 symbol 字段）
        logger.info('未找到 window.data，使用全文件替换模式...')
        so_addresses = function_mapping  # 使用所有地址映射，不再只过滤 libxwebcore.so

        def replace_in_symbol_field(match):
            prefix = match.group(1)
            symbol_value = match.group(2)
            address = extract_address(symbol_value)
            if address and address in so_addresses:
                function_name = so_addresses[address]
                replaced_count['count'] += 1
                if address not in [r['original'] for r in replacement_info]:
                    replacement_info.append({'original': address, 'replaced': function_name})
                # 在替换后保留原始地址，便于追溯
                return f'{prefix}{function_name} [反推，仅供参考] ({address})"'
            return match.group(0)

        # 匹配 symbol 字段（完整格式和压缩格式 "f"，支持任何 .so 文件，包括下划线）
        symbol_pattern = r'("(?:symbol|f)"\s*:\s*")([^"]*lib[\w_]+\.so\+0x[0-9a-fA-F]+[^"]*)"'
        html_content = re.sub(symbol_pattern, replace_in_symbol_field, html_content, flags=re.IGNORECASE)

    logger.info(f'✅ 替换了 {replaced_count["count"]} 个缺失符号')
    return html_content, replacement_info


def extract_html_body_content(html_file_path: Path) -> str:
    """从 HTML 文件中提取 body 内容（不包括 body 标签本身）"""
    try:
        with open(html_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 提取 <body> 标签内的内容
        body_match = re.search(r'<body[^>]*>(.*?)</body>', content, re.DOTALL | re.IGNORECASE)
        if body_match:
            return body_match.group(1).strip()
        
        # 如果没有 body 标签，尝试提取整个文档内容（除了 html/head 标签）
        html_match = re.search(r'</head>(.*?)</html>', content, re.DOTALL | re.IGNORECASE)
        if html_match:
            return html_match.group(1).strip()
        
        # 如果都没有，返回空字符串
        return ''
    except Exception as e:
        logger.warning(f'无法读取 HTML 报告文件 {html_file_path}: {e}')
        return ''


def add_disclaimer(html_content, reference_report_file=None, relative_path=None, 
                   html_report_file=None, excel_file=None, report_data=None, llm_analyzer=None):
    """在 HTML 中添加免责声明、参考链接和嵌入的报告

    Args:
        html_content: HTML 内容
        reference_report_file: 技术参考报告文件名（如 event_count_top33_report.html），
                               如果为 None，则自动查找
        relative_path: 从 HTML 文件到输出目录的相对路径
                      如果为 None，则自动计算或使用默认路径
        html_report_file: HTML 报告文件路径（可选，如果提供则嵌入报告内容）
        excel_file: Excel 文件路径（可选，如果提供则添加下载链接）
    """
    # 获取输出目录
    output_dir = config.get_output_dir()
    config.ensure_output_dir(output_dir)

    # 确定相对路径
    if relative_path is None:
        # 默认相对路径
        relative_path = f'../{output_dir.name}'
    elif relative_path == '.':
        # 当前目录，不需要前缀
        relative_path = ''

    # 确定参考报告文件
    if reference_report_file:
        reference_link = f'{relative_path}/{reference_report_file}' if relative_path else reference_report_file
    # 自动查找最新的报告文件
    elif output_dir.exists():
        # 查找所有报告文件，按修改时间排序
        report_files = list(output_dir.glob('*_report.html'))
        if report_files:
            # 按修改时间排序，取最新的
            report_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
            reference_link = f'{relative_path}/{report_files[0].name}' if relative_path else report_files[0].name
        # 如果没有找到，使用默认名称
        elif relative_path:
            reference_link = f'{relative_path}/{config.EVENT_COUNT_REPORT_PATTERN.format(n=config.DEFAULT_TOP_N)}'
        else:
            reference_link = config.EVENT_COUNT_REPORT_PATTERN.format(n=config.DEFAULT_TOP_N)
    elif relative_path:
        reference_link = f'{relative_path}/{config.EVENT_COUNT_REPORT_PATTERN.format(n=config.DEFAULT_TOP_N)}'
    else:
        reference_link = config.EVENT_COUNT_REPORT_PATTERN.format(n=config.DEFAULT_TOP_N)

    # 构建 Excel 下载链接
    excel_link = ''
    if excel_file:
        excel_path = Path(excel_file)
        if excel_path.exists():
            excel_link_path = f'{relative_path}/{excel_path.name}' if relative_path else excel_path.name
            excel_link = f'''
        <strong>📊 Excel 报告:</strong><br>
        <a href="{excel_link_path}" download
           style="color: #1976d2; text-decoration: underline; font-weight: bold;">
           下载 Excel 分析报告
        </a><br><br>'''

    # 不再显示免责声明框
    disclaimer = ""

    # 生成报告内容（优先使用 report_data，否则从文件读取）
    report_body_content = ''
    if report_data:
        # 直接从数据生成报告内容
        full_html = util.render_html_report(
            report_data,
            llm_analyzer=llm_analyzer,
            time_tracker=None,
            title='缺失符号函数分析报告',
        )
        # 提取 body 内容
        body_match = re.search(r'<body[^>]*>(.*?)</body>', full_html, re.DOTALL | re.IGNORECASE)
        if body_match:
            report_body_content = body_match.group(1).strip()
    elif html_report_file:
        html_report_path = Path(html_report_file)
        if html_report_path.exists():
            report_body_content = extract_html_body_content(html_report_path)
    
    # 嵌入 HTML 报告内容（如果提供）
    embedded_report = ''
    if report_body_content:
        # 转义 JavaScript 字符串中的特殊字符
        report_body_content_escaped = json.dumps(report_body_content)
        
        embedded_report = f"""
    <!-- 添加新的 tab 来显示详细分析报告 -->
    <script>
        (function() {{
            function addReportTab() {{
                // 查找 lit-tabs 元素
                var tabs = document.querySelector('lit-tabs');
                if (!tabs) {{
                    // 如果找不到，延迟重试
                    setTimeout(addReportTab, 500);
                    return;
                }}
                
                // 检查是否已经添加过
                var existingPane = tabs.querySelector('lit-tabpane[key="5"]');
                if (existingPane) {{
                    return;
                }}
                
                // 创建新的 tabpane
                var newPane = document.createElement('lit-tabpane');
                newPane.setAttribute('id', 'pane5');
                newPane.setAttribute('tab', '详细分析报告');
                newPane.setAttribute('key', '5');
                
                // 将报告内容添加到 tabpane 中
                var reportContent = {report_body_content_escaped};
                
                // 创建容器并添加样式
                var container = document.createElement('div');
                container.style.cssText = 'padding: 20px; background: white; min-height: 100vh;';
                
                // 创建样式元素
                var styleElement = document.createElement('style');
                styleElement.textContent = '.container {{ max-width: 100%; margin: 0; background: white; padding: 20px; box-sizing: border-box; }} ' +
                    'h1 {{ color: #333; border-bottom: 3px solid #4CAF50; padding-bottom: 10px; margin-top: 0; }} ' +
                    'table {{ width: 100%; border-collapse: collapse; margin-top: 20px; table-layout: auto; }} ' +
                    'th {{ background-color: #4CAF50; color: white; padding: 12px 8px; text-align: left; position: sticky; top: 0; white-space: nowrap; font-size: 13px; }} ' +
                    'td {{ padding: 10px 8px; border-bottom: 1px solid #ddd; vertical-align: top; font-size: 13px; word-wrap: break-word; }} ' +
                    'tr:hover {{ background-color: #f5f5f5; }} ' +
                    '.rank {{ font-weight: bold; color: #4CAF50; text-align: center; width: 50px; }} ' +
                    '.address {{ font-family: "Courier New", monospace; font-size: 0.85em; white-space: nowrap; max-width: 200px; overflow: hidden; text-overflow: ellipsis; }} ' +
                    '.call-count {{ text-align: right; font-weight: bold; white-space: nowrap; }} ' +
                    '.confidence-high {{ color: #4CAF50; font-weight: bold; }} ' +
                    '.confidence-medium {{ color: #FF9800; font-weight: bold; }} ' +
                    '.confidence-low {{ color: #f44336; }} ' +
                    '.functionality {{ max-width: 400px; word-wrap: break-word; line-height: 1.4; }} ' +
                    '.strings {{ font-family: "Courier New", monospace; font-size: 0.85em; max-width: 300px; word-wrap: break-word; line-height: 1.4; }} ' +
                    '.section {{ margin-top: 40px; padding: 20px; background-color: #f9f9f9; border-radius: 5px; border-left: 4px solid #4CAF50; }} ' +
                    '.section h2 {{ color: #333; margin-top: 0; border-bottom: 2px solid #4CAF50; padding-bottom: 10px; }} ' +
                    '.token-stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-top: 15px; }} ' +
                    '.token-stat-item {{ background: white; padding: 15px; border-radius: 5px; border: 1px solid #ddd; }} ' +
                    '.token-stat-label {{ font-size: 0.9em; color: #666; margin-bottom: 5px; }} ' +
                    '.token-stat-value {{ font-size: 1.5em; font-weight: bold; color: #4CAF50; }} ' +
                    'td:nth-child(2) {{ max-width: 250px; }} ' +
                    'td:nth-child(9) {{ max-width: 350px; }} ' +
                    'td:nth-child(10) {{ max-width: 400px; }}';
                container.appendChild(styleElement);
                
                // 插入报告内容
                container.innerHTML += reportContent;
                newPane.appendChild(container);
                
                // 添加到 tabs 中
                tabs.appendChild(newPane);
            }}
            
            // 页面加载后执行
            if (document.readyState === 'loading') {{
                document.addEventListener('DOMContentLoaded', addReportTab);
            }} else {{
                addReportTab();
            }}
            
            // 延迟执行，确保所有内容都已加载
            setTimeout(addReportTab, 500);
            setTimeout(addReportTab, 1000);
        }})();
    </script>
    """

    # 插入样式和脚本（在 head 或 body 开始处）
    layout_style_script = ''
    if embedded_report:
        # 提取样式和脚本部分
        style_match = re.search(r'<style>(.*?)</style>', embedded_report, re.DOTALL)
        script_match = re.search(r'<script>(.*?)</script>', embedded_report, re.DOTALL)
        
        if style_match:
            layout_style_script += f'<style>{style_match.group(1)}</style>'
        if script_match:
            layout_style_script += f'<script>{script_match.group(1)}</script>'
    
    # 插入布局样式和脚本到 head 或 body 开始处
    if layout_style_script:
        if '</head>' in html_content:
            html_content = html_content.replace('</head>', layout_style_script + '</head>')
        elif '<body' in html_content:
            body_match = re.search(r'(<body[^>]*>)', html_content, re.IGNORECASE)
            if body_match:
                html_content = html_content.replace(body_match.group(1), body_match.group(1) + layout_style_script)
    
    # 提取报告容器部分（不包含样式和脚本）
    report_container = ''
    if embedded_report:
        container_match = re.search(r'(<div id="embedded-report-container".*?</div>)', embedded_report, re.DOTALL)
        if container_match:
            report_container = container_match.group(1)
    
    # 在 </body> 标签前插入声明和报告容器
    insertion_content = disclaimer + report_container
    if '</body>' in html_content:
        html_content = html_content.replace('</body>', insertion_content + '</body>')
    elif '</html>' in html_content:
        html_content = html_content.replace('</html>', insertion_content + '</html>')
    else:
        # 如果没有 body 或 html 标签，在末尾添加
        html_content += insertion_content

    return html_content
