#!/usr/bin/env python3

"""
SymRecover - 二进制符号恢复工具：支持 perf.data 和 Excel 偏移量两种模式
"""

import argparse
import json
import os
import re
import sqlite3
import sys
from pathlib import Path
from typing import Optional

from core.analyzers.event_analyzer import EventCountAnalyzer
from core.analyzers.excel_analyzer import ExcelOffsetAnalyzer
from core.analyzers.memory_flamegraph_analyzer import MemoryFlameGraphAnalyzer
from core.analyzers.perf_analyzer import PerfDataToSqliteConverter
from core.utils.config import (
    CALL_COUNT_ANALYSIS_PATTERN,
    CALL_COUNT_REPORT_PATTERN,
    DEFAULT_BATCH_SIZE,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_PERF_DATA,
    DEFAULT_PERF_DB,
    DEFAULT_TOP_N,
    EVENT_COUNT_ANALYSIS_PATTERN,
    EVENT_COUNT_REPORT_PATTERN,
    HTML_REPORT_PATTERN,
    STEP_DIRS,
    config,
)
from core.utils.logger import get_logger, setup_logging
from core.utils.perf_converter import MissingSymbolFunctionAnalyzer
from core.utils.symbol_replacer import (
    add_disclaimer,
    load_excel_data_for_report,
    load_function_mapping,
    replace_symbols_in_html,
)
from core.utils.time_tracker import TimeTracker

logger = get_logger(__name__)


def _is_dir_writable(p: Path) -> bool:
    try:
        p.mkdir(parents=True, exist_ok=True)
        probe = p / '.writable_probe'
        probe.write_text('ok', encoding='utf-8')
        probe.unlink(missing_ok=True)
        return True
    except Exception:
        return False


def _ensure_writable_cwd():
    """
    在 macOS App 打包场景下，工具可能从只读目录启动（如 .app/Contents/Resources），
    依赖或默认输出（output/cache）使用相对路径时会触发 EROFS。

    仅在 cwd 不可写的情况下，将 cwd 切换到用户主目录下的可写运行目录。
    """
    if sys.platform != 'darwin':
        return
    cwd = Path.cwd()
    if _is_dir_writable(cwd):
        return
    runtime_dir = Path.home() / 'ArkAnalyzer-HapRay' / 'runtime'
    runtime_dir.mkdir(parents=True, exist_ok=True)
    os.chdir(str(runtime_dir))


