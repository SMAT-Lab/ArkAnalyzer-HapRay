# Common 模块导出

# Frame Analyzer 模块化组件（从frame子模块导入）
from .frame import (
    # 核心组件
    FrameAnalyzerCore,
    FrameCacheManager,
    FrameLoadCalculator,

    # 专门分析器
    EmptyFrameAnalyzer,
    StutteredFrameAnalyzer,

    # 数据解析函数
    parse_frame_slice_db,
    get_frame_type,
    validate_database_compatibility,
    get_database_metadata,
    extract_frame_statistics,

    # 兼容性包装器
    FrameAnalyzer,
)

# 工具模块
from .common_utils import CommonUtils
from .coordinate_adapter import CoordinateAdapter
from .exe_utils import ExeUtils
from .folder_utils import scan_folders, delete_folder, read_json_arrays_from_dir
from .excel_utils import ExcelReportSaver

__all__ = [
    # Frame Analyzer 组件
    'FrameAnalyzerCore',
    'FrameCacheManager',
    'FrameLoadCalculator',
    'EmptyFrameAnalyzer',
    'StutteredFrameAnalyzer',
    'parse_frame_slice_db',
    'get_frame_type',
    'validate_database_compatibility',
    'get_database_metadata',
    'extract_frame_statistics',
    'FrameAnalyzer',
    # 工具模块
    'CommonUtils',
    'CoordinateAdapter',
    'ExeUtils',
    'scan_folders',
    'delete_folder',
    'read_json_arrays_from_dir',
    'ExcelReportSaver',
]
