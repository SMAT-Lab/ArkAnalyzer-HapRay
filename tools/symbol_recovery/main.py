#!/usr/bin/env python3

"""
SymRecover - 二进制符号恢复工具：支持 perf.data 和 Excel 偏移量两种模式
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Optional

from core.analyzers.event_analyzer import EventCountAnalyzer
from core.analyzers.excel_analyzer import ExcelOffsetAnalyzer
from core.analyzers.perf_analyzer import PerfDataToSqliteConverter
from core.utils import config
from core.utils.logger import get_logger
from core.utils.perf_converter import MissingSymbolFunctionAnalyzer
from core.utils.symbol_replacer import (
    add_disclaimer,
    load_function_mapping,
    replace_symbols_in_html,
)
from core.utils.time_tracker import TimeTracker

logger = get_logger(__name__)


def create_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description='SymRecover - 二进制符号恢复工具：支持 perf.data 和 Excel 偏移量两种模式',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 运行完整工作流（默认参数）
  python3 main.py

  # 指定输入文件
  python3 main.py --perf-data perf.data --so-dir /path/to/so/directory

  # 只分析前50个函数，不使用 LLM
  python3 main.py --top-n 50 --no-llm

  # 按 event_count 统计（默认）
  python3 main.py
  # 或显式指定
  python3 main.py --stat-method event_count

  # 按调用次数统计
  python3 main.py --stat-method call_count

  # 跳过 Step 1（如果已有 perf.db）
  python3 main.py --skip-step1

  # 只执行 Step 4（HTML 符号替换）
  python3 main.py --only-step4 --html-input step4/hiperfReport.html

  # 跳过 Step 4（不进行 HTML 符号替换）
  python3 main.py --skip-step4

  # Excel 分析模式（从 Excel 文件读取偏移量进行分析）
  python3 main.py --excel-file test.xlsx --so-file /path/to/lib.so

  # Excel 分析模式（不使用 LLM）
  python3 main.py --excel-file test.xlsx --so-file /path/to/lib.so --no-llm
        """,
    )

    # 模式选择：Excel 分析模式或 perf 分析模式
    parser.add_argument(
        '--excel-file',
        type=str,
        default=None,
        help='Excel 文件路径（包含函数偏移量地址）。如果指定此参数，将启用 Excel 分析模式',
    )
    parser.add_argument(
        '--so-file',
        type=str,
        default=None,
        help='SO 文件路径（Excel 分析模式必需）。如果未指定，将使用 --so-dir 目录下的默认 SO 文件',
    )

    # 输入参数（perf 分析模式）
    parser.add_argument(
        '--perf-data',
        type=str,
        default=config.DEFAULT_PERF_DATA,
        help=f'perf.data 文件路径（默认: {config.DEFAULT_PERF_DATA}，仅 perf 分析模式）',
    )
    parser.add_argument(
        '--perf-db',
        type=str,
        default=None,
        help='perf.db 文件路径（默认: 根据 perf.data 路径自动生成，仅 perf 分析模式）',
    )
    parser.add_argument(
        '--so-dir',
        type=str,
        default=None,
        help='SO 文件目录，包含需要分析的 SO 库文件（必需，无默认值）',
    )

    # 输出目录参数
    parser.add_argument(
        '--output-dir',
        type=str,
        default=None,
        help=f'输出目录，用于存储所有分析结果和 perf.db 等（默认: {config.DEFAULT_OUTPUT_DIR}）',
    )

    # 分析参数
    parser.add_argument(
        '--top-n',
        type=int,
        default=config.DEFAULT_TOP_N,
        help=f'分析前 N 个函数（默认: {config.DEFAULT_TOP_N}）',
    )
    parser.add_argument(
        '--stat-method',
        type=str,
        choices=['call_count', 'event_count'],
        default='event_count',
        help='统计方式：call_count（调用次数）或 event_count（指令数）（默认: event_count）',
    )
    parser.add_argument('--no-llm', action='store_true', help='不使用 LLM 分析（仅反汇编）')
    parser.add_argument(
        '--no-batch',
        action='store_true',
        help='不使用批量分析（逐个函数分析，较慢但较稳定）',
    )
    parser.add_argument(
        '--batch-size',
        type=int,
        default=config.DEFAULT_BATCH_SIZE,
        help=f'批量分析时每个 prompt 包含的函数数量（默认: {config.DEFAULT_BATCH_SIZE}，建议范围: 3-10）',
    )
    parser.add_argument(
        '--use-capstone-only',
        action='store_true',
        help='只使用 Capstone 反汇编（不使用 Radare2，即使已安装）',
    )
    parser.add_argument(
        '--save-prompts',
        action='store_true',
        help='保存每个函数生成的 prompt 到文件（用于后续 debug）',
    )
    parser.add_argument(
        '--skip-decompilation',
        action='store_true',
        help='跳过反编译步骤（仅使用反汇编代码，可显著提升速度但可能降低 LLM 分析质量）',
    )

    # 流程控制
    parser.add_argument('--skip-step1', action='store_true', help='跳过 Step 1（perf.data → perf.db）')
    parser.add_argument('--skip-step3', action='store_true', help='跳过 Step 3（LLM 分析）')
    parser.add_argument('--only-step1', action='store_true', help='只执行 Step 1')
    parser.add_argument('--only-step3', action='store_true', help='只执行 Step 3')
    parser.add_argument('--skip-step4', action='store_true', help='跳过 Step 4（HTML 符号替换）')
    parser.add_argument('--only-step4', action='store_true', help='只执行 Step 4（HTML 符号替换）')
    parser.add_argument(
        '--html-input',
        type=str,
        default=None,
        help=f'HTML 输入文件路径或目录（默认: 自动查找 {", ".join(config.STEP_DIRS)} 目录下的 {config.HTML_REPORT_PATTERN}）',
    )
    parser.add_argument(
        '--html-pattern',
        type=str,
        default=config.HTML_REPORT_PATTERN,
        help=f'HTML 文件搜索模式（默认: {config.HTML_REPORT_PATTERN}）',
    )

    # Excel 分析模式参数
    # output-dir 已在上面定义，这里移除重复
    parser.add_argument('--llm-model', type=str, help='LLM 模型名称')
    parser.add_argument(
        '--context',
        type=str,
        default=None,
        help='自定义上下文信息（可选，用于 LLM 分析。如果不提供，工具会根据 SO 文件名和应用路径自动推断）',
    )
    return parser


