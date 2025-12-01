#!/usr/bin/env python3

"""
使用 trace_streamer 工具将 perf.data 转换为 SQLite 格式的 perf.db
"""

import platform
import sqlite3
import subprocess
from pathlib import Path

from core.utils.config import (
    DEFAULT_PERF_DB,
    config,
)
from core.utils.logger import get_logger

logger = get_logger(__name__)


class PerfDataToSqliteConverter:
    """使用 trace_streamer 工具将 perf.data 转换为 SQLite 格式的 perf.db"""

    def __init__(self, perf_data_file, output_dir=None):
        self.perf_data_file = Path(perf_data_file)
        self.output_dir = config.get_output_dir(output_dir)
        config.ensure_output_dir(self.output_dir)

        if not self.perf_data_file.exists():
            raise FileNotFoundError(f'perf.data 文件不存在: {perf_data_file}')

        # 检测操作系统和 trace_streamer 工具
        self.trace_streamer_path = self.find_trace_streamer()

    def find_trace_streamer(self):
        """查找 trace_streamer 工具"""
        system = platform.system().lower()

        # 可能的工具名称
        possible_names = []
        if system == 'windows':
            possible_names = ['trace_streamer_windows', 'trace_streamer_windows.exe']
        elif system == 'darwin':  # macOS
            possible_names = ['trace_streamer_mac', 'trace_streamer']
        else:  # Linux
            possible_names = ['trace_streamer_linux', 'trace_streamer']

        # 检查常见位置
        search_paths = [
            Path.cwd(),
            Path.cwd() / '..' / 'trace_streamer_binary',
            Path.cwd() / '..' / '..' / 'dist' / 'tools' / 'trace_streamer_binary',
            Path.cwd() / 'tools' / 'trace_streamer_binary',
        ]

        for search_path in search_paths:
            for name in possible_names:
                tool_path = search_path / name
                if tool_path.exists() and tool_path.is_file():
                    logger.info(f'找到 trace_streamer 工具: {tool_path}')
                    return tool_path

        # 尝试在 PATH 中查找
        for name in possible_names:
            try:
                result = subprocess.run(['which', name], check=False, capture_output=True, timeout=5)
                if result.returncode == 0:
                    tool_path = result.stdout.decode().strip()
                    logger.info(f'找到 trace_streamer 工具: {tool_path}')
                    return Path(tool_path)
            except Exception:
                pass

        logger.info(f'当前目录: {Path.cwd()}')
        logger.error('❌ 错误: 未找到 trace_streamer 工具')
        logger.info('\n请确保 trace_streamer 工具在以下位置之一:')
        for idx, search_path in enumerate(search_paths, 1):
            resolved_path = search_path.resolve()
            exists = resolved_path.exists()
            status = '✓' if exists else '✗'
            logger.info(f'  {idx}. {status} {resolved_path}')

        logger.info('  4. 系统 PATH 中')

        return None

    def convert_to_sqlite_db(self):
        """使用 trace_streamer 转换为 SQLite perf.db"""
        logger.info('=' * 80)
        logger.info('开始转换 perf.data 到 SQLite perf.db')
        logger.info('=' * 80)

        if not self.trace_streamer_path:
            return None

        # 输出文件路径
        perf_db_path = self.output_dir / DEFAULT_PERF_DB

        logger.info(f'\n输入文件: {self.perf_data_file}')
        logger.info(f'输出文件: {perf_db_path}')
        logger.info(f'使用工具: {self.trace_streamer_path}')

        # 构建命令
        # trace_streamer 通常用法: trace_streamer <input> -e <output>
        cmd = [
            str(self.trace_streamer_path),
            str(self.perf_data_file),
            '-e',
            str(perf_db_path),
        ]

        logger.info(f'\n执行命令: {" ".join(cmd)}')
        logger.info('这可能需要几分钟时间，请耐心等待...')

        try:
            # 执行转换
            result = subprocess.run(
                cmd,
                check=False,
                capture_output=True,
                text=True,
                timeout=3600,  # 1小时超时
            )

            if result.returncode == 0:
                if perf_db_path.exists():
                    logger.info('\n✅ 转换成功！')
                    logger.info(f'   SQLite perf.db 已保存到: {perf_db_path}')
                    logger.info(f'   文件大小: {perf_db_path.stat().st_size / (1024 * 1024):.2f} MB')
                    return perf_db_path
                logger.error('❌ 转换完成但输出文件不存在: %s', perf_db_path)
                return None
            logger.error('\n❌ 转换失败')
            logger.info(f'   返回码: {result.returncode}')
            logger.info('   返回码说明: -9 表示进程被强制终止（可能是内存不足或工具崩溃）')
            if result.stdout:
                logger.info('\n   标准输出:')
                logger.info(f'   {result.stdout[:1000]}')
            if result.stderr:
                logger.info('\n   错误输出:')
                logger.info(f'   {result.stderr[:1000]}')

            # 检查是否是库依赖问题
            if result.stderr and 'Library not loaded' in result.stderr:
                logger.info('\n   提示: 可能是库依赖问题，请检查 trace_streamer 工具的依赖库')

            return None

        except subprocess.TimeoutExpired:
            logger.error('\n❌ 转换超时（超过1小时）')
            return None
        except FileNotFoundError:
            logger.error('❌ 错误: 无法执行 %s', self.trace_streamer_path)
            logger.info('   请检查文件权限或工具是否完整')
            return None
        except Exception:
            logger.exception('❌ 转换过程中出错')
            return None

    def verify_sqlite_db(self, db_path):
        """验证 SQLite 数据库"""
        logger.info('\n正在验证 SQLite 数据库...')

        try:
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()

            # 获取所有表名
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = cursor.fetchall()

            logger.info(f'数据库包含 {len(tables)} 个表:')
            for table in tables:
                table_name = table[0]
                cursor.execute(f'SELECT COUNT(*) FROM {table_name};')
                count = cursor.fetchone()[0]
                logger.info(f'  - {table_name}: {count} 行')

            conn.close()
            return True

        except Exception as e:
            logger.error('❌ 验证失败: %s', e)
            return False

    def convert_all(self):
        """完整转换流程"""
        perf_db_path = self.convert_to_sqlite_db()

        if perf_db_path:
            self.verify_sqlite_db(perf_db_path)
            logger.info('\n' + '=' * 80)
            logger.info('转换完成！')
            logger.info('=' * 80)
            logger.info('\n下一步: 使用 main.py 进行完整分析')
            return perf_db_path
        logger.info('\n转换失败，请检查错误信息')
        return None
