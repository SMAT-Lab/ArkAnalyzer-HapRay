"""
优化检测器包
用于检测二进制文件的优化级别和LTO配置
"""

__version__ = '1.0.0'

from .api import check_prerequisites, detect_optimization
from .errors import (
    OptDetectorAnalysisError,
    OptDetectorError,
    OptDetectorInputError,
    OptDetectorNoFilesError,
    OptDetectorTimeoutError,
)
from .file_info import FILE_STATUS_MAPPING, FileCollector, FileInfo
from .invoke_symbols import InvokeSymbols
from .optimization_detector import OptimizationDetector

__all__ = [
    'FileCollector',
    'OptimizationDetector',
    'InvokeSymbols',
    'FILE_STATUS_MAPPING',
    'FileInfo',
    '__version__',
    'detect_optimization',
    'check_prerequisites',
    'OptDetectorError',
    'OptDetectorInputError',
    'OptDetectorNoFilesError',
    'OptDetectorTimeoutError',
    'OptDetectorAnalysisError',
]