def resolve_file_path(path_str: str) -> Path:
    try:
        candidate = Path(path_str)
        if candidate.exists():
            return candidate
        candidate = Path(path_str).resolve()
        if candidate.exists():
            return candidate
        return Path(os.path.abspath(path_str))
    except Exception:
        return Path(path_str)


def resolve_directory(path_str: str) -> Path:
    try:
        candidate = Path(path_str)
        if candidate.exists():
            return candidate
        candidate = Path(path_str).resolve()
        if candidate.exists():
            return candidate
        return Path(os.path.abspath(path_str))
    except Exception:
        return Path(path_str)


def resolve_perf_paths(args, output_dir: Path) -> tuple[Path, Optional[Path], Optional[Path]]:
    perf_data_file = resolve_file_path(args.perf_data)

    if args.perf_db:
        perf_db_file = Path(args.perf_db)
    elif args.perf_data:
        try:
            perf_db_file = output_dir / config.DEFAULT_PERF_DB
        except Exception:
            perf_db_file = None
    else:
        perf_db_file = None

    so_dir = None
    if args.so_dir and not args.only_step1:
        so_dir = resolve_directory(args.so_dir)
    return perf_data_file, perf_db_file, so_dir


def handle_excel_mode(args, output_dir: Path) -> bool:
    if not args.excel_file:
        return False

    logger.info('=' * 80)
    logger.info('Excel 分析模式：从 Excel 文件读取偏移量进行分析')
    logger.info('=' * 80)

    excel_file = Path(args.excel_file)
    if not excel_file.exists():
        logger.error('❌ 错误: Excel 文件不存在: %s', excel_file)
        sys.exit(1)

    so_file = resolve_excel_so_file(args)
    if not so_file.exists():
        logger.error('❌ 错误: SO 文件不存在: %s', so_file)
        sys.exit(1)

    logger.info(f'输入文件: {excel_file}')
    logger.info(f'SO 文件: {so_file}')

    time_tracker = TimeTracker()
    time_tracker.start_step('初始化', '加载配置和初始化分析器')

    try:
        analyzer = ExcelOffsetAnalyzer(
            so_file=str(so_file),
            excel_file=str(excel_file),
            use_llm=not args.no_llm,
            llm_model=args.llm_model,
            use_batch_llm=not args.no_batch,
            batch_size=args.batch_size,
            context=args.context,
            save_prompts=args.save_prompts,
            output_dir=str(output_dir),
            skip_decompilation=args.skip_decompilation,
        )
        time_tracker.end_step('初始化')
    except Exception:
        logger.exception('❌ 初始化失败')
        sys.exit(1)

    time_tracker.start_step('分析偏移量', '反汇编和 LLM 分析')
    results = analyzer.analyze_all()
    time_tracker.end_step(f'完成分析 {len(results)} 个函数')

    if not results:
        logger.error('❌ 没有分析结果')
        sys.exit(1)

    time_tracker.start_step('保存结果', '生成 Excel 和 HTML 报告')
    config.ensure_output_dir(output_dir)
    excel_file_output = analyzer.save_results(
        results,
        str(output_dir / f'excel_offset_analysis_{len(results)}_functions.xlsx'),
    )
    html_file = analyzer.generate_html_report(
        results,
        str(output_dir / f'excel_offset_analysis_{len(results)}_functions_report.html'),
        time_tracker,
    )
    time_tracker.end_step('结果已保存')

    time_tracker.print_summary()
    time_stats_file = output_dir / f'excel_offset_analysis_{len(results)}_functions_time_stats.json'
    time_tracker.save_to_file(str(time_stats_file))

    logger.info('\n' + '=' * 80)
    logger.info('✅ Excel 分析模式完成！')
    logger.info('=' * 80)
    logger.info(f'📊 分析结果: {len(results)} 个函数')
    logger.info(f'📄 Excel 报告: {excel_file_output}')
    logger.info(f'📄 HTML 报告: {html_file}')
    logger.info(f'⏱️  时间统计: {time_stats_file}')

        if analyzer.use_llm and analyzer.llm_analyzer:
            analyzer.llm_analyzer.finalize()  # 保存所有缓存和统计
            analyzer.llm_analyzer.print_token_stats()
    return True


