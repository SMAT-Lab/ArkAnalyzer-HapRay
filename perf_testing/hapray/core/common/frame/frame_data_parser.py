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

import logging
import sqlite3
import traceback
from typing import Dict, Any, List

from .frame_core_cache_manager import FrameCacheManager


def parse_frame_slice_db(db_path: str) -> Dict[int, List[Dict[str, Any]]]:
    """解析数据库文件，按vsync值分组数据

    结果按vsync值（key）从小到大排序
    只保留flag=0、1、3的帧（实际渲染的帧），排除flag=2的空帧

    帧标志 (flag) 定义：
    - flag = 0: 实际渲染帧不卡帧（正常帧）
    - flag = 1: 实际渲染帧卡帧（expectEndTime < actualEndTime为异常）
    - flag = 2: 数据不需要绘制（空帧，不参与卡顿分析）
    - flag = 3: rs进程与app进程起止异常（|expRsStartTime - expUiEndTime| < 1ms 正常，否则异常）

    Args:
        db_path: 数据库文件路径

    Returns:
        Dict[int, List[Dict[str, Any]]]: 按vsync值分组的帧数据
    """
    try:
        # 连接数据库
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # 修改SQL查询，获取process.name和thread.name字段
        cursor.execute("""
            SELECT fs.*, t.tid, t.name as thread_name, p.name as process_name
            FROM frame_slice fs
            LEFT JOIN thread t ON fs.itid = t.itid
            LEFT JOIN process p ON fs.ipid = p.ipid
        """)

        # 获取列名
        columns = [description[0] for description in cursor.description]

        # 按vsync值分组
        vsync_groups: Dict[int, List[Dict[str, Any]]] = {}
        total_frames = 0

        # 遍历所有行，将数据转换为字典并按vsync分组
        for row in cursor.fetchall():
            row_dict = dict(zip(columns, row))

            vsync_value = row_dict['vsync']
            # 跳过vsync为None的数据
            if vsync_value is None:
                continue
            try:
                # 确保vsync_value是整数
                vsync_value = int(vsync_value)
            except (ValueError, TypeError):
                continue

            if vsync_value not in vsync_groups:
                vsync_groups[vsync_value] = []

            vsync_groups[vsync_value].append(row_dict)
            total_frames += 1

        # 关闭数据库连接
        conn.close()

        # 创建有序字典，按key值排序
        return dict(sorted(vsync_groups.items()))

    except sqlite3.Error as e:
        raise RuntimeError(f"数据库操作错误: {str(e)}\n{traceback.format_exc()}") from e
    except Exception as e:
        raise RuntimeError(f"处理过程中发生错误: {str(e)}\n{traceback.format_exc()}") from e


def get_frame_type(frame: dict, cursor, step_id: str = None) -> str:
    """获取帧的类型（进程名）

    参数:
        frame: 帧数据字典
        cursor: 数据库游标
        step_id: 步骤ID，用于缓存key

    返回:
        str: 'ui'/'render'/'sceneboard'
    """
    ipid = frame.get("ipid")
    if ipid is None or cursor is None:
        return "ui"

    # 确定缓存key
    cache_key = step_id if step_id else str(cursor.connection)

    # 检查缓存是否存在，如果不存在则先获取
    process_cache_data = FrameCacheManager.get_process_cache_by_key(cache_key)
    if process_cache_data.empty:
        # 缓存不存在，需要先获取并缓存
        trace_conn = cursor.connection
        FrameCacheManager.get_process_cache(trace_conn, step_id)
        # 再次获取缓存
        process_cache_data = FrameCacheManager.get_process_cache_by_key(cache_key)
        if process_cache_data.empty:
            logging.warning("process缓存为空，无法获取进程类型")
            return "ui"

    # 从缓存中查找进程名
    process_info = process_cache_data[process_cache_data['ipid'] == ipid]

    if process_info.empty:
        return "ui"

    process_name = process_info['name'].iloc[0]

    # 根据进程名返回类型
    if process_name == "render_service":
        return "render"
    if process_name == "ohos.sceneboard":
        return "sceneboard"
    return "ui"


def validate_database_compatibility(db_path: str) -> bool:
    """验证数据库兼容性

    Args:
        db_path: 数据库文件路径

    Returns:
        bool: 是否兼容
    """
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # 检查SQLite版本是否支持WITH子句
        cursor.execute("SELECT sqlite_version()")
        version = cursor.fetchone()[0]
        version_parts = [int(x) for x in version.split('.')]
        if version_parts[0] < 3 or (version_parts[0] == 3 and version_parts[1] < 8):
            logging.error("SQLite版本 %s 不支持WITH子句，需要3.8.3或更高版本", version)
            conn.close()
            return False

        # 确保所需表存在
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        required_tables = ['frame_slice', 'process', 'thread', 'callstack']
        if not all(table in tables for table in required_tables):
            logging.error("数据库中缺少必要的表，需要: %s", required_tables)
            conn.close()
            return False

        conn.close()
        return True

    except Exception as e:
        logging.error("验证数据库兼容性失败: %s", str(e))
        return False


def get_database_metadata(db_path: str) -> Dict[str, Any]:
    """获取数据库元数据信息

    Args:
        db_path: 数据库文件路径

    Returns:
        Dict[str, Any]: 元数据信息
    """
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        metadata = {}

        # 获取runtime时间
        try:
            cursor.execute("SELECT value FROM meta WHERE name = 'runtime'")
            runtime_result = cursor.fetchone()
            metadata['runtime'] = runtime_result[0] if runtime_result else None
        except sqlite3.DatabaseError:
            logging.warning("Failed to get runtime from database, setting to None")
            metadata['runtime'] = None

        # 获取表信息
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        metadata['tables'] = tables

        # 获取SQLite版本
        cursor.execute("SELECT sqlite_version()")
        metadata['sqlite_version'] = cursor.fetchone()[0]

        conn.close()
        return metadata

    except Exception as e:
        logging.error("获取数据库元数据失败: %s", str(e))
        return {}


def extract_frame_statistics(db_path: str) -> Dict[str, Any]:
    """提取帧统计信息

    Args:
        db_path: 数据库文件路径

    Returns:
        Dict[str, Any]: 帧统计信息
    """
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        stats = {}

        # 总帧数
        cursor.execute("SELECT COUNT(*) FROM frame_slice")
        stats['total_frames'] = cursor.fetchone()[0]

        # 按flag分组的帧数
        cursor.execute("SELECT flag, COUNT(*) FROM frame_slice GROUP BY flag")
        flag_stats = dict(cursor.fetchall())
        stats['frames_by_flag'] = flag_stats

        # 按type分组的帧数
        cursor.execute("SELECT type, COUNT(*) FROM frame_slice GROUP BY type")
        type_stats = dict(cursor.fetchall())
        stats['frames_by_type'] = type_stats

        # 进程数量
        cursor.execute("SELECT COUNT(*) FROM process")
        stats['process_count'] = cursor.fetchone()[0]

        # 线程数量
        cursor.execute("SELECT COUNT(*) FROM thread")
        stats['thread_count'] = cursor.fetchone()[0]

        conn.close()
        return stats

    except Exception as e:
        logging.error("提取帧统计信息失败: %s", str(e))
        return {}
