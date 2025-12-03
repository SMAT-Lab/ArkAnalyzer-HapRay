#!/usr/bin/env python3

"""
按指令数（event_count）统计 和分析函数
从perf.db 文件中读取数据，进行反汇编和LLM分析
"""

import gc
import sqlite3
from collections import defaultdict
from pathlib import Path

import pandas as pd

from core.llm.initializer import init_llm_analyzer
from core.utils import config
from core.utils.config import (
    DEFAULT_BATCH_SIZE,
    DEFAULT_TOP_N,
    EVENT_COUNT_ANALYSIS_PATTERN,
    EVENT_COUNT_REPORT_PATTERN,
    TEMP_FILE_PREFIX,
)
from core.utils.logger import get_logger
from core.utils.perf_converter import MissingSymbolFunctionAnalyzer

# 延迟导入，避免循环依赖
try:
    from core.utils.hap_address_resolver import is_hap_address, resolve_hap_addresses_batch
except ImportError:
    is_hap_address = None
    resolve_hap_addresses_batch = None

#  使用日志
logger = get_logger(__name__)


class EventCountAnalyzer:
    """事件计数分析器"""

    def __init__(
        self,
        perf_db_file,
        so_dir,
        use_llm=True,
        llm_model=None,
        batch_size=5,
        context=None,
        use_capstone_only=False,
        save_prompts=False,
        output_dir=None,
        skip_decompilation=False,
        open_source_lib=None,
    ):
        """
        初始化分析器

        Args:
            perf_db_file: perf.db 文件路径
            so_dir: SO 文件目录
            use_llm: 是否使用 LLM 分析
            llm_model: LLM 模型名称
            batch_size: 批量分析时每个 prompt 包含的函数数量（默认 3）
            context: 自定义上下文信息（可选，如果不提供则根据 SO 文件名自动推断）
            use_capstone_only: 只使用 Capstone 反汇编（不使用 Radare2，即使已安装）
            save_prompts: 是否保存生成的 prompt 到文件
            output_dir: 输出目录，用于保存 prompt 文件
            skip_decompilation: 是否跳过反编译（默认 False，启用反编译可提高 LLM 分析质量但较慢）
        """
        self.perf_db_file = Path(perf_db_file)
        self.so_dir = Path(so_dir)
        self.use_llm = use_llm
        self.llm_model = llm_model
        self.batch_size = batch_size or DEFAULT_BATCH_SIZE
        self.context = context
        self.use_capstone_only = use_capstone_only
        self.skip_decompilation = skip_decompilation

        if not self.perf_db_file.exists():
            raise FileNotFoundError(f'perf.db 不存在: {perf_db_file}')
        # 如果 so_dir 是文件（通过 --so-file 指定），允许；如果是目录，检查是否存在
        if not self.so_dir.exists():
            raise FileNotFoundError(f'SO 文件或目录不存在: {so_dir}')
        if self.so_dir.is_file() and not self.so_dir.suffix == '.so':
            raise ValueError(f'指定的文件不是 SO 文件: {so_dir}')

        # 初始化 LLM 分析器（公共工具）
        self.llm_analyzer, self.use_llm, self.use_batch_llm = init_llm_analyzer(
            use_llm=self.use_llm,
            llm_model=self.llm_model,
            batch_size=self.batch_size,
            save_prompts=save_prompts,
            output_dir=output_dir,
            open_source_lib=open_source_lib,
        )

    def analyze(self):
        """执行分析"""
        logger.info('=' * 80)
        logger.info('Analyzing top100 by event_count')
        logger.info('=' * 80)

        conn = sqlite3.connect(str(self.perf_db_file))
        cursor = conn.cursor()

        try:
            # 1. 加载映射关系
            logger.info('\nStep 1: Loading mappings...')
            cursor.execute('SELECT DISTINCT file_id, path FROM perf_files WHERE path IS NOT NULL')
            file_id_to_path = {row[0]: row[1] for row in cursor.fetchall()}
            logger.info(f'[OK] Loaded {len(file_id_to_path):,} file path mappings')

            cursor.execute('SELECT id, data FROM data_dict WHERE data IS NOT NULL')
            name_to_data = {row[0]: row[1] for row in cursor.fetchall()}
            logger.info(f'[OK] Loaded {len(name_to_data):,} address data mappings')

            # 2. 按调用次数统计 top100（现有逻辑）
            logger.info('\nStep 2: Statistics by call count top100...')
            call_count_top100 = self._get_call_count_top100(cursor, file_id_to_path, name_to_data)
            logger.info(f'[OK] Found {len(call_count_top100)} addresses (call count top100)')

            # 3. 按 event_count 求和统计 top100（新逻辑）
            logger.info('\nStep 3: Statistics by event_count sum top100...')
            # 如果 so_dir 是文件（通过 --so-file 指定），只统计该SO文件的函数
            target_so_name = None
            if self.so_dir and self.so_dir.is_file():
                target_so_name = self.so_dir.name
            
            event_count_top100 = self._get_event_count_top100(cursor, file_id_to_path, name_to_data, top_n=100, target_so_name=target_so_name)
            logger.info(f'[OK] Found {len(event_count_top100)} addresses (event_count top100)')

            # 4. 找出差异
            logger.info('\nStep 4: Finding differences...')
            call_count_keys = set(call_count_top100.keys())
            event_count_keys = set(event_count_top100.keys())

            # Addresses in event_count top100 but not in call_count top100
            diff_keys = event_count_keys - call_count_keys
            logger.info(
                f'[OK] Found {len(diff_keys)} different addresses (in event_count top100 but not in call_count top100)'
            )

            if diff_keys:
                logger.info('\nDifferent address list (top 20):')
                diff_list = sorted(
                    [(k, event_count_top100[k]) for k in diff_keys],
                    key=lambda x: x[1]['event_count'],
                    reverse=True,
                )
                for i, (_key, info) in enumerate(diff_list[:20], 1):
                    logger.info(
                        f'  {i}. {info["file_path"]} {info["address"]} - event_count: {info["event_count"]}, call_count: {info.get("call_count", 0)}'
                    )

            # 5. 对差异部分进行 LLM 分析
            if diff_keys and self.use_llm:
                logger.info('\nStep 5: LLM analysis of differences...')
                self._analyze_differences(diff_keys, event_count_top100)

            # 6. 生成报告
            logger.info('\nStep 6: Generating report...')
            self._generate_report(call_count_top100, event_count_top100, diff_keys)

        finally:
            conn.close()

    def _get_call_count_top100(self, cursor, file_id_to_path, name_to_data):
        """按调用次数统计 top100"""
        cursor.execute("""
            SELECT file_id, name, ip, depth
            FROM perf_callchain
            WHERE symbol_id = -1
        """)

        address_call_counts = defaultdict(int)
        address_info = {}

        batch_size = 100000
        while True:
            rows = cursor.fetchmany(batch_size)
            if not rows:
                break

            for file_id, name_id, ip, depth in rows:
                file_path = file_id_to_path.get(file_id, 'Unknown file')
                address_data = name_to_data.get(name_id, None)

                if address_data and file_path != 'Unknown file':
                    key = (file_path, address_data)
                    address_call_counts[key] += 1

                    if key not in address_info:
                        address_info[key] = {
                            'file_path': file_path,
                            'address': address_data,
                            'file_id': file_id,
                            'name_id': name_id,
                            'ip': ip,
                            'depth': depth,
                        }

        # 过滤和排序
        excluded_exact = ['[shmm]', 'Unknown file', '/bin/devhost.elf']
        excluded_prefixes = ['/system', '/vendor/lib64', '/lib', '/chip_prod']

        filtered = {}
        for key, count in address_call_counts.items():
            file_path, address = key
            if file_path in excluded_exact:
                continue
            if any(file_path.startswith(prefix) for prefix in excluded_prefixes):
                continue
            filtered[key] = {**address_info[key], 'call_count': count}

        # 取 top_n（使用默认值）
        sorted_items = sorted(filtered.items(), key=lambda x: x[1]['call_count'], reverse=True)
        top_n = DEFAULT_TOP_N
        return {k: v for k, v in sorted_items[:top_n]}

    def _get_event_count_top100(self, cursor, file_id_to_path, name_to_data, top_n=None, target_so_name=None):
        """按 event_count 求和统计 topN
        
        Args:
            cursor: 数据库游标
            file_id_to_path: 文件ID到路径的映射
            name_to_data: 名称ID到地址数据的映射
            top_n: 返回前N个结果
            target_so_name: 目标SO文件名（如果指定，只统计该SO文件的函数）
        """
        if top_n is None:
            top_n = DEFAULT_TOP_N
        # 查询 perf_sample 和 perf_callchain 的关联
        # 如果指定了 target_so_name，在 SQL 查询时就过滤
        if target_so_name:
            # 先找到匹配的 file_id
            cursor.execute("""
                SELECT DISTINCT file_id FROM perf_files 
                WHERE path LIKE ? OR path LIKE ?
            """, (f'%{target_so_name}', f'%/{target_so_name}'))
            matching_file_ids = [row[0] for row in cursor.fetchall()]
            
            if matching_file_ids:
                # 使用 IN 子句过滤 file_id
                placeholders = ','.join('?' * len(matching_file_ids))
                query = f"""
                    SELECT pc.file_id, pc.name, SUM(ps.event_count) as total_event_count,
                           COUNT(*) as call_count, pc.ip, pc.depth
                    FROM perf_sample ps
                    JOIN perf_callchain pc ON ps.callchain_id = pc.callchain_id
                    WHERE pc.symbol_id = -1 AND pc.file_id IN ({placeholders})
                    GROUP BY pc.file_id, pc.name
                """
                cursor.execute(query, matching_file_ids)
                all_rows = cursor.fetchall()
            else:
                # 如果没有匹配的 file_id，返回空结果
                all_rows = []
        else:
            # 没有指定 target_so_name，使用原来的查询
            cursor.execute("""
                SELECT pc.file_id, pc.name, SUM(ps.event_count) as total_event_count,
                       COUNT(*) as call_count, pc.ip, pc.depth
                FROM perf_sample ps
                JOIN perf_callchain pc ON ps.callchain_id = pc.callchain_id
                WHERE pc.symbol_id = -1
                GROUP BY pc.file_id, pc.name
            """)
            all_rows = cursor.fetchall()

        # 立即获取所有结果，避免后续连接关闭后无法访问
        logger.debug(f'SQL 查询返回 {len(all_rows)} 行结果')

        address_event_counts = defaultdict(lambda: {'event_count': 0, 'call_count': 0, 'info': None})

        for file_id, name_id, total_event_count, call_count, ip, depth in all_rows:
            file_path = file_id_to_path.get(file_id, 'Unknown file')
            address_data = name_to_data.get(name_id, None)

            if address_data and file_path != 'Unknown file':
                key = (file_path, address_data)
                address_event_counts[key]['event_count'] += total_event_count
                address_event_counts[key]['call_count'] += call_count

                if address_event_counts[key]['info'] is None:
                    address_event_counts[key]['info'] = {
                        'file_path': file_path,
                        'address': address_data,
                        'file_id': file_id,
                        'name_id': name_id,
                        'ip': ip,
                        'depth': depth,
                    }
        
        logger.debug(f'处理后的 address_event_counts 包含 {len(address_event_counts)} 个地址')

        # 过滤和排序
        excluded_exact = ['[shmm]', 'Unknown file', '/bin/devhost.elf']
        excluded_prefixes = ['/system', '/vendor/lib64', '/lib', '/chip_prod']

        filtered = {}
        for key, data in address_event_counts.items():
            file_path, address = key
            if file_path in excluded_exact:
                continue
            if any(file_path.startswith(prefix) for prefix in excluded_prefixes):
                continue
            
            # 注意：如果指定了 target_so_name，已经在 SQL 查询时过滤了，这里不需要再次过滤
            # 但为了安全，仍然可以从地址字符串中验证一下（可选）
            
            filtered[key] = {
                **data['info'],
                'event_count': data['event_count'],
                'call_count': data['call_count'],
            }

        # 取 topN
        sorted_items = sorted(filtered.items(), key=lambda x: x[1]['event_count'], reverse=True)
        result = {k: v for k, v in sorted_items[:top_n]}
        if target_so_name:
            logger.debug(f'_get_event_count_top100 返回 {len(result)} 个地址（指定 SO 文件: {target_so_name}）')
            for key, data in list(result.items())[:3]:
                logger.debug(f'  地址: {data["address"]}, file_path: {data["file_path"]}')
        return result

    def _analyze_differences(self, diff_keys, event_count_top100):
        """对差异部分进行 LLM 分析"""
        # 创建临时 Excel 文件
        diff_data = []
        for key in diff_keys:
            info = event_count_top100[key]
            diff_data.append(
                {
                    '文件路径': info['file_path'],
                    '地址': info['address'],
                    'event_count': info['event_count'],
                    '调用次数': info.get('call_count', 0),
                    '文件ID': info['file_id'],
                    '名称ID': info['name_id'],
                    'IP地址': f'0x{info["ip"]:x}' if info['ip'] else None,
                    '堆栈深度': info['depth'],
                }
            )

        # 使用现有的分析器
        output_dir = config.get_output_dir()
        config.ensure_output_dir(output_dir)
        temp_excel = output_dir / f'{TEMP_FILE_PREFIX}event_count_diff.xlsx'
        temp_excel.parent.mkdir(exist_ok=True)
        df = pd.DataFrame(diff_data)
        df.to_excel(temp_excel, index=False)

        logger.info(f'[OK] Created temporary Excel file: {temp_excel}')
        logger.info(f'   Contains {len(diff_data)} different addresses')

        # 使用现有的分析器进行分析
        analyzer = MissingSymbolFunctionAnalyzer(
            excel_file=temp_excel,
            so_dir=self.so_dir,
            use_llm=self.use_llm,
            llm_model=self.llm_model,
            use_capstone_only=self.use_capstone_only,
        )

        logger.info('\nStarting LLM analysis...')
        # 使用 analyze_top_functions 方法，传入所有差异地址的数量
        results = analyzer.analyze_top_functions(top_n=len(diff_data))

        # 保存结果
        output_file = output_dir / config.DIFF_ANALYSIS_PATTERN
        analyzer.save_results(results, output_file=output_file)
        logger.info(f'[OK] Analysis results saved: {output_file}')

    def _generate_report(self, call_count_top100, event_count_top100, diff_keys):
        """生成对比报告"""
        # 获取输出目录
        output_dir = config.get_output_dir()
        config.ensure_output_dir(output_dir)

        report_data = []

        # 收集所有地址
        all_keys = set(call_count_top100.keys()) | set(event_count_top100.keys())

        for key in all_keys:
            call_info = call_count_top100.get(key, {})
            event_info = event_count_top100.get(key, {})

            file_path = call_info.get('file_path') or event_info.get('file_path', '')
            address = call_info.get('address') or event_info.get('address', '')

            report_data.append(
                {
                    '文件路径': file_path,
                    '地址': address,
                    '调用次数排名': '是' if key in call_count_top100 else '否',
                    '调用次数': call_info.get('call_count', 0),
                    'event_count排名': '是' if key in event_count_top100 else '否',
                    'event_count': event_info.get('event_count', 0),
                    '差异标记': '是' if key in diff_keys else '否',
                }
            )

        # 保存报告
        report_file = output_dir / config.COMPARISON_REPORT_PATTERN
        report_file.parent.mkdir(exist_ok=True)
        df = pd.DataFrame(report_data)
        df.to_excel(report_file, index=False)
        logger.info(f'[OK] Comparison report saved: {report_file}')

    def analyze_event_count_only(self, top_n=None):
        """只按 event_count 统计 topN，不进行对比"""
        if top_n is None:
            top_n = DEFAULT_TOP_N
        logger.info('=' * 80)
        logger.info(f'Analyzing top{top_n} by event_count')
        logger.info('=' * 80)

        conn = None
        cursor = None

        try:
            conn = sqlite3.connect(str(self.perf_db_file))
            cursor = conn.cursor()

            # 1. 加载映射关系
            logger.info('\nStep 1: Loading mappings...')
            try:
                cursor.execute('SELECT DISTINCT file_id, path FROM perf_files WHERE path IS NOT NULL')
                file_id_to_path = {row[0]: row[1] for row in cursor.fetchall()}
                logger.info(f'[OK] Loaded {len(file_id_to_path):,} file path mappings')
            except Exception as e:
                logger.info(f'[ERROR] Failed to load file path mappings: {e}')
                raise

            try:
                cursor.execute('SELECT id, data FROM data_dict WHERE data IS NOT NULL')
                name_to_data = {row[0]: row[1] for row in cursor.fetchall()}
                logger.info(f'[OK] Loaded {len(name_to_data):,} address data mappings')
            except Exception as e:
                logger.info(f'[ERROR] Failed to load address data mappings: {e}')
                raise

            # 2. 按 event_count 求和统计 topN
            logger.info(f'\nStep 2: Statistics by event_count sum top{top_n}...')
            try:
                # 如果 so_dir 是文件（通过 --so-file 指定），只统计该SO文件的函数
                target_so_name = None
                if self.so_dir and self.so_dir.is_file():
                    target_so_name = self.so_dir.name
                    logger.info(f'Filtering by SO file: {target_so_name}')
                
                # Get all data before closing connection
                event_count_top = self._get_event_count_top100(cursor, file_id_to_path, name_to_data, top_n, target_so_name)
                logger.info(f'[OK] Found {len(event_count_top)} addresses (event_count top{top_n})')
            except Exception:
                logger.exception('[ERROR] Failed to calculate event_count statistics')
                raise

            # 3. 转换为分析结果格式，并处理 HAP 地址（在关闭连接之前）
            logger.info('\nStep 3: Preparing analysis data...')
            try:
                results = []
                sorted_items = sorted(
                    event_count_top.items(),
                    key=lambda x: x[1]['event_count'],
                    reverse=True,
                )
                
                # 注意：如果指定了 target_so_name，已经在 SQL 查询时过滤了，这里不需要再次过滤
                # 但为了安全，仍然可以从地址字符串中验证一下（可选）
                # 直接取 top_n，因为 SQL 查询已经过滤了
                sorted_items = sorted_items[:top_n]

                # 3.1 检测并批量解析 HAP 地址
                hap_addresses = []
                for _key, info in sorted_items:
                    address = info['address']
                    # 检测 HAP 地址
                    if is_hap_address and is_hap_address(address):
                        hap_addresses.append(address)

                # 批量解析 HAP 地址
                hap_resolutions = {}
                if hap_addresses and resolve_hap_addresses_batch:
                    try:
                        logger.info(f'Detected {len(hap_addresses)} HAP addresses, starting batch resolution...')

                        so_dir = Path(self.so_dir) if self.so_dir else None

                        hap_resolutions = resolve_hap_addresses_batch(
                            Path(self.perf_db_file), hap_addresses, quick_mode=True, so_dir=so_dir
                        )
                        resolved_count = sum(1 for r in hap_resolutions.values() if r.get('resolved'))
                        logger.info(
                            f'✅ HAP address resolution completed, successfully resolved {resolved_count}/{len(hap_resolutions)}'
                        )
                        if resolved_count < len(hap_resolutions):
                            logger.warning(
                                f'⚠️  {len(hap_resolutions) - resolved_count} HAP addresses could not be resolved (offset exceeds file size)'
                            )
                    except Exception as e:
                        logger.warning(f'⚠️  HAP address resolution failed: {e}')

                # 3.2 转换为结果格式
                # 注意：如果指定了 target_so_name，已经在 SQL 查询时过滤了，这里不需要再次过滤
                for rank, (_key, info) in enumerate(sorted_items, 1):
                    address = info['address']
                    file_path = info['file_path']

                    # 处理 HAP 地址解析结果
                    if address in hap_resolutions:
                        resolution = hap_resolutions[address]
                        if resolution.get('resolved') and resolution.get('so_file_path'):
                            # 更新为 SO 文件路径和地址
                            file_path = resolution['so_file_path']
                            address = f'{resolution["so_name"]}+0x{resolution["so_offset"]:x}'
                            logger.info(f'  ✅ HAP address resolved: {info["address"]} -> {address}')
                        else:
                            # Skip unresolvable HAP addresses
                            logger.warning(f'  ⚠️  HAP address cannot be resolved, skipping: {address}')
                            continue  # 跳过这个地址，不添加到 results 中
                    
                    # 提取偏移量（从 address 中提取，格式如 "libxwebcore.so+0x50338a0"）
                    offset = None
                    if '+' in address:
                        try:
                            offset_str = address.split('+')[-1]
                            offset = f'0x{offset_str}' if not offset_str.startswith('0x') else offset_str
                        except Exception:
                            offset = address
                    else:
                        offset = address

                    results.append(
                        {
                            'rank': rank,
                            'file_path': file_path,  # 使用解析后的文件路径
                            'address': address,  # 使用解析后的地址
                            'offset': offset,
                            'event_count': info['event_count'],
                            'call_count': info.get('call_count', 0),
                            'file_id': info['file_id'],
                            'name_id': info['name_id'],
                            'ip': info.get('ip', 0),
                            'depth': info.get('depth', 0),
                            'so_file': '',  # 将在后续分析中填充
                            'instruction_count': 0,  # 将在后续分析中填充
                            'strings': '',  # 将在后续分析中填充
                            'llm_result': None,  # 将在后续分析中填充
                        }
                    )
                logger.info(f'[OK] Prepared {len(results)} results')
                if self.so_dir and self.so_dir.is_file():
                    logger.info(f'Results 中的地址列表:')
                    for r in results:
                        logger.info(f'  - {r.get("address", "unknown")} (file_path: {r.get("file_path", "unknown")})')
            except Exception:
                logger.exception('[ERROR] Failed to prepare analysis data')
                raise
            finally:
                # 关闭数据库连接（在准备完数据之后）
                if conn:
                    conn.close()
                    conn = None
                    cursor = None

            # 4. 进行函数分析（反汇编和字符串提取，以及可选的 LLM 分析）
            logger.info('\nStep 4: Function analysis (disassembly, string extraction, and LLM analysis)...')
            # 获取输出目录
            output_dir = config.get_output_dir()
            config.ensure_output_dir(output_dir)
            # 创建临时 Excel 文件用于分析（包含 event_count 列）
            # 注意：如果指定了 target_so_name，已经在 SQL 查询时过滤了，results 中应该只包含指定 SO 文件的地址
            temp_excel = output_dir / f'{TEMP_FILE_PREFIX}event_count.xlsx'
            temp_excel.parent.mkdir(exist_ok=True)
            temp_data = []
            for r in results:
                row = {
                    '文件路径': r['file_path'],
                    '地址': r['address'],
                    '调用次数': r.get('call_count', 0),
                }
                # 如果存在 event_count，也添加到临时 Excel 中
                if 'event_count' in r and (r.get('event_count') or 0) > 0:
                    row['指令数(event_count)'] = r['event_count']
                temp_data.append(row)
            pd.DataFrame(temp_data).to_excel(temp_excel, index=False)
            logger.info(f'✅ 创建临时 Excel 文件，包含 {len(temp_data)} 个地址')

            # 创建分析器（无论是否使用 LLM，都需要进行反汇编和字符串提取）
            if self.llm_analyzer:
                # 如果已经有 LLM 分析器，直接复用；否则创建新的（但可能没有 LLM）
                analyzer = MissingSymbolFunctionAnalyzer(
                    skip_decompilation=self.skip_decompilation,
                    excel_file=str(temp_excel),
                    perf_db_file=str(self.perf_db_file),  # 传递 perf_db_file 以便获取调用堆栈信息
                    so_dir=str(self.so_dir),
                    use_llm=False,  # 先不启用，避免重复初始化
                    llm_model=self.llm_model,
                    batch_size=self.batch_size,
                    context=self.context,  # 传递上下文
                    use_capstone_only=self.use_capstone_only,
                )
                # 复用已初始化的 LLM 分析器，并确保 use_llm 和 use_batch_llm 为 True（如果启用 LLM）
                if self.use_llm:
                    analyzer.llm_analyzer = self.llm_analyzer
                    analyzer.use_llm = True
                    analyzer.use_batch_llm = self.use_batch_llm  # 确保批量分析设置正确
                    analyzer.batch_size = self.batch_size  # 确保 batch_size 正确
            else:
                # 如果没有 LLM 分析器，正常创建（会尝试初始化）
                analyzer = MissingSymbolFunctionAnalyzer(
                    skip_decompilation=self.skip_decompilation,
                    excel_file=str(temp_excel),
                    perf_db_file=str(self.perf_db_file),  # 传递 perf_db_file 以便获取调用堆栈信息
                    so_dir=str(self.so_dir),
                    use_llm=self.use_llm,
                    llm_model=self.llm_model,
                    batch_size=self.batch_size,
                    context=self.context,  # 传递上下文
                    use_capstone_only=self.use_capstone_only,
                )

            # 使用 analyze_top_functions 进行分析（会进行反汇编、字符串提取和可选的 LLM 分析）
            analyzed_results = analyzer.analyze_top_functions(top_n=len(results))

            # 将 event_count 和 call_count 添加到结果中（因为 analyze_top_functions 可能不包含这些字段）
            event_count_map = {r['address']: r['event_count'] for r in results}
            call_count_map = {r['address']: r.get('call_count', 0) for r in results}
            logger.debug(f'event_count_map 包含 {len(event_count_map)} 个地址: {list(event_count_map.keys())}')
            for result in analyzed_results:
                address = result.get('address', '')
                if address in event_count_map:
                    result['event_count'] = event_count_map[address]
                else:
                    logger.warning(f'⚠️  地址 {address} 在 event_count_map 中未找到，无法设置 event_count')
                if address in call_count_map:
                    result['call_count'] = call_count_map[address]
                else:
                    logger.warning(f'⚠️  地址 {address} 在 call_count_map 中未找到，无法设置 call_count')
            # 注意：字符串常量已经在 analyze_top_functions -> analyze_function 中提取了

            # 清理临时文件
            if temp_excel.exists():
                temp_excel.unlink()

            return analyzed_results

        except Exception:
            logger.exception('[ERROR] analyze_event_count_only execution failed')
            raise
        finally:
            if conn:
                try:
                    conn.close()
                except Exception as e:
                    logger.info(f'[WARN] Error closing database connection: {e}')
                    pass

    def save_event_count_results(self, results, time_tracker=None, output_dir=None, top_n=None):
        """保存 event_count 分析结果

        Args:
            results: 分析结果列表
            time_tracker: 时间跟踪器（可选）
            output_dir: 输出目录（可选，默认使用配置中的输出目录）
            top_n: 用户指定的分析数量（用于生成文件名，如果不提供则使用实际结果数量）
        """
        try:
            # 获取输出目录
            output_dir = config.get_output_dir() if output_dir is None else Path(output_dir)
            config.ensure_output_dir(output_dir)
            # 确保 results 按 event_count 排序（如果存在）
            # 因为后续的 save_results 可能会重新排序，我们需要确保顺序正确
            if results and any('event_count' in r and (r.get('event_count') or 0) > 0 for r in results):
                # 按 event_count 降序排序
                results = sorted(results, key=lambda x: x.get('event_count') or 0, reverse=True)
                # 更新排名
                for rank, result in enumerate(results, 1):
                    result['rank'] = rank

            # 创建临时 Excel 文件用于保存
            temp_excel = output_dir / f'{TEMP_FILE_PREFIX}event_count.xlsx'
            temp_excel.parent.mkdir(exist_ok=True)

            # 创建临时 Excel 文件时，包含 event_count 字段（如果存在）
            temp_data = []
            for r in results:
                row = {
                    '文件路径': r['file_path'],
                    '地址': r['address'],
                    '调用次数': r.get('call_count', 0),
                }
                # 如果存在 event_count，也添加到临时 Excel 中，以便后续按 event_count 排序
                if 'event_count' in r and (r.get('event_count') or 0) > 0:
                    row['指令数(event_count)'] = r['event_count']
                temp_data.append(row)

            # 确保文件写入完成
            try:
                df_temp = pd.DataFrame(temp_data)
                df_temp.to_excel(temp_excel, index=False, engine='openpyxl')
                # 确保文件已关闭
                gc.collect()
            except Exception as e:
                logger.info(f'[ERROR] Failed to create temporary Excel file: {e}')
                raise

            # 如果已经有 LLM 分析器，直接复用；否则创建新的（但可能没有 LLM）
            if self.llm_analyzer:
                # 创建时先不启用 LLM，避免重复初始化
                analyzer = MissingSymbolFunctionAnalyzer(
                    skip_decompilation=self.skip_decompilation,
                    excel_file=str(temp_excel),
                    perf_db_file=str(self.perf_db_file),  # 传递 perf_db_file 以便获取调用堆栈信息
                    so_dir=str(self.so_dir),
                    use_llm=False,  # 先不启用，避免重复初始化
                    llm_model=self.llm_model,
                    use_capstone_only=self.use_capstone_only,
                )
                # 复用已初始化的 LLM 分析器，并确保 use_llm 和 use_batch_llm 为 True
                analyzer.llm_analyzer = self.llm_analyzer
                analyzer.use_llm = True
                analyzer.use_batch_llm = self.use_batch_llm  # 确保批量分析设置正确
                analyzer.batch_size = self.batch_size  # 确保 batch_size 正确
            else:
                # 如果没有 LLM 分析器，正常创建（会尝试初始化）
                analyzer = MissingSymbolFunctionAnalyzer(
                    skip_decompilation=self.skip_decompilation,
                    excel_file=str(temp_excel),
                    perf_db_file=str(self.perf_db_file),  # 传递 perf_db_file 以便获取调用堆栈信息
                    so_dir=str(self.so_dir),
                    use_llm=self.use_llm,
                    llm_model=self.llm_model,
                    batch_size=self.batch_size,  # 传递 batch_size
                    use_capstone_only=self.use_capstone_only,
                )

            # 确定输出文件名（使用用户指定的 top_n，如果没有则使用实际结果数量）
            if top_n is None:
                top_n = len(results)
            output_file = str(output_dir / EVENT_COUNT_ANALYSIS_PATTERN.format(n=top_n))
            html_file = str(output_dir / EVENT_COUNT_REPORT_PATTERN.format(n=top_n))

            # 保存 Excel 结果和生成 HTML 报告（传递 time_tracker、html_file 和 output_dir）
            saved_file = analyzer.save_results(
                results,
                output_file=output_file,
                html_file=html_file,
                time_tracker=time_tracker,
                output_dir=output_dir,
            )

            # 清理临时文件
            try:
                if temp_excel.exists():
                    temp_excel.unlink()
            except Exception as e:
                logger.info(f'[WARN] Failed to clean up temporary file: {e}')

            return saved_file
        except Exception:
            logger.exception('[ERROR] save_event_count_results failed')
            raise
