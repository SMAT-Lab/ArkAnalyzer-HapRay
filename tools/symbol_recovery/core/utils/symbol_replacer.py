#!/usr/bin/env python3
"""
替换 perf HTML 报告中的缺失符号为 LLM 推断的函数名
"""

import base64
import gzip
import re
import zlib

import pandas as pd

from core.utils import config
from core.utils.logger import get_logger

logger = get_logger(__name__)


def load_function_mapping(excel_file):
    """从 Excel 文件加载地址到函数名的映射"""
    df = pd.read_excel(excel_file, engine='openpyxl')

    # 创建映射：地址 -> 函数名
    mapping = {}
    for _, row in df.iterrows():
        address = str(row.get('地址', '')).strip()
        function_name = str(row.get('LLM推断函数名', '')).strip()

        if address and function_name and function_name != 'nan' and function_name:
            # 提取地址部分（如 libxwebcore.so+0x50338a0）
            mapping[address] = function_name

    logger.info(f'✅ 加载了 {len(mapping)} 个函数名映射')
    return mapping


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
            if address and address in so_addresses:
                function_name = so_addresses[address]
                replaced_count['count'] += 1
                if address not in [r['original'] for r in replacement_info]:
                    replacement_info.append({'original': address, 'replaced': function_name})
                return f'{prefix}{function_name} [反推，仅供参考]"'
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
        remaining_addresses = {addr: name for addr, name in so_addresses.items() if addr not in existing_replacements}
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

                def replace_full_path(m, fn=function_name):
                    if '[反推，仅供参考]' in m.group(0):
                        return m.group(0)
                    replaced_count['count'] += 1
                    return f'{m.group(1)}{m.group(2)}{fn} [反推，仅供参考]'

                data_content_to_replace = re.sub(pattern_full, replace_full_path, data_content_to_replace)

                # 模式2: 简单格式（在引号内）
                pattern_count += 1
                logger.info(f'      模式 2/3: 简单格式 ({pattern_count}/{total_patterns})...')
                pattern_simple = rf'(")({escaped_address})(")'

                def replace_simple(m, fn=function_name):
                    if '[反推，仅供参考]' in m.group(0):
                        return m.group(0)
                    replaced_count['count'] += 1
                    return f'{m.group(1)}{fn} [反推，仅供参考]{m.group(3)}'

                data_content_to_replace = re.sub(pattern_simple, replace_simple, data_content_to_replace)

                # 模式3: symbol 字段中的完整路径
                pattern_count += 1
                logger.info(f'      模式 3/3: symbol 字段 ({pattern_count}/{total_patterns})...')
                pattern_in_symbol = rf'("(?:symbol|f)"\s*:\s*")([^"]*{escaped_address}[^"]*)"'

                def replace_in_symbol_direct(m, fn=function_name):
                    if '[反推，仅供参考]' in m.group(2):
                        return m.group(0)
                    replaced_count['count'] += 1
                    return f'{m.group(1)}{fn} [反推，仅供参考]"'

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
                return f'{prefix}{function_name} [反推，仅供参考]"'
            return match.group(0)

        # 匹配 symbol 字段（完整格式和压缩格式 "f"，支持任何 .so 文件，包括下划线）
        symbol_pattern = r'("(?:symbol|f)"\s*:\s*")([^"]*lib[\w_]+\.so\+0x[0-9a-fA-F]+[^"]*)"'
        html_content = re.sub(symbol_pattern, replace_in_symbol_field, html_content, flags=re.IGNORECASE)

    logger.info(f'✅ 替换了 {replaced_count["count"]} 个缺失符号')
    return html_content, replacement_info


def add_disclaimer(html_content, reference_report_file=None, relative_path=None):
    """在 HTML 中添加免责声明和参考链接

    Args:
        html_content: HTML 内容
        reference_report_file: 技术参考报告文件名（如 event_count_top33_report.html），
                               如果为 None，则自动查找
        relative_path: 从 HTML 文件到输出目录的相对路径
                      如果为 None，则自动计算或使用默认路径
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

    disclaimer = f"""
    <!-- 符号替换说明 -->
    <div style="position: fixed; top: 10px; right: 10px; background: #fff3cd; border: 2px solid #ffc107;
                padding: 15px; border-radius: 5px; z-index: 10000; max-width: 350px; font-size: 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.2);">
        <strong>⚠️ 符号替换说明</strong><br>
        报告中标记为 <span style="color: #d32f2f; font-weight: bold;">[反推，仅供参考]</span> 的函数名<br>
        是通过 LLM 分析反汇编代码推断的，<br>
        格式为 "Function: {{函数名}}"，<br>
        可能与实际函数名存在差异，仅供参考。<br><br>
        <strong>📚 技术参考:</strong><br>
        <a href="{reference_link}" target="_blank"
           style="color: #1976d2; text-decoration: underline; font-weight: bold;">
           查看详细分析报告（技术原理、Token统计、函数列表）
        </a>
    </div>
    """

    # 在 </body> 标签前插入声明
    if '</body>' in html_content:
        html_content = html_content.replace('</body>', disclaimer + '</body>')
    elif '</html>' in html_content:
        html_content = html_content.replace('</html>', disclaimer + '</html>')

    return html_content
