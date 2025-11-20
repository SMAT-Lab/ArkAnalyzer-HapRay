#!/usr/bin/env python3

"""
统一的 logging 配置，支持同时输出到控制台与日志文件。
"""

import logging
import os
import sys
from pathlib import Path
from typing import Optional

_LOGGER_INITIALIZED = False
_LOG_FILE_PATH: Optional[Path] = None


def setup_logging(output_dir: str, level: Optional[str] = None) -> Path:
    """
    初始化 logging，配置控制台与文件双通道输出。

    Args:
        output_dir: 自定义日志文件路径
        level: 字符串形式的日志级别（可选，默认 INFO）

    Returns:
        Path: 实际使用的日志文件路径
    """
    global _LOGGER_INITIALIZED, _LOG_FILE_PATH

    if _LOGGER_INITIALIZED and _LOG_FILE_PATH is not None:
        return _LOG_FILE_PATH

    log_level = level or os.getenv('SYMBOL_RECOVERY_LOG_LEVEL', 'INFO')
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)

    log_dir = output_dir / 'logs'
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / 'symbol_recovery.log'

    logger = logging.getLogger('symbol_recovery')
    logger.setLevel(numeric_level)
    logger.propagate = False

    formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(name)s - %(message)s', '%Y-%m-%d %H:%M:%S')

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    file_handler = logging.FileHandler(log_path, encoding='utf-8')
    file_handler.setLevel(numeric_level)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    _LOGGER_INITIALIZED = True
    _LOG_FILE_PATH = log_path
    return log_path


def get_logger(name: Optional[str] = None, level: Optional[str] = None) -> logging.Logger:
    """
    获取指定名称的日志记录器，保证 logging 已初始化。

    Args:
        name: 日志记录器名称（默认返回根记录器）
        level: 覆盖日志级别（可选，默认 INFO）

    Returns:
        logging.Logger: 对应的日志记录器
    """

    logger_name = 'symbol_recovery'
    if name and name != 'symbol_recovery':
        logger_name = f'{logger_name}.{name}'

    logger = logging.getLogger(logger_name)
    desired_level = level or os.getenv('SYMBOL_RECOVERY_LOGGER_LEVEL')
    if desired_level:
        logger.setLevel(getattr(logging, desired_level.upper(), logging.INFO))
    elif logger.level == logging.NOTSET:
        logger.setLevel(logging.INFO)
    return logger