def resolve_excel_so_file(args) -> Path:
    if args.so_file:
        return Path(args.so_file)

    so_dir = Path(args.so_dir)
    if not so_dir.exists():
        logger.error('❌ 错误: SO 文件目录不存在: %s', so_dir)
        logger.info('   请使用 --so-file 参数指定 SO 文件路径')
        sys.exit(1)

    so_files = list(so_dir.glob('*.so'))
    if so_files:
        so_file = so_files[0]
        logger.info(f'自动选择 SO 文件: {so_file}')
        return so_file

    logger.error('❌ 错误: 在 %s 中未找到 SO 文件', so_dir)
    logger.info('   请使用 --so-file 参数指定 SO 文件路径')
    sys.exit(1)


def convert_perf_data(args, perf_data_file: Path, perf_db_file: Optional[Path], output_dir: Path) -> Optional[Path]:
    if args.skip_step1 or args.only_step3:
        return perf_db_file

    logger.info('\n' + '=' * 80)
    logger.info('Step 1: 转换 perf.data 到 perf.db')
    logger.info('=' * 80)

    if not perf_data_file.exists():
        logger.error('❌ 错误: perf.data 文件不存在: %s', perf_data_file)
        sys.exit(1)

    if perf_db_file and perf_db_file.exists() and not args.only_step1:
        logger.info(f'✅ 发现已有的 perf.db: {perf_db_file}')
        logger.info('   如需重新转换，请删除该文件或使用 --skip-step1 跳过')
        return perf_db_file

    logger.info(f'输入文件: {perf_data_file}')
    logger.info(f'输出文件: {perf_db_file}')

    converter = PerfDataToSqliteConverter(perf_data_file=str(perf_data_file), output_dir=str(output_dir))
    result = converter.convert_all()
    if not result:
        logger.error('\n❌ Step 1 失败，无法继续')
        sys.exit(1)

    return Path(result)


