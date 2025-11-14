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

from optimization_detector import FileCollector, OptimizationDetector


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
        description='检测二进制文件的优化级别和LTO配置',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 检测单个SO文件
  opt-detector -i libexample.so -o report.xlsx

  # 检测目录中的所有二进制文件
  opt-detector -i /path/to/binaries -o report.xlsx --workers 4

  # 只检测优化级别，不检测LTO
  opt-detector -i libexample.so -o report.xlsx --no-lto

  # 只检测LTO，不检测优化级别
  opt-detector -i libexample.so -o report.xlsx --no-opt
        """,
    )

    parser.add_argument(
        '-i',
        '--input',
        required=False,  # 改为非必需，以便 --help 可以快速退出
        help='输入路径：SO文件、AR文件、HAP文件或包含二进制文件的目录',
    )

    parser.add_argument(
        '-o',
        '--output',
        required=False,  # 改为非必需，以便 --help 可以快速退出
        help='输出Excel报告路径',
    )

    parser.add_argument('-w', '--workers', type=int, default=1, help='并行工作线程数（默认: 1）')

    parser.add_argument('-j', '--jobs', type=int, default=None, help='并行工作线程数（与 --workers 相同，用于兼容性）')

    parser.add_argument('--timeout', type=int, default=None, help='单个文件分析超时时间（秒），默认无超时')

    parser.add_argument('--no-lto', action='store_true', help='禁用LTO检测')

    parser.add_argument('--no-opt', action='store_true', help='禁用优化级别检测')

    parser.add_argument('-v', '--verbose', action='store_true', help='显示详细日志')

    parser.add_argument('--log-file', help='日志文件路径')

    parser.add_argument('--lto-demo-path', help='lto_demo目录路径（如果LTO检测需要）')

    parser.add_argument('-r', '--report-dir', help='报告目录路径（用于调用符号分析，需要与 hapray 配合使用）')

    args = parser.parse_args()

    # 如果指定了 --jobs，使用它覆盖 --workers
    if args.jobs is not None:
        args.workers = args.jobs

    # 如果是 --help，直接退出，不加载重型依赖
    # 这样可以让帮助信息显示得非常快
    if not args.input or not args.output:
        if '--help' in sys.argv or '-h' in sys.argv:
            parser.print_help()
            return 0
        parser.error('需要提供 -i/--input 和 -o/--output 参数')

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
            workers=args.workers, timeout=args.timeout, enable_lto=not args.no_lto, enable_opt=not args.no_opt
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

            if not args.no_opt and analyzed > 0:
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
