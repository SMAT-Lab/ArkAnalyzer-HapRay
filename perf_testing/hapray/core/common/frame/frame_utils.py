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

from typing import Any, Optional

import pandas as pd

"""帧分析工具函数模块

提供帧分析中常用的工具函数，避免代码重复。
"""


def clean_frame_data(frame_data: dict[str, Any]) -> dict[str, Any]:
    """清理帧数据中的NaN值，确保JSON序列化安全

    Args:
        frame_data: 原始帧数据字典

    Returns:
        dict: 清理后的帧数据字典
    """
    cleaned_data: dict[str, Any] = {}
    skip_fields = {'frame_samples', 'index'}

    for key, value in frame_data.items():
        if key in skip_fields:
            continue
        cleaned_data[key] = clean_single_value(value)

    return cleaned_data


def clean_single_value(value: Any) -> Any:
    """清理单个值，确保JSON序列化安全

    Args:
        value: 待清理的值

    Returns:
        清理后的值
    """
    if hasattr(value, 'dtype') and hasattr(value, 'item'):
        return clean_numpy_value(value)
    return clean_regular_value(value)


def clean_numpy_value(value: Any) -> Any:
    """清理numpy/pandas类型的值

    Args:
        value: numpy/pandas类型的值

    Returns:
        清理后的值
    """
    try:
        if hasattr(pd.isna(value), 'any'):
            if pd.isna(value).any():
                return 0
            return value.item()

        if pd.isna(value):
            return 0
        return value.item()
    except (ValueError, TypeError):
        return None


def clean_regular_value(value: Any) -> Any:
    """清理普通类型的值

    Args:
        value: 普通类型的值

    Returns:
        清理后的值
    """
    try:
        if pd.isna(value):
            if isinstance(value, (int, float)):
                return 0
            return None
        return value
    except (ValueError, TypeError):
        return value


def validate_app_pids(app_pids: Optional[list]) -> list[int]:
    """验证并过滤应用进程ID列表

    Args:
        app_pids: 应用进程ID列表

    Returns:
        list: 有效的进程ID列表
    """
    if not app_pids or not isinstance(app_pids, (list, tuple)) or len(app_pids) == 0:
        return []

    return [int(pid) for pid in app_pids if pd.notna(pid) and isinstance(pid, (int, float))]