def run_llm_analysis(args, perf_db_file: Optional[Path], so_dir: Optional[Path], output_dir: Path):
    if args.skip_step3 or args.only_step1:
        return

    logger.info('\n' + '=' * 80)
    logger.info(f'Step 3: LLM 分析热点函数（按 {args.stat_method} 统计）')
    logger.info('=' * 80)

    if not so_dir or not so_dir.exists():
        logger.error('❌ 错误: SO 文件目录不存在: %s', so_dir)
        sys.exit(1)

    logger.info(f'SO 文件目录: {so_dir}')
    logger.info(f'统计方式: {args.stat_method}')
    logger.info(f'分析前 {args.top_n} 个函数')

    if args.stat_method == 'call_count':
        analyze_by_call_count(args, perf_db_file, so_dir, output_dir)
    else:
        analyze_by_event_count(args, perf_db_file, so_dir, output_dir)


def analyze_by_call_count(args, perf_db_file: Optional[Path], so_dir: Path, output_dir: Path):
    if not perf_db_file or not perf_db_file.exists():
        logger.info(f'❌ 错误: perf.db 文件不存在: {perf_db_file if perf_db_file else "(未指定)"}')
        logger.info('   请先运行 Step 1')
        sys.exit(1)

    logger.info(f'输入文件: {perf_db_file}')

    time_tracker = TimeTracker()
    time_tracker.start_step('初始化', '加载配置和初始化分析器')
    analyzer = MissingSymbolFunctionAnalyzer(
        perf_db_file=str(perf_db_file),
        so_dir=str(so_dir),
        use_llm=not args.no_llm,
        use_batch_llm=not args.no_batch,
        batch_size=args.batch_size,
        context=args.context,
        use_capstone_only=args.use_capstone_only,
        save_prompts=args.save_prompts,
        output_dir=str(output_dir),
        skip_decompilation=args.skip_decompilation,
    )
    time_tracker.end_step('初始化完成')

    time_tracker.start_step('分析函数', f'反汇编和 LLM 分析前 {args.top_n} 个函数')
    results = analyzer.analyze_top_functions(top_n=args.top_n)
    time_tracker.end_step(f'完成分析 {len(results)} 个函数')

    if results:
        time_tracker.start_step('保存结果', '生成 Excel 和 HTML 报告')
        output_file = analyzer.save_results(results, time_tracker=time_tracker, top_n=args.top_n)
        time_tracker.end_step('结果已保存')

        logger.info(f'\n✅ Step 3 完成！共分析了 {len(results)} 个函数')
        logger.info(f'📄 Excel 报告: {output_file}')

        time_tracker.print_summary()
        time_stats_file = output_dir / f'top{args.top_n}_missing_symbols_time_stats.json'
        time_tracker.save_to_file(str(time_stats_file))
        logger.info(f'⏱️  时间统计: {time_stats_file}')

        if analyzer.use_llm and analyzer.llm_analyzer:
            analyzer.llm_analyzer.finalize()  # 保存所有缓存和统计
            analyzer.llm_analyzer.print_token_stats()
    else:
        logger.warning('\n⚠️  没有成功分析任何函数')


