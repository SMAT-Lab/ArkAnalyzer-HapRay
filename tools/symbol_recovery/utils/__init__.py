#!/usr/bin/env python3
"""
工具模块
包含各种工具函数和辅助功能
"""

from . import config
from .common import (
    create_disassembler,
    find_function_start,
    parse_offset,
    render_html_report,
)
from .string_extractor import StringExtractor
from .symbol_replacer import (
    add_disclaimer,
    load_function_mapping,
    replace_symbols_in_html,
)
from .time_tracker import TimeTracker

# PerfDataToSqliteConverter 现在在 analyzers.perf_analyzer 中
try:
    from analyzers.perf_analyzer import PerfDataToSqliteConverter
except ImportError:
    PerfDataToSqliteConverter = None

__all__ = [
    'setup_windows_console',
    'create_disassembler',
    'parse_offset',
    'find_function_start',
    'render_html_report',
    'config',
    'TimeTracker',
    'StringExtractor',
    'load_function_mapping',
    'replace_symbols_in_html',
    'add_disclaimer',
]

# 如果 PerfDataToSqliteConverter 可用，添加到 __all__
if PerfDataToSqliteConverter is not None:
    __all__.append('PerfDataToSqliteConverter')
