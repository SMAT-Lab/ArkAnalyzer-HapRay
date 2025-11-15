#!/usr/bin/env python3
"""
优化检测器命令行工具
用于检测二进制文件的优化级别和LTO配置
"""

import argparse
import contextlib
import logging
import os
import sys
from pathlib import Path

from optimization_detector import FileCollector, OptimizationDetector, __version__


def setup_logging(verbose: bool = False, log_file: str = None):
    """配置日志"""
    level = logging.DEBUG if verbose else logging.INFO
    handlers = [logging.StreamHandler(sys.stdout)]

    if log_file:
        handlers.append(logging.FileHandler(log_file, encoding='utf-8'))

    logging.basicConfig(level=level, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', handlers=handlers)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='Analyze binary files for optimization flags',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Analyze a single SO file
  opt-detector -i libexample.so -o report.xlsx

  # Analyze all binary files in a directory
  opt-detector -i /path/to/binaries -o report.xlsx --jobs 4

  # Only detect optimization level, skip LTO detection
  opt-detector -i libexample.so -o report.xlsx --no-lto

  # Only detect LTO, skip optimization level detection
  opt-detector -i libexample.so -o report.xlsx --no-opt
        """,
    )

    parser.add_argument(
        '-v',
        '--version',
        action='version',
        version=f'%(prog)s {__version__}',
        help="Show program's version number and exit",
    )

    parser.add_argument('--input', '-i', required=True, help='Directory containing binary files to analyze')

    parser.add_argument(
        '--output',
        '-o',
        default='binary_analysis_report.xlsx',
        help='Output Excel file path (default: binary_analysis_report.xlsx)',
    )

    parser.add_argument('--jobs', '-j', type=int, default=1, help='Number of parallel jobs (default: 1)')

    parser.add_argument(
        '-w', '--workers', type=int, default=None, help='Number of parallel workers (same as --jobs, for compatibility)'
    )

    parser.add_argument(
        '--timeout', type=int, default=None, help='Timeout in seconds for analyzing a single file (default: no timeout)'
    )

    parser.add_argument(
        '--no-lto',
        dest='lto',
        action='store_false',
        default=True,
        help='Disable LTO (Link-Time Optimization) detection for .so files (default: enabled)',
    )

    parser.add_argument(
        '--no-opt',
        dest='opt',
        action='store_false',
        default=True,
        help='Disable optimization level (Ox) detection, only run LTO detection (default: enabled)',
    )

    parser.add_argument('--verbose', action='store_true', help='Show verbose logs')

    parser.add_argument('--log-file', help='Path to log file')

    parser.add_argument('--lto-demo-path', help='Path to lto_demo directory (if required for LTO detection)')

    parser.add_argument('--report-dir', '-r', help='Directory containing reports to update')

    args = parser.parse_args()

    # 如果指定了 --workers，使用它覆盖 --jobs
    if args.workers is not None:
        args.jobs = args.workers

    # 配置日志
    setup_logging(args.verbose, args.log_file)

    # 设置LTO_DEMO_PATH环境变量（如果提供）
    if args.lto_demo_path:
        os.environ['LTO_DEMO_PATH'] = args.lto_demo_path

    # 检查输入路径
    input_path = Path(args.input)
    if not input_path.exists():
        logging.error('输入路径不存在: %s', args.input)
        return 1

    # 创建文件收集器
    collector = FileCollector()
    try:
        # 收集二进制文件
        logging.info('收集二进制文件: %s', args.input)
        file_infos = collector.collect_binary_files(str(input_path))

        if not file_infos:
            logging.warning('未找到任何二进制文件')
            return 0

        logging.info('找到 %d 个二进制文件', len(file_infos))

        # 创建检测器
        detector = OptimizationDetector(
            workers=args.jobs, timeout=args.timeout, enable_lto=args.lto, enable_opt=args.opt
        )

        # 执行检测
        logging.info('开始检测...')
        results = detector.detect_optimization(file_infos)
        # 保存结果
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # 确保 pandas 已导入
        import pandas as pd  # noqa: PLC0415

        with pd.ExcelWriter(output_path, engine='xlsxwriter') as writer:
            for sheet_name, df in results:
                # 截断过长的 sheet 名称（Excel 限制为 31 个字符）
                truncated_sheet_name = sheet_name[:31]
                df.to_excel(writer, sheet_name=truncated_sheet_name, index=False)

                # 自动调整列宽
                worksheet = writer.sheets[truncated_sheet_name]
                for i, col in enumerate(df.columns):
                    max_length = max(df[col].astype(str).map(len).max(), len(col))
                    worksheet.set_column(i, i, min(max_length + 2, 50))

        logging.info('报告已保存到: %s', output_path)

        # 显示摘要
        if results:
            df = results[0][1]
            total = len(df)
            analyzed = len(df[df['Status'] == 'Successfully Analyzed'])
            failed = len(df[df['Status'] == 'Analysis Failed'])

            print('\n检测完成！')
            print(f'总计: {total} 个文件')
            print(f'成功: {analyzed} 个文件')
            print(f'失败: {failed} 个文件')

            if args.opt and analyzed > 0:
                opt_categories = df['Optimization Category'].value_counts()
                print('\n优化级别分布:')
                for category, count in opt_categories.items():
                    print(f'  {category}: {count}')

        return 0

    except KeyboardInterrupt:
        logging.info('用户中断')
        return 130
    except Exception as e:
        logging.exception('检测失败: %s', e)
        return 1
    finally:
        # 清理临时文件
        with contextlib.suppress(Exception):
            collector.cleanup()


if __name__ == '__main__':
    sys.exit(main())
