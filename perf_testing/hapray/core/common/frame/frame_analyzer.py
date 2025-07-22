"""
Copyright (c) 2025 Huawei Device Co., Ltd.
Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

 http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

import codecs
import logging
import os
import sys
from typing import Dict, Any, List, Optional

import pandas as pd

# 设置环境变量
os.environ["PYTHONIOENCODING"] = "utf-8"

# 导入新的模块化组件
from .frame_analyzer_core import FrameAnalyzerCore
from .frame_cache_manager import FrameCacheManager
from .frame_data_parser import parse_frame_slice_db, get_frame_type


class FrameAnalyzer:
    """卡顿帧分析器 - 兼容性包装器

    这是重构后的兼容性包装器，保持原有接口不变，
    内部使用新的模块化组件实现。

    用于分析htrace文件中的卡顿帧数据，包括：
    1. 将htrace文件转换为db文件
    2. 分析卡顿帧数据
    3. 生成分析报告
    
    注意：本类现在委托给新的模块化实现
    """

    # 类变量用于存储缓存 - 委托给FrameCacheManager
    _callchain_cache = FrameCacheManager._callchain_cache
    _files_cache = FrameCacheManager._files_cache
    _pid_cache = FrameCacheManager._pid_cache
    _tid_cache = FrameCacheManager._tid_cache
    _process_cache = FrameCacheManager._process_cache

    # 调试开关配置
    _debug_vsync_enabled = False  # VSync调试开关，True时正常判断，False时永远不触发VSync条件

    # 常量定义
    FRAME_DURATION = 16.67  # 毫秒，60fps基准帧时长
    STUTTER_LEVEL_1_FRAMES = 2  # 1级卡顿阈值：0-2帧
    STUTTER_LEVEL_2_FRAMES = 6  # 2级卡顿阈值：2-6帧
    NS_TO_MS = 1_000_000
    WINDOW_SIZE_MS = 1000  # fps窗口大小：1s

    # 内部核心分析器实例
    _core_analyzer = None

    @classmethod
    def _get_core_analyzer(cls):
        """获取核心分析器实例（单例模式）"""
        if cls._core_analyzer is None:
            cls._core_analyzer = FrameAnalyzerCore(cls._debug_vsync_enabled)
        return cls._core_analyzer

    @staticmethod
    def _update_pid_tid_cache(step_id: str, trace_df: pd.DataFrame) -> None:
        """根据trace_df中的数据更新PID和TID缓存 - 兼容性包装

        Args:
            step_id: 步骤ID，如'step1'或'1'
            trace_df: 包含pid和tid信息的DataFrame
        """
        FrameCacheManager.update_pid_tid_cache(step_id, trace_df)

    @staticmethod
    def _get_callchain_cache(perf_conn, step_id: str = None) -> pd.DataFrame:
        """获取并缓存perf_callchain表的数据 - 兼容性包装

        Args:
            perf_conn: perf数据库连接
            step_id: 步骤ID，用作缓存key

        Returns:
            pd.DataFrame: callchain缓存数据
        """
        return FrameCacheManager.get_callchain_cache(perf_conn, step_id)

    @staticmethod
    def _get_files_cache(perf_conn, step_id: str = None) -> pd.DataFrame:
        """获取并缓存perf_files表的数据 - 兼容性包装

        Args:
            perf_conn: perf数据库连接
            step_id: 步骤ID，用作缓存key

        Returns:
            pd.DataFrame: files缓存数据
        """
        return FrameCacheManager.get_files_cache(perf_conn, step_id)

    @staticmethod
    def _get_pid_cache(trace_conn, step_id: str = None) -> pd.DataFrame:
        """获取并缓存trace_pid表的数据 - 兼容性包装

        Args:
            trace_conn: trace数据库连接
            step_id: 步骤ID，用作缓存key

        Returns:
            pd.DataFrame: pid缓存数据
        """
        return FrameCacheManager.get_pid_cache(trace_conn, step_id)

    @staticmethod
    def _get_tid_cache(trace_conn, step_id: str = None) -> pd.DataFrame:
        """获取并缓存trace_tid表的数据 - 兼容性包装

        Args:
            trace_conn: trace数据库连接
            step_id: 步骤ID，用作缓存key

        Returns:
            pd.DataFrame: tid缓存数据
        """
        return FrameCacheManager.get_tid_cache(trace_conn, step_id)

    @staticmethod
    def _get_process_cache(trace_conn, step_id: str = None) -> pd.DataFrame:
        """获取并缓存trace_process表的数据 - 兼容性包装

        Args:
            trace_conn: trace数据库连接
            step_id: 步骤ID，用作缓存key

        Returns:
            pd.DataFrame: process缓存数据
        """
        return FrameCacheManager.get_process_cache(trace_conn, step_id)

    @staticmethod
    def get_process_cache_by_key(cache_key: str) -> pd.DataFrame:
        """根据缓存key获取process缓存数据 - 兼容性包装

        Args:
            cache_key: 缓存key

        Returns:
            pd.DataFrame: process缓存数据
        """
        return FrameCacheManager.get_process_cache_by_key(cache_key)

    @staticmethod
    def get_process_cache(trace_conn, step_id: str = None) -> pd.DataFrame:
        """获取process缓存数据 - 兼容性包装

        Args:
            trace_conn: trace数据库连接
            step_id: 步骤ID，用作缓存key

        Returns:
            pd.DataFrame: process缓存数据
        """
        return FrameCacheManager.get_process_cache(trace_conn, step_id)

    @staticmethod
    def _analyze_perf_callchain(perf_conn, callchain_id: int, callchain_cache: pd.DataFrame = None,
                                files_cache: pd.DataFrame = None, step_id: str = None) -> list:
        """分析perf callchain - 兼容性包装

        Args:
            perf_conn: perf数据库连接
            callchain_id: callchain ID
            callchain_cache: callchain缓存数据
            files_cache: files缓存数据
            step_id: 步骤ID

        Returns:
            list: callchain分析结果
        """
        core = FrameAnalyzer._get_core_analyzer()
        return core.load_calculator.analyze_perf_callchain(perf_conn, callchain_id, callchain_cache, files_cache, step_id)

    @staticmethod
    def analyze_single_frame(frame, perf_df, perf_conn, step_id):
        """分析单个帧 - 兼容性包装

        Args:
            frame: 帧数据
            perf_df: perf数据
            perf_conn: perf数据库连接
            step_id: 步骤ID

        Returns:
            分析结果
        """
        core = FrameAnalyzer._get_core_analyzer()
        return core.load_calculator.analyze_single_frame(frame, perf_df, perf_conn, step_id)

    @staticmethod
    def analyze_empty_frames(trace_db_path: str, perf_db_path: str, app_pids: list, scene_dir: str = None,
                             step_id: str = None) -> Optional[dict]:
        """分析空帧 - 兼容性包装

        Args:
            trace_db_path: trace数据库路径
            perf_db_path: perf数据库路径
            app_pids: 应用进程ID列表
            scene_dir: 场景目录
            step_id: 步骤ID

        Returns:
            dict: 空帧分析结果
        """
        core = FrameAnalyzer._get_core_analyzer()
        return core.analyze_empty_frames(trace_db_path, perf_db_path, app_pids, scene_dir, step_id)

    @staticmethod
    def analyze_single_stuttered_frame(frame, vsync_key, context):
        """分析单个卡顿帧 - 兼容性包装

        Args:
            frame: 帧数据
            vsync_key: vsync键
            context: 上下文

        Returns:
            卡顿帧分析结果
        """
        core = FrameAnalyzer._get_core_analyzer()
        return core.stuttered_frame_analyzer.analyze_single_stuttered_frame(frame, vsync_key, context)

    @staticmethod
    def analyze_stuttered_frames(db_path: str, perf_db_path: str = None, step_id: str = None) -> Optional[dict]:
        """分析卡顿帧 - 兼容性包装

        Args:
            db_path: 数据库路径
            perf_db_path: perf数据库路径
            step_id: 步骤ID

        Returns:
            dict: 卡顿帧分析结果
        """
        core = FrameAnalyzer._get_core_analyzer()
        return core.analyze_stuttered_frames(db_path, perf_db_path, step_id)

    @staticmethod
    def parse_frame_slice_db(db_path: str) -> Dict[int, List[Dict[str, Any]]]:
        """解析frame_slice数据库 - 兼容性包装

        Args:
            db_path: 数据库路径

        Returns:
            Dict[int, List[Dict[str, Any]]]: 解析结果
        """
        from .frame_data_parser import parse_frame_slice_db as _parse_frame_slice_db
        return _parse_frame_slice_db(db_path)

    @staticmethod
    def get_frame_type(frame: dict, cursor, step_id: str = None) -> str:
        """获取帧类型 - 兼容性包装

        Args:
            frame: 帧数据
            cursor: 数据库游标
            step_id: 步骤ID

        Returns:
            str: 帧类型
        """
        from .frame_data_parser import get_frame_type as _get_frame_type
        return _get_frame_type(frame, cursor, step_id)


# 兼容性函数 - 直接委托给新的模块化实现
def parse_frame_slice_db(db_path: str) -> Dict[int, List[Dict[str, Any]]]:
    """解析frame_slice数据库 - 兼容性函数

    Args:
        db_path: 数据库路径

    Returns:
        Dict[int, List[Dict[str, Any]]]: 解析结果
    """
    from .frame_data_parser import parse_frame_slice_db as _parse_frame_slice_db
    return _parse_frame_slice_db(db_path)


def get_frame_type(frame: dict, cursor, step_id: str = None) -> str:
    """获取帧类型 - 兼容性函数

    Args:
        frame: 帧数据
        cursor: 数据库游标
        step_id: 步骤ID

    Returns:
        str: 帧类型
    """
    from .frame_data_parser import get_frame_type as _get_frame_type
    return _get_frame_type(frame, cursor, step_id)