def analyze_by_event_count(args, perf_db_file: Optional[Path], so_dir: Path, output_dir: Path):
    if not perf_db_file or not perf_db_file.exists():
        logger.error('❌ 错误: perf.db 文件不存在: %s', perf_db_file)
        logger.info('   请先运行 Step 1')
        sys.exit(1)

    logger.info(f'输入文件: {perf_db_file}')

    time_tracker = TimeTracker()
    time_tracker.start_step('初始化', '加载配置和初始化分析器')
    analyzer = EventCountAnalyzer(
        perf_db_file=str(perf_db_file),
        so_dir=str(so_dir),
        use_llm=not args.no_llm,
        llm_model=args.llm_model,
        use_batch_llm=not args.no_batch,
        batch_size=args.batch_size,
        context=args.context,
        use_capstone_only=args.use_capstone_only,
        save_prompts=args.save_prompts,
        output_dir=str(output_dir),
        skip_decompilation=args.skip_decompilation,
    )
    time_tracker.end_step('初始化完成')

    time_tracker.start_step('分析函数', f'反汇编和 LLM 分析前 {args.top_n} 个函数')
    results = analyzer.analyze_event_count_only(top_n=args.top_n)
    time_tracker.end_step(f'完成分析 {len(results)} 个函数')

    if results:
        time_tracker.start_step('保存结果', '生成 Excel 和 HTML 报告')
        output_dir = config.get_output_dir(args.output_dir)
        output_file = analyzer.save_event_count_results(
            results,
            time_tracker=time_tracker,
            output_dir=output_dir,
            top_n=args.top_n,
        )
        time_tracker.end_step('结果已保存')

        actual_result_count = len(results)
        Path(output_file)

        logger.info(f'\n✅ Step 3 完成！共分析了 {actual_result_count} 个函数')
        logger.info(f'📄 Excel 报告: {output_file}')

        time_tracker.print_summary()
        time_stats_file = output_dir / f'event_count_top{args.top_n}_time_stats.json'
        time_tracker.save_to_file(str(time_stats_file))
        logger.info(f'⏱️  时间统计: {time_stats_file}')

        if analyzer.use_llm and analyzer.llm_analyzer:
            analyzer.llm_analyzer.finalize()  # 保存所有缓存和统计
            analyzer.llm_analyzer.print_token_stats()
    else:
        logger.warning('\n⚠️  没有成功分析任何函数')


