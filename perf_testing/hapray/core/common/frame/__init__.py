# Frame Analyzer 模块化组件导出

# 兼容性包装器（保持向后兼容）
from .frame_compat_analyzer import FrameAnalyzer
from .frame_core_analyzer import FrameAnalyzerCore
from .frame_core_cache_manager import FrameCacheManager

# pylint: disable=duplicate-code
__all__ = [
    # 核心组件
    'FrameAnalyzerCore',
    'FrameCacheManager',
    # 兼容性包装器
    'FrameAnalyzer',
]
# pylint: enable=duplicate-code
