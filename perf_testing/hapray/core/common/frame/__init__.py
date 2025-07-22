# Frame Analyzer 模块化组件导出

# 核心组件
from .frame_analyzer_core import FrameAnalyzerCore
from .frame_cache_manager import FrameCacheManager
from .frame_load_calculator import FrameLoadCalculator

# 专门分析器
from .empty_frame_analyzer import EmptyFrameAnalyzer
from .stuttered_frame_analyzer import StutteredFrameAnalyzer

# 数据解析函数
from .frame_data_parser import (
    parse_frame_slice_db,
    get_frame_type,
    validate_database_compatibility,
    get_database_metadata,
    extract_frame_statistics
)

# 兼容性包装器（保持向后兼容）
from .frame_analyzer import FrameAnalyzer

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