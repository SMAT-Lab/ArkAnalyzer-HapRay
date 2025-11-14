"""
帧分析时间工具类

提供帧分析中常用的时间转换和计算功能，避免代码重复。
"""

import logging

from .frame_constants import (
    FPS_WINDOW_SIZE_MS,
    FRAME_DURATION_MS,
    MILLISECONDS_TO_NANOSECONDS,
    SECONDS_TO_NANOSECONDS,
    TIMESTAMP_MAX_NANOSECONDS,
)


class FrameTimeUtils:
    """帧分析时间工具类

    提供帧分析中常用的时间转换和计算功能，包括：
    1. 相对时间戳转换
    2. 时间单位转换
    3. 时间验证和格式化
    """

    # 常用时间常量 - 从frame_constants导入以避免重复
    NS_TO_MS = MILLISECONDS_TO_NANOSECONDS
    NS_TO_S = SECONDS_TO_NANOSECONDS
    MS_TO_NS = MILLISECONDS_TO_NANOSECONDS
    S_TO_NS = SECONDS_TO_NANOSECONDS
    FRAME_DURATION_60FPS_MS = FRAME_DURATION_MS
    WINDOW_SIZE_MS = FPS_WINDOW_SIZE_MS

    @staticmethod
    def convert_to_relative_nanoseconds(timestamp_ns: int, first_frame_time_ns: int) -> int:
        """将纳秒时间戳转换为相对于第一帧的纳秒数

        Args:
            timestamp_ns: 纳秒时间戳
            first_frame_time_ns: 第一帧的纳秒时间戳

        Returns:
            int: 相对于第一帧的纳秒数
        """
        return timestamp_ns - first_frame_time_ns

    @staticmethod
    def convert_nanoseconds_to_milliseconds(nanoseconds: int) -> float:
        """将纳秒转换为毫秒

        Args:
            nanoseconds: 纳秒数

        Returns:
            float: 毫秒数
        """
        return nanoseconds / MILLISECONDS_TO_NANOSECONDS

    @staticmethod
    def convert_nanoseconds_to_seconds(nanoseconds: int) -> float:
        """将纳秒转换为秒

        Args:
            nanoseconds: 纳秒数

        Returns:
            float: 秒数
        """
        return nanoseconds / SECONDS_TO_NANOSECONDS

    @staticmethod
    def convert_milliseconds_to_nanoseconds(milliseconds: float) -> int:
        """将毫秒转换为纳秒

        Args:
            milliseconds: 毫秒数

        Returns:
            int: 纳秒数
        """
        return int(milliseconds * MILLISECONDS_TO_NANOSECONDS)

    @staticmethod
    def convert_seconds_to_nanoseconds(seconds: float) -> int:
        """将秒转换为纳秒

        Args:
            seconds: 秒数

        Returns:
            int: 纳秒数
        """
        return int(seconds * SECONDS_TO_NANOSECONDS)

    @staticmethod
    def validate_timestamp(timestamp_ns: int, name: str = 'timestamp') -> bool:
        """验证时间戳的有效性

        Args:
            timestamp_ns: 纳秒时间戳
            name: 时间戳名称，用于日志

        Returns:
            bool: 是否有效
        """

        if timestamp_ns < 0:
            logging.warning('%s 时间戳为负数: %d', name, timestamp_ns)
            return False

        if timestamp_ns > TIMESTAMP_MAX_NANOSECONDS:
            logging.warning('%s 时间戳过大: %d', name, timestamp_ns)
            return False

        return True

    @staticmethod
    def format_duration_nanoseconds(nanoseconds: int) -> str:
        """格式化纳秒时长显示

        Args:
            nanoseconds: 纳秒数

        Returns:
            str: 格式化的时长字符串
        """
        if nanoseconds < 1_000:
            return f'{nanoseconds}ns'
        if nanoseconds < 1_000_000:
            return f'{nanoseconds / 1_000:.1f}μs'
        if nanoseconds < 1_000_000_000:
            return f'{nanoseconds / 1_000_000:.1f}ms'
        return f'{nanoseconds / 1_000_000_000:.3f}s'

    @staticmethod
    def format_timestamp_nanoseconds(nanoseconds: int) -> str:
        """格式化纳秒时间戳显示

        Args:
            nanoseconds: 纳秒数

        Returns:
            str: 格式化的时间戳字符串
        """
        seconds = nanoseconds / SECONDS_TO_NANOSECONDS
        minutes = int(seconds // 60)
        seconds = seconds % 60

        if minutes > 0:
            return f'{minutes}m {seconds:.3f}s'
        return f'{seconds:.3f}s'