def run_html_symbol_replacement(args, output_dir: Path):
    if args.skip_step4 or args.only_step1 or args.only_step3:
        return

    logger.info('\n' + '=' * 80)
    logger.info('Step 4: HTML 符号替换')
    logger.info('=' * 80)

    excel_file = detect_excel_file(args, output_dir)
    if not excel_file or not excel_file.exists():
        logger.warning('⚠️  Excel 文件不存在: %s', excel_file)
        logger.info('   请先运行 Step 3 生成分析结果')
        logger.info('   跳过 Step 4')
        return

    html_input = detect_html_input(args)
    if not html_input or not html_input.exists():
        logger.info(f'⚠️  HTML 文件不存在: {html_input if html_input else "(未指定)"}')
        logger.info('   请使用 --html-input 参数指定 HTML 文件路径或目录')
        logger.info('   跳过 Step 4')
        return

    logger.info(f'\n加载函数映射: {excel_file}')
    function_mapping = load_function_mapping(excel_file)
    if not function_mapping:
        logger.warning('⚠️  没有找到函数名映射')
        logger.info('   跳过 Step 4')
        return

    logger.info(f'\n读取 HTML 文件: {html_input}')
    with open(html_input, encoding='utf-8') as f:
        html_content = f.read()

    logger.info('\n正在替换缺失符号...')
    html_content, replacement_info = replace_symbols_in_html(html_content, function_mapping)

    logger.info('\n添加免责声明和嵌入报告...')
    reference_report = build_reference_report_name(excel_file.name, args)
    relative_path = compute_relative_output_path(html_input, output_dir, args)

    # 从 Excel 文件读取数据用于生成报告
    from core.utils.symbol_replacer import load_excel_data_for_report
    report_data = None
    llm_analyzer = None
    try:
        report_data = load_excel_data_for_report(excel_file)
        logger.info(f'✅ 从 Excel 加载了 {len(report_data)} 条记录用于生成报告')
        
        # 尝试加载 LLM 统计信息
        from core.utils import common as util
        token_stats_file = Path('cache/llm_token_stats.json')
        if token_stats_file.exists():
            try:
                with token_stats_file.open('r', encoding='utf-8') as f:
                    saved_stats = json.load(f)
                # 创建一个简单的对象来存储 token 统计信息
                class SimpleLLMAnalyzer:
                    def get_token_stats(self):
                        return saved_stats
                llm_analyzer = SimpleLLMAnalyzer()
            except Exception:
                pass
    except Exception as e:
        logger.warning(f'⚠️  无法从 Excel 加载报告数据: {e}')

    html_content = add_disclaimer(
        html_content,
        reference_report_file=reference_report,
        relative_path=relative_path,
        html_report_file=None,  # 不再从文件读取
        excel_file=str(excel_file) if excel_file else None,
        report_data=report_data,
        llm_analyzer=llm_analyzer,
    )

    # 生成新的 HTML 文件，而不是直接修改原文件
    html_input_stem = html_input.stem
    html_output = html_input.parent / f'{html_input_stem}_with_inferred_symbols.html'

    logger.info(f'\n保存新文件: {html_output}')
    logger.info(f'原文件保持不变: {html_input}')
    with open(html_output, 'w', encoding='utf-8') as f:
        f.write(html_content)

    logger.info('\n✅ Step 4 完成！')
    logger.info(f'📄 原文件: {html_input}（未修改）')
    logger.info(f'📄 新文件: {html_output}')
    logger.info(f'   替换了 {len(replacement_info)} 个缺失符号')


