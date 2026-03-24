"""
数据收集模块

包含数据采集、传输、命令构建等相关功能
"""

from hapray.core.collection.capture_ui import CaptureUI
from hapray.core.collection.data_collector import DataCollector
from hapray.core.collection.data_transfer import DataTransfer
from hapray.core.collection.process_manager import ProcessManager

__all__ = [
    'CaptureUI',
    'DataCollector',
    'DataTransfer',
    'ProcessManager',
]
