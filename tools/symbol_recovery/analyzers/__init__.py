#!/usr/bin/env python3
"""
分析器模块
包含各种分析功能的实现
"""

from .event_analyzer import EventCountAnalyzer
from .excel_analyzer import ExcelOffsetAnalyzer
from .perf_analyzer import PerfDataToSqliteConverter
from .r2_analyzer import R2FunctionAnalyzer

# MissingSymbolFunctionAnalyzer 在 utils.perf_converter 中
try:
    from utils.perf_converter import MissingSymbolFunctionAnalyzer
except ImportError:
    MissingSymbolFunctionAnalyzer = None

__all__ = [
    'PerfDataToSqliteConverter',
    'EventCountAnalyzer',
    'ExcelOffsetAnalyzer',
    'R2FunctionAnalyzer',
]

if MissingSymbolFunctionAnalyzer is not None:
    __all__.append('MissingSymbolFunctionAnalyzer')
