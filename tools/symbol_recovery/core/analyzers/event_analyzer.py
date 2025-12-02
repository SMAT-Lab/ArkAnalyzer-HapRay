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
from core.utils.logger import get_logger
from core.utils.perf_converter import MissingSymbolFunctionAnalyzer

#  使用日志
logger = get_logger(__name__)

# 加载 .env 文件中的环境变量
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    logger.warning('未安装 python-dotenv 库，将跳过 .env 文件的加载')
    logger.warning('请安装 python-dotenv 库: pip install python-dotenv')
except Exception as e:
    logger.error('加载 .env 文件时出错: %s', e)
    raise


class EventCountAnalyzer:
    """事件计数分析器"""

    def __init__(
        self,
        perf_db_file,
        so_dir=None,
        so_file=None,
        use_llm=True,
        llm_model=None,
        use_batch_llm=True,
        batch_size=5,
        context=None,
        open_source_lib=None,
        use_capstone_only=False,
        save_prompts=False,
        output_dir=None,
        skip_decompilation=False,
    ):
        """
        初始化分析器

        Args:
            perf_db_file: perf.db 文件路径
            so_dir: SO 文件目录（可选，如果指定了 so_file 则不需要）
            so_file: 单个 SO 文件路径（可选，如果指定则优先使用此文件，否则使用 so_dir）
            use_llm: 是否使用 LLM 分析
            llm_model: LLM 模型名称
            use_batch_llm: 是否使用批量 LLM 分析（一个 prompt 包含多个函数，默认 True）
            batch_size: 批量分析时每个 prompt 包含的函数数量（默认 3）
            context: 自定义上下文信息（可选，如果不提供则根据 SO 文件名自动推断）
            open_source_lib: 开源库名称（可选，如 "ffmpeg", "openssl" 等）。如果指定，会告诉大模型这是基于该开源库的定制版本
            use_capstone_only: 只使用 Capstone 反汇编（不使用 Radare2，即使已安装）
            save_prompts: 是否保存生成的 prompt 到文件
            output_dir: 输出目录，用于保存 prompt 文件
            skip_decompilation: 是否跳过反编译（默认 False，启用反编译可提高 LLM 分析质量但较慢）
        """
        self.perf_db_file = Path(perf_db_file)
        self.so_dir = Path(so_dir) if so_dir else None
        self.so_file = Path(so_file) if so_file else None
        
        # 验证：必须提供 so_file 或 so_dir 之一
        if not self.so_file and not self.so_dir:
            raise ValueError('必须提供 so_file 或 so_dir 之一')
        
        if self.so_file and not self.so_file.exists():
            raise FileNotFoundError(f'SO 文件不存在: {so_file}')
        self.use_llm = use_llm
        self.llm_model = llm_model
        self.use_batch_llm = use_batch_llm
        self.batch_size = batch_size or config.DEFAULT_BATCH_SIZE
        self.context = context
        self.open_source_lib = open_source_lib
        self.use_capstone_only = use_capstone_only
        self.skip_decompilation = skip_decompilation

        if not self.perf_db_file.exists():
            raise FileNotFoundError(f'perf.db 不存在: {perf_db_file}')
        if self.so_dir and not self.so_dir.exists():
            raise FileNotFoundError(f'SO 文件目录不存在: {so_dir}')

        # 初始化 LLM 分析器（公共工具）
        self.llm_analyzer, self.use_llm, self.use_batch_llm = init_llm_analyzer(
            use_llm=self.use_llm,
            llm_model=self.llm_model,
            use_batch_llm=self.use_batch_llm,
            batch_size=self.batch_size,
            logger=logger.info,
            save_prompts=save_prompts,
            output_dir=output_dir,
            open_source_lib=self.open_source_lib,
        )

    def analyze(self):
        """执行分析"""
        logger.info('=' * 80)
        logger.info('分析 event_count 的 top100')
        logger.info('=' * 80)

        conn = sqlite3.connect(str(self.perf_db_file))
        cursor = conn.cursor()

        try:
            # 1. 加载映射关系
            logger.info('\n步骤 1: 加载映射关系...')
            cursor.execute('SELECT DISTINCT file_id, path FROM perf_files WHERE path IS NOT NULL')
            file_id_to_path = {row[0]: row[1] for row in cursor.fetchall()}
            logger.info(f'[OK] 加载了 {len(file_id_to_path):,} 个文件路径映射')

            cursor.execute('SELECT id, data FROM data_dict WHERE data IS NOT NULL')
            name_to_data = {row[0]: row[1] for row in cursor.fetchall()}
            logger.info(f'[OK] 加载了 {len(name_to_data):,} 个地址数据映射')

            # 2. 按调用次数统计 top100（现有逻辑）
            logger.info('\n步骤 2: 按调用次数统计 top100...')
            call_count_top100 = self._get_call_count_top100(cursor, file_id_to_path, name_to_data)
            logger.info(f'[OK] 找到 {len(call_count_top100)} 个地址（调用次数 top100）')

            # 3. 按 event_count 求和统计 top100（新逻辑）
            logger.info('\n步骤 3: 按 event_count 求和统计 top100...')
            event_count_top100 = self._get_event_count_top100(cursor, file_id_to_path, name_to_data)
            logger.info(f'[OK] 找到 {len(event_count_top100)} 个地址（event_count top100）')

            # 4. 找出差异
            logger.info('\n步骤 4: 找出差异...')
            call_count_keys = set(call_count_top100.keys())
            event_count_keys = set(event_count_top100.keys())

            # 在 event_count top100 中但不在 call_count top100 中的
            diff_keys = event_count_keys - call_count_keys
            logger.info(f'[OK] 找到 {len(diff_keys)} 个差异地址（在 event_count top100 但不在 call_count top100）')

            if diff_keys:
                logger.info('\n差异地址列表（前20个）:')
                diff_list = sorted(
                    [(k, event_count_top100[k]) for k in diff_keys],
                    key=lambda x: x[1]['event_count'],
                    reverse=True,
                )
                for i, (_key, info) in enumerate(diff_list[:20], 1):
                    logger.info(
                        f'  {i}. {info["file_path"]} {info["address"]} - event_count: {info["event_count"]}, 调用次数: {info.get("call_count", 0)}'
                    )

            # 5. 对差异部分进行 LLM 分析
            if diff_keys and self.use_llm:
                logger.info('\n步骤 5: 对差异部分进行 LLM 分析...')
                self._analyze_differences(diff_keys, event_count_top100)

            # 6. 生成报告
            logger.info('\n步骤 6: 生成报告...')
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
                file_path = file_id_to_path.get(file_id, '未知文件')
                address_data = name_to_data.get(name_id, None)

                if address_data and file_path != '未知文件':
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
        excluded_exact = ['[shmm]', '未知文件', '/bin/devhost.elf']
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
        top_n = config.DEFAULT_TOP_N
        return {k: v for k, v in sorted_items[:top_n]}

    def _get_event_count_top100(self, cursor, file_id_to_path, name_to_data, top_n=None):
        """按 event_count 求和统计 topN"""
        if top_n is None:
            top_n = config.DEFAULT_TOP_N
        # 查询 perf_sample 和 perf_callchain 的关联
        cursor.execute("""
            SELECT pc.file_id, pc.name, SUM(ps.event_count) as total_event_count,
                   COUNT(*) as call_count, pc.ip, pc.depth
            FROM perf_sample ps
            JOIN perf_callchain pc ON ps.callchain_id = pc.callchain_id
            WHERE pc.symbol_id = -1
            GROUP BY pc.file_id, pc.name
        """)

        # 立即获取所有结果，避免后续连接关闭后无法访问
        all_rows = cursor.fetchall()

        address_event_counts = defaultdict(lambda: {'event_count': 0, 'call_count': 0, 'info': None})

        for file_id, name_id, total_event_count, call_count, ip, depth in all_rows:
            file_path = file_id_to_path.get(file_id, '未知文件')
            address_data = name_to_data.get(name_id, None)

            if address_data and file_path != '未知文件':
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

        # 过滤和排序
        excluded_exact = ['[shmm]', '未知文件', '/bin/devhost.elf']
        excluded_prefixes = ['/system', '/vendor/lib64', '/lib', '/chip_prod']

        # 如果指定了 so_file，只保留匹配的地址
        target_so_name = None
        if self.so_file:
            target_so_name = self.so_file.name
            logger.info(f'📌 已指定 SO 文件: {target_so_name}，将只分析该文件的地址')

        filtered = {}
        for key, data in address_event_counts.items():
            file_path, address = key
            if file_path in excluded_exact:
                continue
            if any(file_path.startswith(prefix) for prefix in excluded_prefixes):
                continue
            
            # 如果指定了 so_file，只保留匹配的地址
            if target_so_name:
                file_so_name = Path(file_path).name
                if file_so_name != target_so_name:
                    continue
            
            filtered[key] = {
                **data['info'],
                'event_count': data['event_count'],
                'call_count': data['call_count'],
            }

        # 取 topN
        sorted_items = sorted(filtered.items(), key=lambda x: x[1]['event_count'], reverse=True)
        return {k: v for k, v in sorted_items[:top_n]}

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
        temp_excel = output_dir / f'{config.TEMP_FILE_PREFIX}event_count_diff.xlsx'
        temp_excel.parent.mkdir(exist_ok=True)
        df = pd.DataFrame(diff_data)
        df.to_excel(temp_excel, index=False)

        logger.info(f'[OK] 创建临时 Excel 文件: {temp_excel}')
        logger.info(f'   包含 {len(diff_data)} 个差异地址')

        # 使用现有的分析器进行分析
        analyzer = MissingSymbolFunctionAnalyzer(
            excel_file=temp_excel,
            so_dir=self.so_dir,
            so_file=self.so_file,
            use_llm=self.use_llm,
            llm_model=self.llm_model,
            use_capstone_only=self.use_capstone_only,
        )

        logger.info('\n开始 LLM 分析...')
        # 使用 analyze_top_functions 方法，传入所有差异地址的数量
        results = analyzer.analyze_top_functions(top_n=len(diff_data))

        # 保存结果
        output_file = output_dir / config.DIFF_ANALYSIS_PATTERN
        analyzer.save_results(results, output_file=output_file)
        logger.info(f'[OK] 分析结果已保存: {output_file}')

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
        logger.info(f'[OK] 对比报告已保存: {report_file}')

    def analyze_event_count_only(self, top_n=None):
        """只按 event_count 统计 topN，不进行对比"""
        if top_n is None:
            top_n = config.DEFAULT_TOP_N
        logger.info('=' * 80)
        logger.info(f'分析 event_count 的 top{top_n}')
        logger.info('=' * 80)

        conn = None
        cursor = None

        try:
            conn = sqlite3.connect(str(self.perf_db_file))
            cursor = conn.cursor()

            # 1. 加载映射关系
            logger.info('\n步骤 1: 加载映射关系...')
            try:
                cursor.execute('SELECT DISTINCT file_id, path FROM perf_files WHERE path IS NOT NULL')
                file_id_to_path = {row[0]: row[1] for row in cursor.fetchall()}
                logger.info(f'[OK] 加载了 {len(file_id_to_path):,} 个文件路径映射')
            except Exception as e:
                logger.info(f'[ERROR] 加载文件路径映射失败: {e}')
                raise

            try:
                cursor.execute('SELECT id, data FROM data_dict WHERE data IS NOT NULL')
                name_to_data = {row[0]: row[1] for row in cursor.fetchall()}
                logger.info(f'[OK] 加载了 {len(name_to_data):,} 个地址数据映射')
            except Exception as e:
                logger.info(f'[ERROR] 加载地址数据映射失败: {e}')
                raise

            # 2. 按 event_count 求和统计 topN
            logger.info(f'\n步骤 2: 按 event_count 求和统计 top{top_n}...')
            try:
                # 在关闭连接前获取所有数据
                event_count_top = self._get_event_count_top100(cursor, file_id_to_path, name_to_data, top_n)
                logger.info(f'[OK] 找到 {len(event_count_top)} 个地址（event_count top{top_n}）')
            except Exception:
                logger.exception('[ERROR] 统计 event_count 失败')
                raise

            # 3. 转换为分析结果格式，并处理 HAP 地址（在关闭连接之前）
            logger.info('\n步骤 3: 准备分析数据...')
            try:
                results = []
                sorted_items = sorted(
                    event_count_top.items(),
                    key=lambda x: x[1]['event_count'],
                    reverse=True,
                )[:top_n]

                # 3.1 检测并批量解析 HAP 地址
                hap_addresses = []
                for _key, info in sorted_items:
                    address = info['address']
                    # 检测 HAP 地址
                    try:
                        from core.utils.hap_address_resolver import is_hap_address, resolve_hap_addresses_batch
                        if is_hap_address(address):
                            hap_addresses.append(address)
                    except ImportError:
                        pass  # HAP 解析模块不可用
                
                # 批量解析 HAP 地址
                hap_resolutions = {}
                if hap_addresses:
                    try:
                        from core.utils.hap_address_resolver import resolve_hap_addresses_batch
                        from pathlib import Path
                        logger.info(f'检测到 {len(hap_addresses)} 个 HAP 地址，开始批量解析...')
                        from pathlib import Path
                        so_dir = Path(self.so_dir) if self.so_dir else None
                        
                        hap_resolutions = resolve_hap_addresses_batch(Path(self.perf_db_file), hap_addresses, quick_mode=True, so_dir=so_dir)
                        resolved_count = sum(1 for r in hap_resolutions.values() if r.get("resolved"))
                        logger.info(f'✅ HAP 地址解析完成，成功解析 {resolved_count}/{len(hap_resolutions)} 个')
                        if resolved_count < len(hap_resolutions):
                            logger.warning(f'⚠️  有 {len(hap_resolutions) - resolved_count} 个 HAP 地址无法解析（偏移量超出文件大小）')
                    except Exception as e:
                        logger.warning(f'⚠️  HAP 地址解析失败: {e}')

                # 3.2 转换为结果格式
                for rank, (_key, info) in enumerate(sorted_items, 1):
                    address = info['address']
                    file_path = info['file_path']
                    
                    # 处理 HAP 地址解析结果
                    if address in hap_resolutions:
                        resolution = hap_resolutions[address]
                        if resolution.get('resolved') and resolution.get('so_file_path'):
                            # 更新为 SO 文件路径和地址
                            file_path = resolution['so_file_path']
                            address = f"{resolution['so_name']}+0x{resolution['so_offset']:x}"
                            logger.info(f'  ✅ HAP 地址解析: {info["address"]} -> {address}')
                        else:
                            # 无法解析的 HAP 地址，跳过
                            logger.warning(f'  ⚠️  HAP 地址无法解析，跳过: {address}')
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
                logger.info(f'[OK] 准备了 {len(results)} 个结果')
            except Exception:
                logger.exception('[ERROR] 准备分析数据失败')
                raise
            finally:
                # 关闭数据库连接（在准备完数据之后）
                if conn:
                    conn.close()
                    conn = None
                    cursor = None

            # 4. 进行函数分析（反汇编和字符串提取，以及可选的 LLM 分析）
            logger.info('\n步骤 4: 进行函数分析（反汇编、字符串提取和 LLM 分析）...')
            # 获取输出目录
            output_dir = config.get_output_dir()
            config.ensure_output_dir(output_dir)
            # 创建临时 Excel 文件用于分析（包含 event_count 列）
            temp_excel = output_dir / f'{config.TEMP_FILE_PREFIX}event_count.xlsx'
            temp_excel.parent.mkdir(exist_ok=True)
            temp_data = []
            for r in results:
                row = {
                    '文件路径': r['file_path'],
                    '地址': r['address'],
                    '调用次数': r.get('call_count', 0),
                }
                # 如果存在 event_count，也添加到临时 Excel 中
                if 'event_count' in r and r.get('event_count', 0) > 0:
                    row['指令数(event_count)'] = r['event_count']
                temp_data.append(row)
            pd.DataFrame(temp_data).to_excel(temp_excel, index=False)

            # 创建分析器（无论是否使用 LLM，都需要进行反汇编和字符串提取）
            if self.llm_analyzer:
                # 如果已经有 LLM 分析器，直接复用；否则创建新的（但可能没有 LLM）
                analyzer = MissingSymbolFunctionAnalyzer(
                    skip_decompilation=self.skip_decompilation,
                    excel_file=str(temp_excel),
                    so_dir=str(self.so_dir) if self.so_dir else None,
                    so_file=str(self.so_file) if self.so_file else None,
                    use_llm=False,  # 先不启用，避免重复初始化
                    llm_model=self.llm_model,
                    use_batch_llm=self.use_batch_llm,
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
                    so_dir=str(self.so_dir) if self.so_dir else None,
                    so_file=str(self.so_file) if self.so_file else None,
                    use_llm=self.use_llm,
                    llm_model=self.llm_model,
                    use_batch_llm=self.use_batch_llm,
                    batch_size=self.batch_size,
                    context=self.context,  # 传递上下文
                    use_capstone_only=self.use_capstone_only,
                )

            # 使用 analyze_top_functions 进行分析（会进行反汇编、字符串提取和可选的 LLM 分析）
            analyzed_results = analyzer.analyze_top_functions(top_n=len(results))

            # 将 event_count 和 call_count 添加到结果中（因为 analyze_top_functions 可能不包含这些字段）
            event_count_map = {r['address']: r['event_count'] for r in results}
            call_count_map = {r['address']: r.get('call_count', 0) for r in results}
            for result in analyzed_results:
                address = result.get('address', '')
                if address in event_count_map:
                    result['event_count'] = event_count_map[address]
                if address in call_count_map:
                    result['call_count'] = call_count_map[address]
            # 注意：字符串常量已经在 analyze_top_functions -> analyze_function 中提取了

            # 清理临时文件
            if temp_excel.exists():
                temp_excel.unlink()

            return analyzed_results

        except Exception:
            logger.exception('[ERROR] analyze_event_count_only 执行失败')
            raise
        finally:
            if conn:
                try:
                    conn.close()
                except Exception as e:
                    logger.info(f'[WARN] 关闭数据库连接时出错: {e}')
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
            if results and any('event_count' in r and r.get('event_count', 0) > 0 for r in results):
                # 按 event_count 降序排序
                results = sorted(results, key=lambda x: x.get('event_count', 0), reverse=True)
                # 更新排名
                for rank, result in enumerate(results, 1):
                    result['rank'] = rank

            # 创建临时 Excel 文件用于保存
            temp_excel = output_dir / f'{config.TEMP_FILE_PREFIX}event_count.xlsx'
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
                if 'event_count' in r and r.get('event_count', 0) > 0:
                    row['指令数(event_count)'] = r['event_count']
                temp_data.append(row)

            # 确保文件写入完成
            try:
                df_temp = pd.DataFrame(temp_data)
                df_temp.to_excel(temp_excel, index=False, engine='openpyxl')
                # 确保文件已关闭
                gc.collect()
            except Exception as e:
                logger.info(f'[ERROR] 创建临时 Excel 文件失败: {e}')
                raise

            # 如果已经有 LLM 分析器，直接复用；否则创建新的（但可能没有 LLM）
            if self.llm_analyzer:
                # 创建时先不启用 LLM，避免重复初始化
                analyzer = MissingSymbolFunctionAnalyzer(
                    skip_decompilation=self.skip_decompilation,
                    excel_file=str(temp_excel),
                    so_dir=str(self.so_dir) if self.so_dir else None,
                    so_file=str(self.so_file) if self.so_file else None,
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
                    so_dir=str(self.so_dir) if self.so_dir else None,
                    so_file=str(self.so_file) if self.so_file else None,
                    use_llm=self.use_llm,
                    llm_model=self.llm_model,
                    use_batch_llm=self.use_batch_llm,  # 传递批量分析设置
                    batch_size=self.batch_size,  # 传递 batch_size
                    use_capstone_only=self.use_capstone_only,
                )

            # 确定输出文件名（使用用户指定的 top_n，如果没有则使用实际结果数量）
            if top_n is None:
                top_n = len(results)
            output_file = str(output_dir / config.EVENT_COUNT_ANALYSIS_PATTERN.format(n=top_n))
            html_file = str(output_dir / config.EVENT_COUNT_REPORT_PATTERN.format(n=top_n))

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
                logger.info(f'[WARN] 清理临时文件失败: {e}')

            return saved_file
        except Exception:
            logger.exception('[ERROR] save_event_count_results 失败')
            raise
