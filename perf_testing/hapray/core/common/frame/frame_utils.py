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

import sqlite3
import logging
import traceback
from typing import Any, Optional, Dict, Set, Tuple

import pandas as pd

"""帧分析基础工具函数模块

提供帧分析中常用的基础工具函数，避免代码重复。
包括：数据清理、验证、系统线程判断等。

注意：CPU计算相关函数和空刷帧分析公共模块类已移至frame_empty_common.py
为了向后兼容，这里在文件末尾重新导出这些函数和类。
"""

logger = logging.getLogger(__name__)


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


def is_system_thread(process_name: Optional[str], thread_name: Optional[str]) -> bool:
    """判断线程是否为系统线程（参考RN实现）
    
    系统线程包括：
    - hiperf（性能采集工具）
    - render_service（渲染服务）
    - sysmgr-main（系统管理）
    - OS_开头的线程
    - ohos.开头的线程
    - pp.开头的线程
    - 其他系统服务
    
    Args:
        process_name: 进程名
        thread_name: 线程名
        
    Returns:
        True 如果是系统线程，False 如果是应用线程
    """
    if not process_name:
        process_name = ""
    if not thread_name:
        thread_name = ""
    
    # 系统进程名模式
    system_process_patterns = [
        'hiperf',
        'render_service',
        'sysmgr-main',
        'OS_%',
        'ohos.%',
        'pp.%',
        'hilogd',
        'hiprofiler',
        'hiprofiler_cmd',
        'hiprofiler_plug',
        'hiprofilerd',
        'kworker',
        'hdcd',
        'hiview',
        'foundation',
        'resource_schedu',
        'netmanager',
        'wifi_manager',
        'telephony',
        'sensors',
        'multimodalinput',
        'accountmgr',
        'accesstoken_ser',
        'samgr',
        'memmgrservice',
        'distributeddata',
        'privacy_service',
        'security_guard',
        'time_service',
        'bluetooth_servi',
        'media_service',
        'audio_server',
        'rmrenderservice',
        'ohos.sceneboard',
    ]
    
    # 系统线程名模式
    system_thread_patterns = [
        'OS_%',
        'ohos.%',
        'pp.%',
        'hiperf',
        'hiprofiler',
        'hiprofiler_cmd',
        'hiprofiler_plug',
        'hiprofilerd',
        'HmTraceReader',
        'kworker',
        'hilogd',
        'render_service',
        'VSyncGenerator',
        'RSUniRenderThre',
        'RSHardwareThrea',
        'RSBackgroundThr',
        'Present Fence',
        'Acquire Fence',
        'Release Fence',
        'gpu-work-server',
        'tppmgr-sched-in',
        'tppmgr-misc',
        'fs-kmsgfd',
        'dh-irq-bind',
        'dpu_gfx_primary',
        'display_engine_',
        'gpu-pm-release',
        'hisi_frw',
        'rcu_sched',
        'effect thread',
        'gpu-wq-id',
        'gpu-token-id',
        'irq/',
        'ksoftirqd',
        'netlink_handle',
        'hisi_tx_sch',
        'hisi_hcc',
        'hisi_rxdata',
        'spi',
        'gpufreq',
        'npu_excp',
        'dra_thread',
        'agent_vltmm',
        'tuid',
        'hw_kstate',
        'pci_ete_rx0',
        'wlan_bus_rx',
        'bbox_main',
        'kthread-joind',
        'dmabuf-deferred',
        'chr_web_thread',
        'ldk-kallocd',
    ]
    
    # 检查进程名
    for pattern in system_process_patterns:
        if pattern.endswith('%'):
            if process_name.startswith(pattern[:-1]):
                return True
        elif pattern.endswith('.'):
            if process_name.startswith(pattern):
                return True
        else:
            if pattern in process_name or process_name == pattern:
                return True
    
    # 检查线程名
    for pattern in system_thread_patterns:
        if pattern.endswith('%'):
            if thread_name.startswith(pattern[:-1]):
                return True
        elif pattern.endswith('_'):
            if thread_name.startswith(pattern):
                return True
        else:
            if pattern in thread_name or thread_name == pattern:
                return True
    
    return False


# ============================================================================
# 向后兼容：从frame_empty_common导入CPU计算函数和公共模块类
# ============================================================================
# 注意：必须在文件末尾导入，避免循环导入
from .frame_empty_common import (
    calculate_thread_instructions,
    calculate_process_instructions,
    calculate_app_frame_cpu_waste,
    EmptyFrameCPUCalculator,
    EmptyFrameCallchainAnalyzer,
    EmptyFrameResultBuilder
)

# 导出列表，确保向后兼容
__all__ = [
    'clean_frame_data',
    'clean_single_value',
    'clean_numpy_value',
    'clean_regular_value',
    'validate_app_pids',
    'is_system_thread',
    'calculate_thread_instructions',
    'calculate_process_instructions',
    'calculate_app_frame_cpu_waste',
    'EmptyFrameCPUCalculator',
    'EmptyFrameCallchainAnalyzer',
    'EmptyFrameResultBuilder'
]


# ============================================================================
# 向后兼容：从frame_empty_common导入CPU计算函数和公共模块类
# ============================================================================
# 注意：以下内容已移至frame_empty_common.py，这里仅保留导入以确保向后兼容
#
# 已移动的内容：
# - calculate_thread_instructions() - 线程级CPU计算
# - calculate_process_instructions() - 进程级CPU计算
# - calculate_app_frame_cpu_waste() - 应用帧CPU浪费计算
# - EmptyFrameCPUCalculator - CPU计算模块
# - EmptyFrameCallchainAnalyzer - 调用链分析模块
# - EmptyFrameResultBuilder - 结果构建模块
#
# 用法：
#   from .frame_utils import calculate_process_instructions  # 仍然有效
#   from .frame_empty_common import calculate_process_instructions  # 推荐
# ============================================================================
