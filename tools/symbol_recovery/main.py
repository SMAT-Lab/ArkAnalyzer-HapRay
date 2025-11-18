#!/usr/bin/env python3

"""
SymRecover - 二进制符号恢复工具：支持 perf.data 和 Excel 偏移量两种模式
"""

import argparse
import os
import re
import sys
from pathlib import Path

from analyzers.event_analyzer import EventCountAnalyzer
from analyzers.excel_analyzer import ExcelOffsetAnalyzer
from analyzers.perf_analyzer import PerfDataToSqliteConverter
from utils import config
from utils.logger import get_logger
from utils.perf_converter import MissingSymbolFunctionAnalyzer
from utils.symbol_replacer import (
    add_disclaimer,
    load_function_mapping,
    replace_symbols_in_html,
)
from utils.time_tracker import TimeTracker

logger = get_logger(__name__)


def main():
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

    args = parser.parse_args()

    # 处理输出目录配置
    output_dir = config.get_output_dir(args.output_dir)
    config.ensure_output_dir(output_dir)

    # ========================================================================
    # Excel 分析模式
    # ========================================================================
    if args.excel_file:
        logger.info('=' * 80)
        logger.info('Excel 分析模式：从 Excel 文件读取偏移量进行分析')
        logger.info('=' * 80)

        excel_file = Path(args.excel_file)
        if not excel_file.exists():
            logger.error('❌ 错误: Excel 文件不存在: %s', excel_file)
            sys.exit(1)

        # 确定 SO 文件
        if args.so_file:
            so_file = Path(args.so_file)
        else:
            # 如果没有指定 --so-file，尝试从 --so-dir 中查找
            so_dir = Path(args.so_dir)
            if not so_dir.exists():
                logger.error('❌ 错误: SO 文件目录不存在: %s', so_dir)
                logger.info('   请使用 --so-file 参数指定 SO 文件路径')
                sys.exit(1)

            # 尝试查找第一个 .so 文件
            so_file = None
            so_files = list(so_dir.glob('*.so'))
            if so_files:
                so_file = so_files[0]  # 使用第一个找到的 .so 文件
                logger.info(f'自动选择 SO 文件: {so_file}')

            if not so_file:
                logger.error('❌ 错误: 在 %s 中未找到 SO 文件', so_dir)
                logger.info('   请使用 --so-file 参数指定 SO 文件路径')
                sys.exit(1)

        if not so_file.exists():
            logger.error('❌ 错误: SO 文件不存在: %s', so_file)
            sys.exit(1)

        logger.info(f'输入文件: {excel_file}')
        logger.info(f'SO 文件: {so_file}')

        # 创建时间跟踪器
        time_tracker = TimeTracker()
        time_tracker.start_step('初始化', '加载配置和初始化分析器')

        # 初始化分析器
        try:
            analyzer = ExcelOffsetAnalyzer(
                so_file=str(so_file),
                excel_file=str(excel_file),
                use_llm=not args.no_llm,
                llm_model=args.llm_model,
                use_batch_llm=not args.no_batch,
                batch_size=args.batch_size,
                context=args.context,
            )
            time_tracker.end_step('初始化')
        except Exception:
            logger.exception('❌ 初始化失败')
            sys.exit(1)

        # 分析所有偏移量
        time_tracker.start_step('分析偏移量', '反汇编和 LLM 分析')
        results = analyzer.analyze_all()
        time_tracker.end_step(f'完成分析 {len(results)} 个函数')

        if not results:
            logger.error('❌ 没有分析结果')
            sys.exit(1)

        # 保存结果
        time_tracker.start_step('保存结果', '生成 Excel 和 HTML 报告')

        # 使用配置模块获取输出目录
        output_dir = config.get_output_dir(args.output_dir)
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

        # 打印时间统计
        time_tracker.print_summary()

        # 保存时间统计
        time_stats_file = output_dir / f'excel_offset_analysis_{len(results)}_functions_time_stats.json'
        time_tracker.save_to_file(str(time_stats_file))

        # 打印总结
        logger.info('\n' + '=' * 80)
        logger.info('✅ Excel 分析模式完成！')
        logger.info('=' * 80)
        logger.info(f'📊 分析结果: {len(results)} 个函数')
        logger.info(f'📄 Excel 报告: {excel_file_output}')
        logger.info(f'📄 HTML 报告: {html_file}')
        logger.info(f'⏱️  时间统计: {time_stats_file}')

        if analyzer.use_llm and analyzer.llm_analyzer:
            analyzer.llm_analyzer.print_token_stats()

        return

    # ========================================================================
    # perf 分析模式（原有流程）
    # ========================================================================
    # 检查输入文件（处理中文路径编码问题）
    # 尝试多种方式解析路径，确保中文路径正确
    try:
        # 方法1: 直接使用 Path
        perf_data_file = Path(args.perf_data)
        if not perf_data_file.exists():
            # 方法2: 尝试 resolve()
            perf_data_file = Path(args.perf_data).resolve()
        if not perf_data_file.exists():
            # 方法3: 尝试使用 os.path 然后转换
            abs_path = os.path.abspath(args.perf_data)
            perf_data_file = Path(abs_path)
    except Exception:
        perf_data_file = Path(args.perf_data)

    # 初始化 perf_db_file（如果未指定，将在 Step 1 中生成）
    # 注意：output_dir 已在上面定义
    if args.perf_db:
        perf_db_file = Path(args.perf_db)
    # 如果未指定，使用统一的输出目录
    elif args.perf_data:
        try:
            # 使用统一的输出目录
            perf_db_file = output_dir / config.DEFAULT_PERF_DB
        except Exception:
            perf_db_file = None
    else:
        perf_db_file = None

    # 只有在需要 SO 目录时才处理（Step 3 需要）
    so_dir = None
    if args.so_dir and not args.only_step1:
        try:
            so_dir = Path(args.so_dir)
            if not so_dir.exists():
                so_dir = Path(args.so_dir).resolve()
            if not so_dir.exists():
                abs_path = os.path.abspath(args.so_dir)
                so_dir = Path(abs_path)
        except Exception:
            so_dir = Path(args.so_dir) if args.so_dir else None

    logger.info('=' * 80)
    logger.info('完整工作流：从 perf.data 到 LLM 分析报告')
    logger.info('=' * 80)

    # ========================================================================
    # Step 1: 转换 perf.data 到 perf.db
    # ========================================================================
    if not args.skip_step1 and not args.only_step3:
        logger.info('\n' + '=' * 80)
        logger.info('Step 1: 转换 perf.data 到 perf.db')
        logger.info('=' * 80)

        if not perf_data_file.exists():
            logger.error('❌ 错误: perf.data 文件不存在: %s', perf_data_file)
            sys.exit(1)

        if perf_db_file and perf_db_file.exists() and not args.only_step1:
            logger.info(f'✅ 发现已有的 perf.db: {perf_db_file}')
            logger.info('   如需重新转换，请删除该文件或使用 --skip-step1 跳过')
        else:
            logger.info(f'输入文件: {perf_data_file}')
            logger.info(f'输出文件: {perf_db_file}')

            converter = PerfDataToSqliteConverter(perf_data_file=str(perf_data_file), output_dir=str(output_dir))

            result = converter.convert_all()
            if not result:
                logger.error('\n❌ Step 1 失败，无法继续')
                sys.exit(1)

            perf_db_file = Path(result)

        if args.only_step1:
            logger.info('\n✅ Step 1 完成！')
            return

    # ========================================================================
    # Step 3: LLM 分析热点函数
    # ========================================================================
    if not args.skip_step3 and not args.only_step1:
        logger.info('\n' + '=' * 80)
        logger.info(f'Step 3: LLM 分析热点函数（按 {args.stat_method} 统计）')
        logger.info('=' * 80)

        if not so_dir.exists():
            logger.error('❌ 错误: SO 文件目录不存在: %s', so_dir)
            sys.exit(1)

        logger.info(f'SO 文件目录: {so_dir}')
        logger.info(f'统计方式: {args.stat_method}')
        logger.info(f'分析前 {args.top_n} 个函数')

        if args.stat_method == 'call_count':
            # 按调用次数统计（直接从 perf.db 读取，不再需要 Excel 文件）
            if not perf_db_file or not perf_db_file.exists():
                logger.info(f'❌ 错误: perf.db 文件不存在: {perf_db_file if perf_db_file else "(未指定)"}')
                logger.info('   请先运行 Step 1')
                sys.exit(1)

            logger.info(f'输入文件: {perf_db_file}')

            # 创建时间跟踪器
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
            )
            time_tracker.end_step('初始化完成')

            # 分析函数
            time_tracker.start_step('分析函数', f'反汇编和 LLM 分析前 {args.top_n} 个函数')
            results = analyzer.analyze_top_functions(top_n=args.top_n)
            time_tracker.end_step(f'完成分析 {len(results)} 个函数')

            if results:
                time_tracker.start_step('保存结果', '生成 Excel 和 HTML 报告')
                output_file = analyzer.save_results(results, time_tracker=time_tracker, top_n=args.top_n)
                time_tracker.end_step('结果已保存')

                logger.info(f'\n✅ Step 3 完成！共分析了 {len(results)} 个函数')
                logger.info(f'📄 Excel 报告: {output_file}')

                # 打印时间统计
                time_tracker.print_summary()

                # 保存时间统计
                time_stats_file = output_dir / f'top{args.top_n}_missing_symbols_time_stats.json'
                time_tracker.save_to_file(str(time_stats_file))
                logger.info(f'⏱️  时间统计: {time_stats_file}')

                if analyzer.use_llm and analyzer.llm_analyzer:
                    analyzer.llm_analyzer.print_token_stats()
            else:
                logger.warning('\n⚠️  没有成功分析任何函数')

        elif args.stat_method == 'event_count':
            # 按 event_count 统计
            if not perf_db_file or not perf_db_file.exists():
                logger.error('❌ 错误: perf.db 文件不存在: %s', perf_db_file)
                logger.info('   请先运行 Step 1')
                sys.exit(1)

            logger.info(f'输入文件: {perf_db_file}')

            # 创建时间跟踪器
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
            )
            time_tracker.end_step('初始化完成')

            # 分析 event_count top100
            time_tracker.start_step('分析函数', f'反汇编和 LLM 分析前 {args.top_n} 个函数')
            results = analyzer.analyze_event_count_only(top_n=args.top_n)
            time_tracker.end_step(f'完成分析 {len(results)} 个函数')

            if results:
                time_tracker.start_step('保存结果', '生成 Excel 和 HTML 报告')
                # 使用配置模块获取输出目录
                output_dir = config.get_output_dir(args.output_dir)
                output_file = analyzer.save_event_count_results(
                    results,
                    time_tracker=time_tracker,
                    output_dir=output_dir,
                    top_n=args.top_n,
                )
                time_tracker.end_step('结果已保存')

                # 保存实际生成的文件路径（用于 Step 4）
                actual_result_count = len(results)
                Path(output_file)

                logger.info(f'\n✅ Step 3 完成！共分析了 {actual_result_count} 个函数')
                logger.info(f'📄 Excel 报告: {output_file}')

                # 打印时间统计
                time_tracker.print_summary()

                # 保存时间统计
                # output_dir 已在上面定义
                time_stats_file = output_dir / f'event_count_top{args.top_n}_time_stats.json'
                time_tracker.save_to_file(str(time_stats_file))
                logger.info(f'⏱️  时间统计: {time_stats_file}')

                if analyzer.use_llm and analyzer.llm_analyzer:
                    analyzer.llm_analyzer.print_token_stats()
            else:
                logger.warning('\n⚠️  没有成功分析任何函数')

    # ========================================================================
    # Step 4: HTML 符号替换
    # ========================================================================
    if (args.only_step4) or (not args.skip_step4 and not args.only_step1 and not args.only_step3):
        logger.info('\n' + '=' * 80)
        logger.info('Step 4: HTML 符号替换')
        logger.info('=' * 80)

        # 1. 确定 Excel 输入文件（Step 3 的输出）
        excel_file = None

        # 如果是 only_step4，需要自动检测使用哪个 Excel 文件
        if args.only_step4:
            # 尝试查找可用的 Excel 文件（按优先级排序）
            # output_dir 已在上面定义
            search_patterns = [
                # 先尝试精确匹配（根据 stat_method 和 top_n）
                f'event_count_top{args.top_n}_analysis.xlsx'
                if args.stat_method == 'event_count'
                else f'top{args.top_n}_missing_symbols_analysis.xlsx',
                # 然后尝试查找所有 event_count 或 call_count 文件，按修改时间排序
                'event_count_top*_analysis.xlsx'
                if args.stat_method == 'event_count'
                else 'top*_missing_symbols_analysis.xlsx',
                # 最后尝试通用模式
                'event_count_top*_analysis.xlsx',
                'top*_missing_symbols_analysis.xlsx',
            ]

            for pattern in search_patterns:
                matching_files = list(output_dir.glob(pattern))
                if matching_files:
                    # 按修改时间排序，使用最新的文件
                    matching_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
                    excel_file = matching_files[0]
                    logger.info(f'自动检测到 Excel 文件: {excel_file}')
                    break
        # 正常流程，自动查找最新的分析文件（按修改时间排序）
        # 这样可以处理实际分析的函数数量少于 top_n 的情况
        # output_dir 已在上面定义
        elif args.stat_method == 'event_count':
            # 先尝试查找所有 event_count 文件，按修改时间排序
            all_event_count_files = sorted(
                output_dir.glob('event_count_top*_analysis.xlsx'),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            if all_event_count_files:
                excel_file = all_event_count_files[0]
                logger.info(f'使用最新的 event_count 分析文件: {excel_file}')
            else:
                # 回退到按 top_n 命名的文件
                excel_file = output_dir / config.EVENT_COUNT_ANALYSIS_PATTERN.format(n=args.top_n)
        else:  # call_count
            # 先尝试查找所有 call_count 文件，按修改时间排序
            all_call_count_files = sorted(
                output_dir.glob('top*_missing_symbols_analysis.xlsx'),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            if all_call_count_files:
                excel_file = all_call_count_files[0]
                logger.info(f'使用最新的 call_count 分析文件: {excel_file}')
            else:
                # 回退到按 top_n 命名的文件
                excel_file = output_dir / config.CALL_COUNT_ANALYSIS_PATTERN.format(n=args.top_n)

        if not excel_file or not excel_file.exists():
            logger.warning('⚠️  Excel 文件不存在: %s', excel_file)
            logger.info('   请先运行 Step 3 生成分析结果')
            logger.info('   跳过 Step 4')
        else:
            # 2. 确定 HTML 输入文件
            html_input = None
            if args.html_input:
                html_input_path = Path(args.html_input)
                # 如果是目录，在目录中查找 HTML 文件
                if html_input_path.is_dir():
                    html_files = list(html_input_path.glob(args.html_pattern))
                    if html_files:
                        html_input = html_files[0]
                        logger.info(f'在目录 {html_input_path} 中找到 HTML 文件: {html_input}')
                    else:
                        logger.info(f'⚠️  在目录 {html_input_path} 中未找到匹配 {args.html_pattern} 的文件')
                # 如果是文件，直接使用
                elif html_input_path.is_file():
                    html_input = html_input_path
                else:
                    logger.warning('⚠️  HTML 路径不存在: %s', html_input_path)
            else:
                # 自动查找步骤目录下的 HTML 文件
                for step_dir in config.STEP_DIRS:
                    step_path = Path(step_dir)
                    if step_path.exists():
                        html_files = list(step_path.glob(args.html_pattern))
                        if html_files:
                            html_input = html_files[0]
                            logger.info(f'自动找到 HTML 文件: {html_input}')
                            break

            if not html_input or not html_input.exists():
                logger.info(f'⚠️  HTML 文件不存在: {html_input if html_input else "(未指定)"}')
                logger.info('   请使用 --html-input 参数指定 HTML 文件路径或目录')
                logger.info('   跳过 Step 4')
            else:
                # 3. 加载函数映射
                logger.info(f'\n加载函数映射: {excel_file}')
                function_mapping = load_function_mapping(excel_file)

                if not function_mapping:
                    logger.warning('⚠️  没有找到函数名映射')
                    logger.info('   跳过 Step 4')
                else:
                    # 4. 读取 HTML 文件
                    logger.info(f'\n读取 HTML 文件: {html_input}')
                    with open(html_input, encoding='utf-8') as f:
                        html_content = f.read()

                    # 5. 替换符号
                    logger.info('\n正在替换缺失符号...')
                    html_content, replacement_info = replace_symbols_in_html(html_content, function_mapping)

                    # 6. 添加免责声明
                    logger.info('\n添加免责声明...')
                    # 根据实际生成的 Excel 文件来确定对应的报告文件
                    # Excel 文件名格式：event_count_top33_analysis.xlsx -> event_count_top33_report.html
                    excel_file_name = excel_file.name
                    if 'event_count_top' in excel_file_name:
                        # 提取数字部分：event_count_top33_analysis.xlsx -> event_count_top33_report.html
                        match = re.search(r'event_count_top(\d+)_analysis', excel_file_name)
                        if match:
                            actual_count = match.group(1)
                            reference_report = f'event_count_top{actual_count}_report.html'
                        else:
                            # 回退到使用 top_n
                            reference_report = f'event_count_top{args.top_n}_report.html'
                    elif 'top' in excel_file_name and 'missing_symbols' in excel_file_name:
                        # 提取数字部分：top100_missing_symbols_analysis.xlsx -> top100_missing_symbols_report.html
                        match = re.search(r'top(\d+)_missing_symbols_analysis', excel_file_name)
                        if match:
                            actual_count = match.group(1)
                            reference_report = f'top{actual_count}_missing_symbols_report.html'
                        else:
                            reference_report = f'top{args.top_n}_missing_symbols_report.html'
                    # 默认使用 top_n
                    elif args.stat_method == 'event_count':
                        reference_report = f'event_count_top{args.top_n}_report.html'
                    else:
                        reference_report = f'top{args.top_n}_missing_symbols_report.html'

                    # 计算相对路径：从 HTML 文件所在目录到输出目录
                    html_input_path = Path(html_input).resolve()
                    output_dir_path = config.get_output_dir(args.output_dir).resolve()
                    # 计算相对路径
                    try:
                        relative_path = str(output_dir_path.relative_to(html_input_path.parent))
                        # 确保路径使用正斜杠（Web 标准）
                        relative_path = relative_path.replace('\\', '/')
                    except ValueError:
                        # 如果无法计算相对路径（不在同一文件系统树中），使用启发式方法
                        str(html_input_path)
                        # 计算需要向上几级目录
                        html_parts = html_input_path.parts
                        base_parts = Path('.').resolve().parts
                        # 找到共同前缀的长度
                        common_len = 0
                        for i in range(min(len(html_parts), len(base_parts))):
                            if html_parts[i] == base_parts[i]:
                                common_len += 1
                            else:
                                break
                        # 计算向上级数：HTML 文件所在目录到项目根目录的级数
                        up_levels = len(html_parts) - common_len - 1  # -1 因为最后一个是文件名
                        relative_path = '../' * up_levels + str(output_dir.name)

                    html_content = add_disclaimer(
                        html_content,
                        reference_report_file=reference_report,
                        relative_path=relative_path,
                    )

                    # 7. 生成输出文件名（不覆盖原文件）
                    html_input_stem = html_input.stem
                    html_output = html_input.parent / f'{html_input_stem}_with_inferred_symbols.html'

                    # 8. 保存新文件
                    logger.info(f'\n保存新文件: {html_output}')
                    logger.info(f'原文件保持不变: {html_input}')
                    with open(html_output, 'w', encoding='utf-8') as f:
                        f.write(html_content)

                    logger.info('\n✅ Step 4 完成！')
                    logger.info(f'📄 原文件: {html_input}（未修改）')
                    logger.info(f'📄 新文件: {html_output}')
                    logger.info(f'   替换了 {len(replacement_info)} 个缺失符号')

    # ========================================================================
    # 完成
    # ========================================================================
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

    # Step 4 的输出（如果执行了）
    if not args.skip_step4 and not args.only_step1 and not args.only_step3:
        html_input = None
        if args.html_input:
            html_input_path = Path(args.html_input)
            # 如果是目录，在目录中查找 HTML 文件
            if html_input_path.is_dir():
                html_files = list(html_input_path.glob(args.html_pattern))
                if html_files:
                    html_input = html_files[0]
            # 如果是文件，直接使用
            elif html_input_path.is_file():
                html_input = html_input_path
        else:
            for step_dir in config.STEP_DIRS:
                step_path = Path(step_dir)
                if step_path.exists():
                    html_files = list(step_path.glob(args.html_pattern))
                    if html_files:
                        html_input = html_files[0]
                        break
        if html_input and html_input.exists():
            html_output = html_input.parent / f'{html_input.stem}_with_inferred_symbols.html'
            logger.info(f'  - {html_output} (符号替换后的 HTML 报告)')


if __name__ == '__main__':
    main()
