# Common 模块导出

# Frame Analyzer 模块化组件（从frame子模块导入）
# 工具模块
from .common_utils import CommonUtils
from .coordinate_adapter import CoordinateAdapter
from .excel_utils import ExcelReportSaver
from .exe_utils import ExeUtils
from .folder_utils import delete_folder, read_json_arrays_from_dir, scan_folders
from .frame import (
    # 专门分析器
    EmptyFrameAnalyzer,
    # 兼容性包装器
    FrameAnalyzer,
    # 核心组件
    FrameAnalyzerCore,
    FrameCacheManager,
    FrameLoadCalculator,
    StutteredFrameAnalyzer,
    extract_frame_statistics,
    get_database_metadata,
    get_frame_type,
    # 数据解析函数
    parse_frame_slice_db,
    validate_database_compatibility,
)

# pylint: disable=duplicate-code
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
# pylint: enable=duplicate-code
