"""
日志管理器 - 提供统一的日志功能
"""

import contextlib
import io
import logging
import sys
from pathlib import Path
from typing import Optional


def get_logger(name: str, log_file: Optional[str] = None) -> logging.Logger:
    """
    获取日志器

    Args:
        name: 日志器名称
        log_file: 日志文件路径（可选）
    """
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)

    # 控制台处理器 - 使用 UTF-8 编码包装器处理 Windows 下的编码问题
    # 在 PyInstaller 打包的 GUI 应用中，sys.stdout 可能为 None
    if sys.stdout is not None:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)

        # 对于 Windows，需要使用 UTF-8 编码包装器
        if sys.platform == 'win32':
            # 重定向 stdout 到 UTF-8 编码的包装器
            if hasattr(sys.stdout, 'reconfigure'):
                with contextlib.suppress(Exception):
                    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
            # 创建 UTF-8 编码的流包装器（仅当 buffer 存在时）
            if hasattr(sys.stdout, 'buffer') and sys.stdout.buffer is not None:
                try:
                    utf8_stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
                    console_handler.stream = utf8_stdout
                except Exception:
                    pass

        console_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S',
        )
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)

    # 文件处理器（如果指定）- 使用 UTF-8 编码
    # 如果没有指定日志文件，但 stdout 不可用（如 GUI 打包后），创建默认日志文件
    if log_file is None and sys.stdout is None:
        # 在用户主目录创建日志文件
        log_dir = Path.home() / '.hapray-gui' / 'logs'
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = str(log_dir / 'hapray-gui.log')

    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding='utf-8', errors='replace')
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S',
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

    return logger
