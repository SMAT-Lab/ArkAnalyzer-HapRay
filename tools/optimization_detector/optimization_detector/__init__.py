"""
优化检测器包
用于检测二进制文件的优化级别和LTO配置
"""

__version__ = '1.0.0'

from .file_info import FileCollector
from .invoke_symbols import InvokeSymbols
from .optimization_detector import OptimizationDetector

__all__ = ['FileCollector', 'OptimizationDetector', 'InvokeSymbols', '__version__']
