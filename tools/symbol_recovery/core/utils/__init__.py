#!/usr/bin/env python3
"""
工具模块
包含各种工具函数和辅助功能

注意：不在包初始化时导入 ``.common``（含 capstone），以便 ``symbol_replacer`` 等模块
可在仅含 pandas/openpyxl 的环境中（如 perf-testing 父进程写 perf.json）被导入。
``create_disassembler`` 等仍可通过 ``from core.utils import ...`` 懒加载。
"""

from __future__ import annotations

import importlib
from typing import Any

from .config import (
    CALL_COUNT_ANALYSIS_PATTERN,
    CALL_COUNT_REPORT_PATTERN,
    DEFAULT_BATCH_SIZE,
    DEFAULT_LLM_MODEL,
    DEFAULT_OUTPUT_DIR,
    DEFAULT_PERF_DATA,
    DEFAULT_PERF_DB,
    DEFAULT_TOP_N,
    EVENT_COUNT_ANALYSIS_PATTERN,
    EVENT_COUNT_REPORT_PATTERN,
    EXCEL_ANALYSIS_PATTERN,
    EXCEL_REPORT_PATTERN,
    HTML_REPORT_PATTERN,
    STEP_DIRS,
    TEMP_FILE_PREFIX,
    TIME_STATS_PATTERN,
    config,
)
from .logger import get_logger
from .time_tracker import TimeTracker

_LAZY_COMMON_EXPORTS = frozenset(
    {
        'create_disassembler',
        'parse_offset',
        'find_function_start',
        'render_html_report',
    }
)
_LAZY_STRING_EXTRACTOR_EXPORTS = frozenset({'StringExtractor'})
_LAZY_SYMBOL_REPLACER_EXPORTS = frozenset({'load_function_mapping', 'replace_symbols_in_html', 'add_disclaimer'})


def __getattr__(name: str) -> Any:
    if name == 'common':
        return importlib.import_module(f'{__name__}.common')
    if name in _LAZY_COMMON_EXPORTS:
        common = importlib.import_module(f'{__name__}.common')
        return getattr(common, name)
    if name in _LAZY_STRING_EXTRACTOR_EXPORTS:
        string_extractor = importlib.import_module(f'{__name__}.string_extractor')
        return getattr(string_extractor, name)
    if name in _LAZY_SYMBOL_REPLACER_EXPORTS:
        symbol_replacer = importlib.import_module(f'{__name__}.symbol_replacer')
        return getattr(symbol_replacer, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    'create_disassembler',
    'parse_offset',
    'find_function_start',
    'render_html_report',
    'config',
    'DEFAULT_OUTPUT_DIR',
    'DEFAULT_PERF_DATA',
    'DEFAULT_PERF_DB',
    'DEFAULT_TOP_N',
    'DEFAULT_BATCH_SIZE',
    'DEFAULT_LLM_MODEL',
    'HTML_REPORT_PATTERN',
    'STEP_DIRS',
    'EXCEL_ANALYSIS_PATTERN',
    'EXCEL_REPORT_PATTERN',
    'EVENT_COUNT_ANALYSIS_PATTERN',
    'EVENT_COUNT_REPORT_PATTERN',
    'CALL_COUNT_ANALYSIS_PATTERN',
    'CALL_COUNT_REPORT_PATTERN',
    'TIME_STATS_PATTERN',
    'TEMP_FILE_PREFIX',
    'TimeTracker',
    'StringExtractor',
    'load_function_mapping',
    'replace_symbols_in_html',
    'add_disclaimer',
    'get_logger',
]
