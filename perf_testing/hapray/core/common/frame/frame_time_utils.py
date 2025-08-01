#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
帧分析时间工具类

提供帧分析中常用的时间转换和计算功能，避免代码重复。
"""

import logging


# from typing import Optional  # 未使用


class FrameTimeUtils:
    """帧分析时间工具类

    提供帧分析中常用的时间转换和计算功能，包括：
    1. 相对时间戳转换
    2. 时间单位转换
    3. 时间验证和格式化
    """

    # 常用时间常量
    NS_TO_MS = 1_000_000  # 纳秒到毫秒的转换因子
    NS_TO_S = 1_000_000_000  # 纳秒到秒的转换因子
    MS_TO_NS = 1_000_000  # 毫秒到纳秒的转换因子
    S_TO_NS = 1_000_000_000  # 秒到纳秒的转换因子

    # 帧分析相关常量
    FRAME_DURATION_60FPS_MS = 16.67  # 60fps基准帧时长（毫秒）
    WINDOW_SIZE_MS = 1000  # FPS窗口大小（毫秒）

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
        return nanoseconds / 1_000_000

    @staticmethod
    def convert_nanoseconds_to_seconds(nanoseconds: int) -> float:
        """将纳秒转换为秒

        Args:
            nanoseconds: 纳秒数

        Returns:
            float: 秒数
        """
        return nanoseconds / 1_000_000_000

    @staticmethod
    def convert_milliseconds_to_nanoseconds(milliseconds: float) -> int:
        """将毫秒转换为纳秒

        Args:
            milliseconds: 毫秒数

        Returns:
            int: 纳秒数
        """
        return int(milliseconds * 1_000_000)

    @staticmethod
    def convert_seconds_to_nanoseconds(seconds: float) -> int:
        """将秒转换为纳秒

        Args:
            seconds: 秒数

        Returns:
            int: 纳秒数
        """
        return int(seconds * 1_000_000_000)

    @staticmethod
    def validate_timestamp(timestamp_ns: int, name: str = "timestamp") -> bool:
        """验证时间戳的有效性

        Args:
            timestamp_ns: 纳秒时间戳
            name: 时间戳名称，用于日志

        Returns:
            bool: 是否有效
        """
        if timestamp_ns is None:
            logging.warning("%s 时间戳为 None", name)
            return False

        if timestamp_ns < 0:
            logging.warning("%s 时间戳为负数: %d", name, timestamp_ns)
            return False

        if timestamp_ns > 1_000_000_000_000_000:  # 约31年
            logging.warning("%s 时间戳过大: %d", name, timestamp_ns)
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
            return f"{nanoseconds}ns"
        elif nanoseconds < 1_000_000:
            return f"{nanoseconds / 1_000:.1f}μs"
        elif nanoseconds < 1_000_000_000:
            return f"{nanoseconds / 1_000_000:.1f}ms"
        else:
            return f"{nanoseconds / 1_000_000_000:.3f}s"

    @staticmethod
    def format_timestamp_nanoseconds(nanoseconds: int) -> str:
        """格式化纳秒时间戳显示

        Args:
            nanoseconds: 纳秒数

        Returns:
            str: 格式化的时间戳字符串
        """
        seconds = nanoseconds / 1_000_000_000
        minutes = int(seconds // 60)
        seconds = seconds % 60

        if minutes > 0:
            return f"{minutes}m {seconds:.3f}s"
        else:
            return f"{seconds:.3f}s"