def create_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description='SymRecover - 二进制符号恢复工具：支持 perf.data、Excel 偏移量和内存模式火焰图三种模式',
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

  # 内存模式（从火焰图 HTML 文件中提取符号）
  python3 main.py --memory-mode --html-dir /path/to/flamegraphs --so-dir /path/to/so/directory

  # 内存模式（指定分析数量）
  python3 main.py --memory-mode --html-dir /path/to/flamegraphs --so-dir /path/to/so/directory --top-n 100
        """,
    )

    # 模式选择：Excel 分析模式、perf 分析模式或内存模式
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
    parser.add_argument(
        '--memory-mode',
        action='store_true',
        help='启用内存模式：从火焰图 HTML 文件中提取符号地址进行分析',
    )
    parser.add_argument(
        '--html-dir',
        type=str,
        default=None,
        help='火焰图 HTML 文件目录（内存模式必需）。包含需要分析的 HTML 火焰图文件',
    )

    # 输入参数（perf 分析模式）
    parser.add_argument(
        '--perf-data',
        type=str,
        default=DEFAULT_PERF_DATA,
        help=f'perf.data 文件路径（默认: {DEFAULT_PERF_DATA}，仅 perf 分析模式）',
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
        help='SO 文件目录，包含需要分析的 SO 库文件（可选，如果提供了 --so-file 则不需要）',
    )

    # 输出目录参数
    parser.add_argument(
        '--output-dir',
        '--output',
        type=str,
        default=None,
        help=f'输出目录，用于存储所有分析结果和 perf.db 等（默认: {DEFAULT_OUTPUT_DIR}）',
    )

    # 分析参数
    parser.add_argument(
        '--top-n',
        type=int,
        default=DEFAULT_TOP_N,
        help=f'分析前 N 个函数（默认: {DEFAULT_TOP_N}）',
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
        '--batch-size',
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help=f'批量分析时每个 prompt 包含的函数数量（默认: {DEFAULT_BATCH_SIZE}，建议范围: 3-10）。当 batch-size > 1 时使用批量分析，否则使用单个函数分析',
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
        help=f'HTML 输入文件路径或目录（默认: 自动查找 {", ".join(STEP_DIRS)} 目录下的 {HTML_REPORT_PATTERN}）',
    )
    parser.add_argument(
        '--html-pattern',
        type=str,
        default=HTML_REPORT_PATTERN,
        help=f'HTML 文件搜索模式（默认: {HTML_REPORT_PATTERN}）',
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
    parser.add_argument(
        '--open-source-lib',
        type=str,
        default=None,
        help='开源库名称（可选，如 "ffmpeg", "openssl", "libcurl" 等）。如果指定，会告诉大模型这是基于该开源库的定制版本，大模型可以利用对开源库的知识来更准确地推断函数名和功能',
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
            perf_db_file = output_dir / DEFAULT_PERF_DB
        except Exception:
            perf_db_file = None
    else:
        perf_db_file = None

    so_dir = None
    if not args.only_step1:
        # 如果提供了 --so-file，直接使用该文件（而不是目录）
        if args.so_file:
            so_file_path = Path(args.so_file)
            if so_file_path.exists():
                # 直接传递文件路径，find_so_file 会特殊处理
                so_dir = so_file_path.resolve()
                logger.info(f'Using specific SO file: {so_dir}')
            else:
                logger.error('❌ Error: SO file does not exist: %s', so_file_path)
                sys.exit(1)
        elif args.so_dir:
            so_dir = resolve_directory(args.so_dir)
    return perf_data_file, perf_db_file, so_dir


def handle_excel_mode(args, output_dir: Path) -> bool:
    if not args.excel_file:
        return False

    logger.info('=' * 80)
    logger.info('Excel Analysis Mode: Reading offsets from Excel file for analysis')
    logger.info('=' * 80)

    excel_file = Path(args.excel_file)
    if not excel_file.exists():
        logger.error('❌ Error: Excel file does not exist: %s', excel_file)
        sys.exit(1)

    so_file = resolve_excel_so_file(args)
    if not so_file.exists():
        logger.error('❌ Error: SO file does not exist: %s', so_file)
        sys.exit(1)

    logger.info(f'Input file: {excel_file}')
    logger.info(f'SO file: {so_file}')

    time_tracker = TimeTracker()
    time_tracker.start_step('Initialization', 'Loading configuration and initializing analyzer')

    try:
        analyzer = ExcelOffsetAnalyzer(
            so_file=str(so_file),
            excel_file=str(excel_file),
            use_llm=not args.no_llm,
            llm_model=args.llm_model,
            batch_size=args.batch_size,
            context=args.context,
            save_prompts=args.save_prompts,
            output_dir=str(output_dir),
            skip_decompilation=args.skip_decompilation,
            open_source_lib=args.open_source_lib,
        )
        time_tracker.end_step('初始化')
    except Exception:
        logger.exception('❌ Initialization failed')
        sys.exit(1)

    time_tracker.start_step('Analyzing offsets', 'Disassembly and LLM analysis')
    results = analyzer.analyze_all()
    time_tracker.end_step(f'Completed analysis of {len(results)} functions')

    if not results:
        logger.error('❌ No analysis results')
        sys.exit(1)

    time_tracker.start_step('Saving results', 'Generating Excel and HTML reports')
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
    time_tracker.end_step('Results saved')

    time_tracker.print_summary()
    time_stats_file = output_dir / f'excel_offset_analysis_{len(results)}_functions_time_stats.json'
    time_tracker.save_to_file(str(time_stats_file))

    logger.info('\n' + '=' * 80)
    logger.info('✅ Excel Analysis Mode Completed!')
    logger.info('=' * 80)
    logger.info(f'📊 Analysis results: {len(results)} functions')
    logger.info(f'📄 Excel report: {excel_file_output}')
    logger.info(f'📄 HTML report: {html_file}')
    logger.info(f'⏱️  Time statistics: {time_stats_file}')

    if analyzer.use_llm and analyzer.llm_analyzer:
        analyzer.llm_analyzer.finalize()  # 保存所有缓存和统计
        analyzer.llm_analyzer.print_token_stats()
    return True


def resolve_excel_so_file(args) -> Path:
    if args.so_file:
        return Path(args.so_file)

    so_dir = Path(args.so_dir)
    if not so_dir.exists():
        logger.error('❌ Error: SO file directory does not exist: %s', so_dir)
        logger.info('   Please use --so-file parameter to specify SO file path')
        sys.exit(1)

    so_files = list(so_dir.glob('*.so'))
    if so_files:
        so_file = so_files[0]
        logger.info(f'Auto-selected SO file: {so_file}')
        return so_file

    logger.error('❌ Error: No SO file found in %s', so_dir)
    logger.info('   Please use --so-file parameter to specify SO file path')
    sys.exit(1)


def convert_perf_data(args, perf_data_file: Path, perf_db_file: Optional[Path], output_dir: Path) -> Optional[Path]:
    if args.skip_step1 or args.only_step3:
        return perf_db_file

    logger.info('\n' + '=' * 80)
    logger.info('Step 1: Convert perf.data to perf.db')
    logger.info('=' * 80)

    if not perf_data_file.exists():
        logger.error('❌ Error: perf.data file does not exist: %s', perf_data_file)
        sys.exit(1)

    if perf_db_file and perf_db_file.exists() and not args.only_step1:
        logger.info(f'✅ Found existing perf.db: {perf_db_file}')
        logger.info('   To reconvert, please delete this file or use --skip-step1 to skip')
        return perf_db_file

    logger.info(f'Input file: {perf_data_file}')
    logger.info(f'Output file: {perf_db_file}')

    converter = PerfDataToSqliteConverter(perf_data_file=str(perf_data_file), output_dir=str(output_dir))
    result = converter.convert_all()
    if not result:
        logger.error('\n❌ Step 1 failed, cannot continue')
        sys.exit(1)

    return Path(result)


def run_llm_analysis(args, perf_db_file: Optional[Path], so_dir: Optional[Path], output_dir: Path):
    if args.skip_step3 or args.only_step1:
        return

    logger.info('\n' + '=' * 80)
    logger.info(f'Step 3: LLM Analysis of Hot Functions (by {args.stat_method})')
    logger.info('=' * 80)

    if not so_dir or not so_dir.exists():
        logger.error('❌ Error: SO file directory does not exist: %s', so_dir)
        sys.exit(1)

    if so_dir and so_dir.is_file():
        logger.info(f'SO file: {so_dir}')
    else:
        logger.info(f'SO file directory: {so_dir}')
    logger.info(f'Statistics method: {args.stat_method}')
    logger.info(f'Analyzing top {args.top_n} functions')

    if args.stat_method == 'call_count':
        analyze_by_call_count(args, perf_db_file, so_dir, output_dir)
    else:
        analyze_by_event_count(args, perf_db_file, so_dir, output_dir)


def analyze_by_call_count(args, perf_db_file: Optional[Path], so_dir: Path, output_dir: Path):
    if not perf_db_file or not perf_db_file.exists():
        logger.info(f'❌ Error: perf.db file does not exist: {perf_db_file if perf_db_file else "(not specified)"}')
        logger.info('   Please run Step 1 first')
        sys.exit(1)

    logger.info(f'Input file: {perf_db_file}')

    time_tracker = TimeTracker()
    time_tracker.start_step('Initialization', 'Loading configuration and initializing analyzer')
    analyzer = MissingSymbolFunctionAnalyzer(
        perf_db_file=str(perf_db_file),
        so_dir=str(so_dir),
        use_llm=not args.no_llm,
        batch_size=args.batch_size,
        context=args.context,
        use_capstone_only=args.use_capstone_only,
        save_prompts=args.save_prompts,
        output_dir=str(output_dir),
        skip_decompilation=args.skip_decompilation,
        open_source_lib=args.open_source_lib,
    )
    time_tracker.end_step('Initialization completed')

    time_tracker.start_step('Analyzing functions', f'Disassembly and LLM analysis of top {args.top_n} functions')
    results = analyzer.analyze_top_functions(top_n=args.top_n)
    time_tracker.end_step(f'Completed analysis of {len(results)} functions')

    if results:
        time_tracker.start_step('Saving results', 'Generating Excel and HTML reports')
        output_file = analyzer.save_results(results, time_tracker=time_tracker, top_n=args.top_n)
        time_tracker.end_step('Results saved')

        logger.info(f'\n✅ Step 3 completed! Analyzed {len(results)} functions')
        logger.info(f'📄 Excel report: {output_file}')

        time_tracker.print_summary()
        time_stats_file = output_dir / f'top{args.top_n}_missing_symbols_time_stats.json'
        time_tracker.save_to_file(str(time_stats_file))
        logger.info(f'⏱️  Time statistics: {time_stats_file}')

        if analyzer.use_llm and analyzer.llm_analyzer:
            analyzer.llm_analyzer.finalize()  # 保存所有缓存和统计
            analyzer.llm_analyzer.print_token_stats()
    else:
        logger.warning('\n⚠️  No functions were successfully analyzed')


def analyze_by_event_count(args, perf_db_file: Optional[Path], so_dir: Path, output_dir: Path):
    if not perf_db_file or not perf_db_file.exists():
        logger.error('❌ Error: perf.db file does not exist: %s', perf_db_file)
        logger.info('   Please run Step 1 first')
        sys.exit(1)

    logger.info(f'Input file: {perf_db_file}')

    time_tracker = TimeTracker()
    time_tracker.start_step('Initialization', 'Loading configuration and initializing analyzer')
    analyzer = EventCountAnalyzer(
        perf_db_file=str(perf_db_file),
        so_dir=str(so_dir),
        use_llm=not args.no_llm,
        llm_model=args.llm_model,
        batch_size=args.batch_size,
        context=args.context,
        use_capstone_only=args.use_capstone_only,
        save_prompts=args.save_prompts,
        output_dir=str(output_dir),
        skip_decompilation=args.skip_decompilation,
        open_source_lib=args.open_source_lib,
    )
    time_tracker.end_step('Initialization completed')

    time_tracker.start_step('Analyzing functions', f'Disassembly and LLM analysis of top {args.top_n} functions')
    results = analyzer.analyze_event_count_only(top_n=args.top_n)
    time_tracker.end_step(f'完成分析 {len(results)} 个函数')

    if results:
        time_tracker.start_step('Saving results', 'Generating Excel and HTML reports')
        output_dir = config.get_output_dir(args.output_dir)
        output_file = analyzer.save_event_count_results(
            results,
            time_tracker=time_tracker,
            output_dir=output_dir,
            top_n=args.top_n,
        )
        time_tracker.end_step('Results saved')

        actual_result_count = len(results)
        Path(output_file)

        logger.info(f'\n✅ Step 3 completed! Analyzed {actual_result_count} functions')
        logger.info(f'📄 Excel report: {output_file}')

        time_tracker.print_summary()
        time_stats_file = output_dir / f'event_count_top{args.top_n}_time_stats.json'
        time_tracker.save_to_file(str(time_stats_file))
        logger.info(f'⏱️  Time statistics: {time_stats_file}')

        if analyzer.use_llm and analyzer.llm_analyzer:
            analyzer.llm_analyzer.finalize()  # 保存所有缓存和统计
            analyzer.llm_analyzer.print_token_stats()
    else:
        logger.warning('\n⚠️  No functions were successfully analyzed')


def run_html_symbol_replacement(args, output_dir: Path):
    if args.skip_step4 or args.only_step1 or args.only_step3:
        return

    logger.info('\n' + '=' * 80)
    logger.info('Step 4: HTML Symbol Replacement')
    logger.info('=' * 80)

    excel_file = detect_excel_file(args, output_dir)
    if not excel_file or not excel_file.exists():
        logger.warning('⚠️  Excel file does not exist: %s', excel_file)
        logger.info('   Please run Step 3 first to generate analysis results')
        logger.info('   Skipping Step 4')
        return

    html_input = detect_html_input(args)
    if not html_input or not html_input.exists():
        logger.info(f'⚠️  HTML file does not exist: {html_input if html_input else "(not specified)"}')
        logger.info('   Please use --html-input parameter to specify HTML file path or directory')
        logger.info('   Skipping Step 4')
        return

    logger.info(f'\nLoading function mapping: {excel_file}')
    function_mapping = load_function_mapping(excel_file)
    if not function_mapping:
        logger.warning('⚠️  No function name mapping found')
        logger.info('   Skipping Step 4')
        return

    logger.info(f'\nReading HTML file: {html_input}')
    with open(html_input, encoding='utf-8') as f:
        html_content = f.read()

    logger.info('\nReplacing missing symbols...')
    html_content, replacement_info = replace_symbols_in_html(html_content, function_mapping)

    logger.info('\nAdding disclaimer and embedding report...')
    reference_report = build_reference_report_name(excel_file.name, args)
    relative_path = compute_relative_output_path(html_input, output_dir, args)

    # 从 Excel 文件读取数据用于生成报告
    report_data = None
    llm_analyzer = None
    try:
        report_data = load_excel_data_for_report(excel_file)
        logger.info(f'✅ Loaded {len(report_data)} records from Excel for report generation')

        # 尝试加载 LLM 统计信息

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
        logger.warning(f'⚠️  Failed to load report data from Excel: {e}')

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

    logger.info(f'\nSaving new file: {html_output}')
    logger.info(f'Original file unchanged: {html_input}')
    with open(html_output, 'w', encoding='utf-8') as f:
        f.write(html_content)

    logger.info('\n✅ Step 4 completed!')
    logger.info(f'📄 Original file: {html_input} (unchanged)')
    logger.info(f'📄 New file: {html_output}')
    logger.info(f'   Replaced {len(replacement_info)} missing symbols')


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
                logger.info(f'Auto-detected Excel file: {matching_files[0]}')
                return matching_files[0]
        return None

    if args.stat_method == 'event_count':
        all_event_count_files = sorted(
            output_dir.glob('event_count_top*_analysis.xlsx'),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if all_event_count_files:
            logger.info(f'Using latest event_count analysis file: {all_event_count_files[0]}')
            return all_event_count_files[0]
        return output_dir / EVENT_COUNT_ANALYSIS_PATTERN.format(n=args.top_n)

    all_call_count_files = sorted(
        output_dir.glob('top*_missing_symbols_analysis.xlsx'),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if all_call_count_files:
        logger.info(f'Using latest call_count analysis file: {all_call_count_files[0]}')
        return all_call_count_files[0]
    return output_dir / CALL_COUNT_ANALYSIS_PATTERN.format(n=args.top_n)


def detect_html_input(args) -> Optional[Path]:
    if args.html_input:
        html_input_path = Path(args.html_input)
        if html_input_path.is_dir():
            html_files = list(html_input_path.glob(args.html_pattern))
            if html_files:
                logger.info(f'Found HTML file in directory {html_input_path}: {html_files[0]}')
                return html_files[0]
            logger.info(f'⚠️  No file matching {args.html_pattern} found in directory {html_input_path}')
            return None
        if html_input_path.is_file():
            return html_input_path
        logger.warning('⚠️  HTML path does not exist: %s', html_input_path)
        return None

    for step_dir in STEP_DIRS:
        step_path = Path(step_dir)
        if step_path.exists():
            html_files = list(step_path.glob(args.html_pattern))
            if html_files:
                logger.info(f'Auto-found HTML file: {html_files[0]}')
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
    logger.info('✅ Complete workflow executed successfully!')
    logger.info('=' * 80)
    logger.info('\nOutput files:')
    if not args.only_step4:
        logger.info(f'  - {output_dir}/{DEFAULT_PERF_DB}')
        if args.stat_method == 'event_count':
            logger.info(f'  - {output_dir}/{EVENT_COUNT_ANALYSIS_PATTERN.format(n=args.top_n)}')
            logger.info(f'  - {output_dir}/{EVENT_COUNT_REPORT_PATTERN.format(n=args.top_n)}')
        elif args.stat_method == 'call_count':
            logger.info(f'  - {output_dir}/{CALL_COUNT_ANALYSIS_PATTERN.format(n=args.top_n)}')
            logger.info(f'  - {output_dir}/{CALL_COUNT_REPORT_PATTERN.format(n=args.top_n)}')

    if not args.skip_step4 and not args.only_step1 and not args.only_step3:
        html_input = detect_html_input(args)
        if html_input and html_input.exists():
            logger.info(f'  - {html_input} (modified, symbols replaced)')


def handle_memory_mode(args, output_dir: Path):
    """处理内存模式：从火焰图 HTML 文件中提取符号并恢复"""
    if not args.memory_mode:
        return False

    logger.info('=' * 80)
    logger.info('内存模式：从火焰图 HTML 文件中提取符号地址')
    logger.info('=' * 80)

    # 验证参数
    if not args.html_dir:
        logger.error('❌ 错误: 内存模式需要指定 --html-dir 参数')
        sys.exit(1)

    html_dir = Path(args.html_dir)
    if not html_dir.exists():
        logger.error(f'❌ 错误: HTML 目录不存在: {html_dir}')
        sys.exit(1)

    so_dir = args.so_dir
    if not so_dir:
        logger.error('❌ 错误: 内存模式需要指定 --so-dir 参数')
        sys.exit(1)

    so_dir = Path(so_dir)
    if not so_dir.exists():
        logger.error(f'❌ 错误: SO 目录不存在: {so_dir}')
        sys.exit(1)

    # 创建内存模式分析器
    memory_analyzer = MemoryFlameGraphAnalyzer(
        html_dir=str(html_dir),
        so_dir=str(so_dir),
        output_dir=str(output_dir),
    )

    # 处理所有 HTML 文件，提取符号并创建 perf.db
    perf_db_file, html_symbols = memory_analyzer.process_all_html_files()

    # 运行 LLM 分析（使用创建的 perf.db）
    logger.info('\n' + '=' * 80)
    logger.info('开始符号恢复分析')
    logger.info('=' * 80)

    run_llm_analysis(args, perf_db_file, so_dir, output_dir)

    # 替换所有 HTML 文件中的符号
    logger.info('\n' + '=' * 80)
    logger.info('替换火焰图 HTML 文件中的符号')
    logger.info('=' * 80)

    # 加载函数映射
    if args.stat_method == 'event_count':
        excel_file = output_dir / EVENT_COUNT_ANALYSIS_PATTERN.format(n=args.top_n)
    else:
        excel_file = output_dir / CALL_COUNT_ANALYSIS_PATTERN.format(n=args.top_n)

    if not excel_file.exists():
        logger.error(f'❌ 错误: Excel 分析文件不存在: {excel_file}')
        logger.info('   请先完成符号恢复分析')
        sys.exit(1)

    from core.utils.symbol_replacer import load_function_mapping, replace_symbols_in_html

    function_mapping = load_function_mapping(excel_file)
    logger.info(f'✅ 加载了 {len(function_mapping)} 个函数映射')
    
    if len(function_mapping) == 0:
        logger.warning('⚠️  警告: 没有函数映射，可能是未使用 LLM 分析')
        logger.warning('   建议使用 LLM 分析（移除 --no-llm 参数）以获得符号恢复结果')
        logger.warning('   将继续处理，但不会替换任何符号')

    # 处理每个 HTML 文件
    html_files = list(html_dir.glob('*.html'))
    output_html_dir = output_dir / 'memory_flamegraphs_recovered'
    output_html_dir.mkdir(parents=True, exist_ok=True)

    for html_file in html_files:
        logger.info(f'处理: {html_file.name}')
        try:
            with open(html_file, 'r', encoding='utf-8', errors='ignore') as f:
                html_content = f.read()

            # 替换符号
            # replace_symbols_in_html 返回 (html_content, replacement_info) 元组
            replaced_html, replacement_info = replace_symbols_in_html(html_content, function_mapping)

            # 保存到输出目录
            output_file = output_html_dir / html_file.name
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(replaced_html)
            
            logger.info(f'    替换了 {len(replacement_info)} 个符号')

            logger.info(f'  ✅ 已保存: {output_file}')
        except Exception as e:
            logger.error(f'  ❌ 处理失败: {html_file.name}, 错误: {e}')

    logger.info(f'\n✅ 所有火焰图已处理完成，输出目录: {output_html_dir}')
    return True


def main():
    _ensure_writable_cwd()
    parser = create_argument_parser()
    args = parser.parse_args()

    # 处理输出目录配置
    output_dir = config.ensure_output_dir(config.get_output_dir(args.output_dir))
    setup_logging(output_dir)

    # 处理内存模式
    if handle_memory_mode(args, output_dir):
        return

    # 处理 Excel 模式
    if handle_excel_mode(args, output_dir):
        return

    # 处理 perf 模式（默认）
    perf_data_file, perf_db_file, so_dir = resolve_perf_paths(args, output_dir)

    logger.info('=' * 80)
    logger.info('Complete workflow: From perf.data to LLM analysis report')
    logger.info('=' * 80)

    perf_db_file = convert_perf_data(args, perf_data_file, perf_db_file, output_dir)
    if args.only_step1:
        logger.info('\n✅ Step 1 completed!')
        return

    run_llm_analysis(args, perf_db_file, so_dir, output_dir)
    run_html_symbol_replacement(args, output_dir)
    summarize_outputs(args, output_dir)


if __name__ == '__main__':
    main()
