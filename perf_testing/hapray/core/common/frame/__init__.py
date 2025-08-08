# Frame Analyzer 模块化组件导出

# 核心组件
from .frame_core_analyzer import FrameAnalyzerCore
from .frame_core_cache_manager import FrameCacheManager
from .frame_core_load_calculator import FrameLoadCalculator

# 专门分析器
from .frame_analyzer_empty import EmptyFrameAnalyzer
from .frame_analyzer_stuttered import StutteredFrameAnalyzer

# 数据解析函数
from .frame_data_parser import (
    parse_frame_slice_db,
    get_frame_type,
    validate_database_compatibility,
    get_database_metadata,
    extract_frame_statistics
)

# 兼容性包装器（保持向后兼容）
from .frame_compat_analyzer import FrameAnalyzer

# pylint: disable=duplicate-code
__all__ = [
    # 核心组件
    'FrameAnalyzerCore',
    'FrameCacheManager',
    'FrameLoadCalculator',
    # 专门分析器
    'EmptyFrameAnalyzer',
    'StutteredFrameAnalyzer',
    # 数据解析函数
    'parse_frame_slice_db',
    'get_frame_type',
    'validate_database_compatibility',
    'get_database_metadata',
    'extract_frame_statistics',
    # 兼容性包装器
    'FrameAnalyzer',
]
# pylint: enable=duplicate-code
