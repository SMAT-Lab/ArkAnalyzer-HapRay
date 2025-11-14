"""
优化检测器工具包
用于检测二进制文件的优化级别和LTO配置
"""

from .file_info import FileCollector, FileInfo
from .invoke_symbols import InvokeSymbols
from .optimization_detector import OptimizationDetector
from .resource_utils import get_model_path, get_models_dir, get_resource_path

__all__ = [
    'OptimizationDetector',
    'FileInfo',
    'FileCollector',
    'InvokeSymbols',
    'get_resource_path',
    'get_models_dir',
    'get_model_path',
]
__version__ = '1.0.0'
