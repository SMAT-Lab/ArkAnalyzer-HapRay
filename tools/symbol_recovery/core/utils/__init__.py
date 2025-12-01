#!/usr/bin/env python3
"""
工具模块
包含各种工具函数和辅助功能
"""

from .common import (
    create_disassembler,
    find_function_start,
    parse_offset,
    render_html_report,
)
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
from .string_extractor import StringExtractor
from .symbol_replacer import (
    add_disclaimer,
    load_function_mapping,
    replace_symbols_in_html,
)
from .time_tracker import TimeTracker

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