def detect_excel_file(args, output_dir: Path) -> Optional[Path]:
    if args.only_step4:
        search_patterns = [
            f'event_count_top{args.top_n}_analysis.xlsx'
            if args.stat_method == 'event_count'
            else f'top{args.top_n}_missing_symbols_analysis.xlsx',
            'event_count_top*_analysis.xlsx'
            if args.stat_method == 'event_count'
            else 'top*_missing_symbols_analysis.xlsx',
            'event_count_top*_analysis.xlsx',
            'top*_missing_symbols_analysis.xlsx',
        ]
        for pattern in search_patterns:
            matching_files = list(output_dir.glob(pattern))
            if matching_files:
                matching_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
                logger.info(f'自动检测到 Excel 文件: {matching_files[0]}')
                return matching_files[0]
        return None

    if args.stat_method == 'event_count':
        all_event_count_files = sorted(
            output_dir.glob('event_count_top*_analysis.xlsx'),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if all_event_count_files:
            logger.info(f'使用最新的 event_count 分析文件: {all_event_count_files[0]}')
            return all_event_count_files[0]
        return output_dir / config.EVENT_COUNT_ANALYSIS_PATTERN.format(n=args.top_n)

    all_call_count_files = sorted(
        output_dir.glob('top*_missing_symbols_analysis.xlsx'),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if all_call_count_files:
        logger.info(f'使用最新的 call_count 分析文件: {all_call_count_files[0]}')
        return all_call_count_files[0]
    return output_dir / config.CALL_COUNT_ANALYSIS_PATTERN.format(n=args.top_n)


def detect_html_input(args) -> Optional[Path]:
    if args.html_input:
        html_input_path = Path(args.html_input)
        if html_input_path.is_dir():
            html_files = list(html_input_path.glob(args.html_pattern))
            if html_files:
                logger.info(f'在目录 {html_input_path} 中找到 HTML 文件: {html_files[0]}')
                return html_files[0]
            logger.info(f'⚠️  在目录 {html_input_path} 中未找到匹配 {args.html_pattern} 的文件')
            return None
        if html_input_path.is_file():
            return html_input_path
        logger.warning('⚠️  HTML 路径不存在: %s', html_input_path)
        return None

    for step_dir in config.STEP_DIRS:
        step_path = Path(step_dir)
        if step_path.exists():
            html_files = list(step_path.glob(args.html_pattern))
            if html_files:
                logger.info(f'自动找到 HTML 文件: {html_files[0]}')
                return html_files[0]
    return None


def build_reference_report_name(excel_file_name: str, args) -> str:
    if 'event_count_top' in excel_file_name:
        match = re.search(r'event_count_top(\d+)_analysis', excel_file_name)
        if match:
            return f'event_count_top{match.group(1)}_report.html'
        return f'event_count_top{args.top_n}_report.html'
    if 'top' in excel_file_name and 'missing_symbols' in excel_file_name:
        match = re.search(r'top(\d+)_missing_symbols_analysis', excel_file_name)
        if match:
            return f'top{match.group(1)}_missing_symbols_report.html'
        return f'top{args.top_n}_missing_symbols_report.html'
    if args.stat_method == 'event_count':
        return f'event_count_top{args.top_n}_report.html'
    return f'top{args.top_n}_missing_symbols_report.html'


def compute_relative_output_path(html_input: Path, output_dir: Path, args) -> str:
    html_input_path = html_input.resolve()
    output_dir_path = config.get_output_dir(args.output_dir).resolve()
    try:
        relative_path = str(output_dir_path.relative_to(html_input_path.parent))
        return relative_path.replace('\\', '/')
    except ValueError:
        html_parts = html_input_path.parts
        base_parts = Path('.').resolve().parts
        common_len = 0
        for i in range(min(len(html_parts), len(base_parts))):
            if html_parts[i] == base_parts[i]:
                common_len += 1
            else:
                break
        up_levels = len(html_parts) - common_len - 1
        return ('../' * up_levels) + str(output_dir.name)


def summarize_outputs(args, output_dir: Path):
    logger.info('\n' + '=' * 80)
    logger.info('✅ 完整工作流执行成功！')
    logger.info('=' * 80)
    logger.info('\n输出文件:')
    if not args.only_step4:
        logger.info(f'  - {output_dir}/{config.DEFAULT_PERF_DB}')
        if args.stat_method == 'event_count':
            logger.info(f'  - {output_dir}/{config.EVENT_COUNT_ANALYSIS_PATTERN.format(n=args.top_n)}')
            logger.info(f'  - {output_dir}/{config.EVENT_COUNT_REPORT_PATTERN.format(n=args.top_n)}')
        elif args.stat_method == 'call_count':
            logger.info(f'  - {output_dir}/{config.CALL_COUNT_ANALYSIS_PATTERN.format(n=args.top_n)}')
            logger.info(f'  - {output_dir}/{config.CALL_COUNT_REPORT_PATTERN.format(n=args.top_n)}')

    if not args.skip_step4 and not args.only_step1 and not args.only_step3:
        html_input = detect_html_input(args)
        if html_input and html_input.exists():
            logger.info(f'  - {html_input} (已修改，符号已替换)')


def main():
    parser = create_argument_parser()
    args = parser.parse_args()

    # 处理输出目录配置
    output_dir = config.ensure_output_dir(config.get_output_dir(args.output_dir))

    if handle_excel_mode(args, output_dir):
        return

    perf_data_file, perf_db_file, so_dir = resolve_perf_paths(args, output_dir)

    logger.info('=' * 80)
    logger.info('完整工作流：从 perf.data 到 LLM 分析报告')
    logger.info('=' * 80)

    perf_db_file = convert_perf_data(args, perf_data_file, perf_db_file, output_dir)
    if args.only_step1:
        logger.info('\n✅ Step 1 完成！')
        return

    run_llm_analysis(args, perf_db_file, so_dir, output_dir)
    run_html_symbol_replacement(args, output_dir)
    summarize_outputs(args, output_dir)


if __name__ == '__main__':
    main()
