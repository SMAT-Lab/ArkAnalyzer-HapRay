from enum import IntEnum


class Mode(IntEnum):
    """运行模式枚举"""
    COMMUNITY = 0      # 社区模式
    COMPATIBILITY = 1  # 兼容模式
    SIMPLE = 2         # 简单模式
