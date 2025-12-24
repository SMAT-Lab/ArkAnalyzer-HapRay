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

import functools
import logging
import os
import sqlite3
import traceback
from typing import Any, Callable, Optional

import pandas as pd

from .frame_constants import (
    HIGH_LOAD_THRESHOLD,
    PERF_DB_SIZE_ERROR_MB,
    PERF_DB_SIZE_WARNING_MB,
    PROCESS_NAME_RENDER_SERVICE,
    PROCESS_NAME_SCENEBOARD,
    PROCESS_TYPE_RENDER,
    PROCESS_TYPE_SCENEBOARD,
    PROCESS_TYPE_UI,
)
from .frame_perf_accessor import FramePerfAccessor
from .frame_trace_accessor import FrameTraceAccessor
from .frame_utils import clean_frame_data, validate_app_pids


def cached(cache_key: str, stats_key: str = None):
    """缓存装饰器

    自动处理缓存逻辑：
    1. 检查缓存是否存在
    2. 如果存在，返回缓存并更新命中统计
    3. 如果不存在，调用原函数，将结果缓存，并更新未命中统计

    Args:
        cache_key: 缓存变量名（实例变量名，如 '_frames_cache'）
        stats_key: 统计键名（用于缓存命中率统计，默认使用 cache_key 去掉下划线前缀）

    Returns:
        装饰器函数
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            # 获取缓存变量
            cache_var = getattr(self, cache_key, None)

            # 检查缓存是否存在且有效
            if cache_var is not None:
                # 对于 DataFrame，还需要检查是否为空
                if isinstance(cache_var, pd.DataFrame):
                    if not cache_var.empty:
                        # 更新命中统计
                        stats_key_name = stats_key or cache_key.lstrip('_').replace('_cache', '')
                        if stats_key_name in self._cache_hit_stats:
                            self._cache_hit_stats[stats_key_name]['hits'] += 1
                        return cache_var
                else:
                    # 非 DataFrame 类型，直接返回
                    stats_key_name = stats_key or cache_key.lstrip('_').replace('_cache', '')
                    if stats_key_name in self._cache_hit_stats:
                        self._cache_hit_stats[stats_key_name]['hits'] += 1
                    return cache_var

            # 缓存未命中，调用原函数
            stats_key_name = stats_key or cache_key.lstrip('_').replace('_cache', '')
            if stats_key_name in self._cache_hit_stats:
                self._cache_hit_stats[stats_key_name]['misses'] += 1

            # 调用原函数获取数据
            result = func(self, *args, **kwargs)

            # 缓存结果
            setattr(self, cache_key, result)

            return result

        return wrapper

    return decorator


class FrameCacheManager(FramePerfAccessor, FrameTraceAccessor):  # pylint: disable=too-many-public-methods
    """帧缓存管理器 - 负责缓存管理和数据访问委托

    主要职责：
    1. 管理各种数据缓存（帧数据、性能数据、调用链等）
    2. 提供统一的数据访问接口，默认从缓存获取，缓存无数据时从数据库获取
    3. 实现缓存策略和缓存管理
    4. 提供帧负载分析和统计功能

    注意：本类继承自FrameTraceAccessor和FramePerfAccessor，可以直接使用它们的方法
    """

    def _trace_db_has_perf_tables(self) -> bool:
        """检查trace.db是否包含必要的perf数据表

        Returns:
            bool: 如果trace.db包含perf_sample, perf_callchain, perf_files表则返回True
        """
        if not self.trace_conn:
            return False

        required_tables = ['perf_sample', 'perf_callchain', 'perf_files']
        try:
            cursor = self.trace_conn.cursor()
            # 查询所有表名
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            existing_tables = {row[0] for row in cursor.fetchall()}

            # 检查是否包含所有必需的perf表
            has_all_tables = all(table in existing_tables for table in required_tables)

            if has_all_tables:
                # 进一步检查表是否有数据（至少perf_sample表不为空）
                cursor.execute('SELECT COUNT(*) FROM perf_sample')
                sample_count = cursor.fetchone()[0]
                return sample_count > 0

            return False

        except Exception as e:
            logging.warning('检查trace.db中的perf表失败: %s', str(e))
            return False

    def __init__(self, trace_db_path: str = None, perf_db_path: str = None, app_pids: list = None):
        """初始化FrameCacheManager

        Args:
            trace_db_path: trace数据库文件路径
            perf_db_path: perf数据库文件路径
            app_pids: 应用进程ID列表
        """
        self.trace_db_path = trace_db_path
        self.perf_db_path = perf_db_path
        self.app_pids = app_pids if app_pids is not None else []

        # 建立数据库连接
        self.trace_conn: Optional[sqlite3.Connection] = None
        self.perf_conn: Optional[sqlite3.Connection] = None

        if trace_db_path and os.path.exists(trace_db_path):
            try:
                self.trace_conn = sqlite3.connect(trace_db_path)
            except Exception as e:
                logging.error('建立trace数据库连接失败: %s', str(e))

        if perf_db_path and os.path.exists(perf_db_path):
            try:
                # 检查性能数据库文件大小
                self._check_perf_db_size(perf_db_path)
                self.perf_conn = sqlite3.connect(perf_db_path)
            except Exception as e:
                logging.error('建立perf数据库连接失败: %s', str(e))
        elif self.trace_conn and self._trace_db_has_perf_tables():
            # 如果perf.db不存在但trace.db包含perf数据，则使用trace.db作为perf数据源
            logging.info('perf.db不存在，使用trace.db中的perf数据进行帧分析')
            self.perf_conn = self.trace_conn
            self.perf_db_path = trace_db_path  # 更新perf_db_path指向trace.db

        FramePerfAccessor.__init__(self, self.perf_conn)
        FrameTraceAccessor.__init__(self, self.trace_conn)

        # 【新增】自动查找并添加ArkWeb render进程
        if self.trace_conn and self.app_pids:
            self._expand_arkweb_render_processes()

        # ==================== 实例变量：缓存存储 ====================
        self._callchain_cache = None
        self._files_cache = None
        self._pid_cache = None
        self._tid_cache = None
        self._process_cache = None
        self._frame_loads_cache = []
        self._frames_cache = None
        self._perf_samples_cache = None
        self._first_frame_timestamp_cache = None

        # 缓存命中率统计
        self._cache_hit_stats = {
            'frames': {'hits': 0, 'misses': 0},
            'perf_samples': {'hits': 0, 'misses': 0},
            'callchain': {'hits': 0, 'misses': 0},
            'files': {'hits': 0, 'misses': 0},
            'process': {'hits': 0, 'misses': 0},
            'first_frame_timestamp': {'hits': 0, 'misses': 0},
        }

    # ==================== Public 接口：数据获取 ====================

    @cached('_first_frame_timestamp_cache', 'first_frame_timestamp')
    def get_first_frame_timestamp(self) -> int:
        """获取第一帧时间戳（带缓存）

        优先从缓存获取，缓存无数据时从数据库获取并缓存。

        Returns:
            int: 第一帧的时间戳（纳秒）
        """
        return self._fetch_first_frame_timestamp()

    @cached('_frames_cache', 'frames')
    def _fetch_all_frames_data(self) -> pd.DataFrame:
        """从数据库获取所有帧数据（带缓存，内部方法）

        优先从缓存获取，缓存无数据时从数据库获取并缓存。

        Returns:
            pd.DataFrame: 所有帧数据
        """
        if not self.trace_conn:
            logging.warning('trace_conn未建立，无法获取帧数据')
            return pd.DataFrame()
        # 获取所有数据，不进行 app_pids 过滤
        frames_df = FrameTraceAccessor.get_frames_data(self, app_pids=None)
        # 更新PID和TID缓存
        pids, tids = FrameTraceAccessor.extract_pid_tid_info(frames_df)
        self._pid_cache = pids
        self._tid_cache = tids
        return frames_df

    def get_frames_data(self, app_pids: list = None) -> pd.DataFrame:
        """获取帧数据（带缓存）

        优先从缓存获取，缓存无数据时从数据库获取并缓存。
        如果指定了 app_pids，会对缓存的数据进行过滤。

        Args:
            app_pids: 应用进程ID列表，如果提供则只返回这些进程的数据

        Returns:
            pd.DataFrame: 帧数据
        """
        # 从缓存获取所有数据
        frames_df = self._fetch_all_frames_data()

        # 如果指定了app_pids，进行过滤
        if app_pids is not None:
            valid_pids = validate_app_pids(app_pids)
            if valid_pids:
                return frames_df[frames_df['pid'].isin(valid_pids)]

        return frames_df

    @cached('_perf_samples_cache', 'perf_samples')
    def get_perf_samples(self) -> pd.DataFrame:
        """获取性能采样数据（带缓存）

        优先从缓存获取，缓存无数据时从数据库获取并缓存。

        Returns:
            pd.DataFrame: 性能采样数据
        """
        if not self.perf_conn:
            logging.warning('perf_conn未建立，无法获取性能采样数据')
            return pd.DataFrame()
        return FramePerfAccessor.get_perf_samples(self)

    @cached('_callchain_cache', 'callchain')
    def get_callchain_cache(self) -> pd.DataFrame:
        """获取调用链缓存数据（带缓存）

        优先从缓存获取，缓存无数据时从数据库获取并缓存。

        Returns:
            pd.DataFrame: 调用链数据
        """
        if not self.perf_conn:
            logging.warning('perf_conn未建立，无法获取调用链缓存')
            return pd.DataFrame()
        return FramePerfAccessor.get_callchain_cache(self)

    @cached('_files_cache', 'files')
    def get_files_cache(self) -> pd.DataFrame:
        """获取文件缓存数据（带缓存）

        优先从缓存获取，缓存无数据时从数据库获取并缓存。

        Returns:
            pd.DataFrame: 文件数据
        """
        if not self.perf_conn:
            logging.warning('perf_conn未建立，无法获取文件缓存')
            return pd.DataFrame()
        return FramePerfAccessor.get_files_cache(self)

    @cached('_tid_to_info_cache', 'tid_to_info')
    def get_tid_to_info(self) -> dict:
        """获取tid到线程信息的映射（带缓存）

        查询thread表获取所有thread_id和thread_name的对应关系，并缓存结果。
        这个映射用于快速查找线程名称，避免重复查询数据库。
        注意：查询所有线程信息，不仅限于应用进程，因为perf_sample可能包含系统线程。

        Returns:
            dict: {tid: {'thread_name': str, 'process_name': str}} 的字典
        """
        if not self.trace_conn:
            logging.warning('trace_conn未建立，无法获取线程信息')
            return {}

        tid_to_info = {}
        try:
            trace_cursor = self.trace_conn.cursor()
            # 查询所有线程信息，不仅限于应用进程
            # 因为perf_sample可能包含系统线程或其他进程的线程
            trace_cursor.execute("""
                SELECT DISTINCT t.tid, t.name as thread_name, p.name as process_name
                FROM thread t
                INNER JOIN process p ON t.ipid = p.ipid
            """)

            for tid, thread_name, process_name in trace_cursor.fetchall():
                tid_to_info[tid] = {'thread_name': thread_name, 'process_name': process_name}
        except Exception as e:
            logging.warning('查询线程信息失败: %s', str(e))

        return tid_to_info

    def get_total_load_for_pids(self, app_pids: list[int], time_ranges: Optional[list[tuple[int, int]]] = None) -> int:
        """获取指定进程的总负载（重写父类方法，使用trace_conn关联thread表）

        修复：原方法错误地用进程ID直接匹配thread_id，现在通过trace数据库的thread表
        找到属于指定进程的所有线程ID，然后统计这些线程的perf_sample总和。

        Args:
            app_pids: 应用进程ID列表
            time_ranges: 可选的时间范围列表，格式为 [(start_ts, end_ts), ...]
                        如果为None，则统计整个trace的CPU
                        如果提供，只统计这些时间范围内的CPU

        Returns:
            int: 总负载值（只包含指定进程的线程的perf_sample）
        """
        # 验证app_pids参数
        if not app_pids or not isinstance(app_pids, (list, tuple)) or len(app_pids) == 0:
            logging.warning('app_pids参数无效，返回0')
            return 0

        # 过滤掉无效的PID值
        valid_pids = [pid for pid in app_pids if pd.notna(pid) and isinstance(pid, (int, float))]
        if not valid_pids:
            logging.warning('没有有效的PID值，返回0')
            return 0

        if not self.trace_conn or not self.perf_conn:
            logging.warning('数据库连接未建立，返回0')
            return 0

        try:
            # 步骤1：通过trace数据库的thread表，找到属于指定进程的所有线程ID（tid）
            cursor = self.trace_conn.cursor()
            placeholders = ','.join('?' * len(valid_pids))
            thread_query = f"""
                SELECT DISTINCT t.tid
                FROM thread t
                INNER JOIN process p ON t.ipid = p.ipid
                WHERE p.pid IN ({placeholders})
            """
            cursor.execute(thread_query, valid_pids)
            thread_rows = cursor.fetchall()
            thread_ids = [row[0] for row in thread_rows if row[0] is not None]

            if not thread_ids:
                logging.warning('未找到进程 %s 的线程，返回0', valid_pids)
                return 0

            # 步骤2：统计这些线程的perf_sample总和
            perf_cursor = self.perf_conn.cursor()
            thread_placeholders = ','.join('?' * len(thread_ids))

            if time_ranges:
                # 使用时间范围过滤
                # 如果时间范围太多，SQLite 的表达式树会太大（最大深度 1000）
                # 解决方案：分批查询，每批最多 200 个时间范围
                MAX_RANGES_PER_BATCH = 200
                total_load = 0

                if len(time_ranges) <= MAX_RANGES_PER_BATCH:
                    # 时间范围不多，直接查询
                    time_conditions = []
                    time_params = []

                    for start_ts, end_ts in time_ranges:
                        time_conditions.append('(timestamp_trace >= ? AND timestamp_trace <= ?)')
                        time_params.extend([start_ts, end_ts])

                    time_condition_str = ' OR '.join(time_conditions)
                    perf_query = f"""
                        SELECT SUM(event_count) as total_load
                        FROM perf_sample
                        WHERE thread_id IN ({thread_placeholders})
                        AND ({time_condition_str})
                    """
                    perf_cursor.execute(perf_query, thread_ids + time_params)
                    result = perf_cursor.fetchone()
                    total_load = result[0] if result and result[0] else 0
                else:
                    # 时间范围太多，分批查询
                    logging.info('时间范围数量 (%d) 超过限制 (%d)，分批查询', len(time_ranges), MAX_RANGES_PER_BATCH)

                    for i in range(0, len(time_ranges), MAX_RANGES_PER_BATCH):
                        batch_ranges = time_ranges[i : i + MAX_RANGES_PER_BATCH]
                        time_conditions = []
                        time_params = []

                        for start_ts, end_ts in batch_ranges:
                            time_conditions.append('(timestamp_trace >= ? AND timestamp_trace <= ?)')
                            time_params.extend([start_ts, end_ts])

                        time_condition_str = ' OR '.join(time_conditions)
                        perf_query = f"""
                            SELECT SUM(event_count) as total_load
                            FROM perf_sample
                            WHERE thread_id IN ({thread_placeholders})
                            AND ({time_condition_str})
                        """
                        perf_cursor.execute(perf_query, thread_ids + time_params)
                        result = perf_cursor.fetchone()
                        batch_load = result[0] if result and result[0] else 0
                        total_load += batch_load

                    logging.info(
                        '分批查询完成: %d 批，总负载: %d',
                        (len(time_ranges) + MAX_RANGES_PER_BATCH - 1) // MAX_RANGES_PER_BATCH,
                        total_load,
                    )
            else:
                # 原有逻辑：统计整个trace
                perf_query = f"""
                    SELECT SUM(event_count) as total_load
                    FROM perf_sample
                    WHERE thread_id IN ({thread_placeholders})
                """
                perf_cursor.execute(perf_query, thread_ids)
                result = perf_cursor.fetchone()
                total_load = result[0] if result and result[0] else 0

            if time_ranges:
                total_time_ns = sum(end - start for start, end in time_ranges)
                logging.info(
                    '获取总负载: %d (进程ID: %s, 线程数: %d, 时间范围: %d个区间, 总时长: %.2f秒)',
                    total_load,
                    valid_pids,
                    len(thread_ids),
                    len(time_ranges),
                    total_time_ns / 1_000_000_000,
                )
            else:
                logging.info('获取总负载: %d (进程ID: %s, 线程数: %d)', total_load, valid_pids, len(thread_ids))

            return int(total_load)
        except Exception as e:
            logging.error('获取总负载失败: %s', str(e))
            logging.error('异常堆栈跟踪:\n%s', traceback.format_exc())
            return 0

    def get_thread_loads_for_pids(
        self,
        app_pids: list[int],
        time_ranges: Optional[list[tuple[int, int]]] = None,
        filter_main_thread: Optional[bool] = None,
    ) -> dict[int, int]:
        """获取指定进程的按线程分组的负载（支持时间范围去重）

        Args:
            app_pids: 应用进程ID列表
            time_ranges: 时间范围列表，格式为 [(start_ts, end_ts), ...]
                        如果为None，则统计整个trace的CPU
                        如果提供，只统计这些时间范围内的CPU（已去重）
            filter_main_thread: 是否过滤主线程
                               None: 不过滤，返回所有线程
                               True: 只返回主线程（thread_name == process_name）
                               False: 只返回后台线程（thread_name != process_name）

        Returns:
            dict[int, int]: {thread_id: total_load, ...}
        """
        # 验证app_pids参数
        if not app_pids or not isinstance(app_pids, (list, tuple)) or len(app_pids) == 0:
            logging.warning('app_pids参数无效，返回空字典')
            return {}

        # 过滤掉无效的PID值
        valid_pids = [pid for pid in app_pids if pd.notna(pid) and isinstance(pid, (int, float))]
        if not valid_pids:
            logging.warning('没有有效的PID值，返回空字典')
            return {}

        if not self.trace_conn or not self.perf_conn:
            logging.warning('数据库连接未建立，返回空字典')
            return {}

        try:
            # 步骤1：通过trace数据库的thread表，找到属于指定进程的所有线程信息
            cursor = self.trace_conn.cursor()
            placeholders = ','.join('?' * len(valid_pids))

            # 根据filter_main_thread构建查询条件
            if filter_main_thread is True:
                # 只要主线程
                thread_query = f"""
                    SELECT DISTINCT t.tid, t.name as thread_name, p.name as process_name
                    FROM thread t
                    INNER JOIN process p ON t.ipid = p.ipid
                    WHERE p.pid IN ({placeholders})
                    AND t.name = p.name
                """
            elif filter_main_thread is False:
                # 只要后台线程
                thread_query = f"""
                    SELECT DISTINCT t.tid, t.name as thread_name, p.name as process_name
                    FROM thread t
                    INNER JOIN process p ON t.ipid = p.ipid
                    WHERE p.pid IN ({placeholders})
                    AND t.name != p.name
                """
            else:
                # 不过滤，返回所有线程
                thread_query = f"""
                    SELECT DISTINCT t.tid, t.name as thread_name, p.name as process_name
                    FROM thread t
                    INNER JOIN process p ON t.ipid = p.ipid
                    WHERE p.pid IN ({placeholders})
                """

            cursor.execute(thread_query, valid_pids)
            thread_rows = cursor.fetchall()
            thread_ids = [row[0] for row in thread_rows if row[0] is not None]

            if not thread_ids:
                logging.warning('未找到进程 %s 的线程，返回空字典', valid_pids)
                return {}

            # 步骤2：统计这些线程的perf_sample总和（按线程分组）
            perf_cursor = self.perf_conn.cursor()
            thread_placeholders = ','.join('?' * len(thread_ids))

            if time_ranges:
                # 使用时间范围过滤
                MAX_RANGES_PER_BATCH = 200
                thread_loads = {}  # {thread_id: total_load}

                if len(time_ranges) <= MAX_RANGES_PER_BATCH:
                    # 时间范围不多，直接查询
                    time_conditions = []
                    time_params = []

                    for start_ts, end_ts in time_ranges:
                        time_conditions.append('(timestamp_trace >= ? AND timestamp_trace <= ?)')
                        time_params.extend([start_ts, end_ts])

                    time_condition_str = ' OR '.join(time_conditions)
                    perf_query = f"""
                        SELECT thread_id, SUM(event_count) as total_load
                        FROM perf_sample
                        WHERE thread_id IN ({thread_placeholders})
                        AND ({time_condition_str})
                        GROUP BY thread_id
                    """
                    perf_cursor.execute(perf_query, thread_ids + time_params)
                    results = perf_cursor.fetchall()

                    for thread_id, total_load in results:
                        if thread_id is not None and total_load is not None:
                            thread_loads[thread_id] = int(total_load)
                else:
                    # 时间范围太多，分批查询
                    logging.info('时间范围数量 (%d) 超过限制 (%d)，分批查询', len(time_ranges), MAX_RANGES_PER_BATCH)

                    for i in range(0, len(time_ranges), MAX_RANGES_PER_BATCH):
                        batch_ranges = time_ranges[i : i + MAX_RANGES_PER_BATCH]
                        time_conditions = []
                        time_params = []

                        for start_ts, end_ts in batch_ranges:
                            time_conditions.append('(timestamp_trace >= ? AND timestamp_trace <= ?)')
                            time_params.extend([start_ts, end_ts])

                        time_condition_str = ' OR '.join(time_conditions)
                        perf_query = f"""
                            SELECT thread_id, SUM(event_count) as total_load
                            FROM perf_sample
                            WHERE thread_id IN ({thread_placeholders})
                            AND ({time_condition_str})
                            GROUP BY thread_id
                        """
                        perf_cursor.execute(perf_query, thread_ids + time_params)
                        batch_results = perf_cursor.fetchall()

                        for thread_id, batch_load in batch_results:
                            if thread_id is not None and batch_load is not None:
                                if thread_id not in thread_loads:
                                    thread_loads[thread_id] = 0
                                thread_loads[thread_id] += int(batch_load)

                    logging.info(
                        '分批查询完成: %d 批，线程数: %d',
                        (len(time_ranges) + MAX_RANGES_PER_BATCH - 1) // MAX_RANGES_PER_BATCH,
                        len(thread_loads),
                    )
            else:
                # 原有逻辑：统计整个trace
                perf_query = f"""
                    SELECT thread_id, SUM(event_count) as total_load
                    FROM perf_sample
                    WHERE thread_id IN ({thread_placeholders})
                    GROUP BY thread_id
                """
                perf_cursor.execute(perf_query, thread_ids)
                results = perf_cursor.fetchall()
                thread_loads = {}

                for thread_id, total_load in results:
                    if thread_id is not None and total_load is not None:
                        thread_loads[thread_id] = int(total_load)

            return thread_loads
        except Exception as e:
            logging.error('获取线程负载失败: %s', str(e))
            logging.error('异常堆栈跟踪:\n%s', traceback.format_exc())
            return {}

    @cached('_process_cache', 'process')
    def get_process_cache(self) -> pd.DataFrame:
        """获取进程缓存数据（带缓存）

        优先从缓存获取，缓存无数据时从数据库获取并缓存。

        Returns:
            pd.DataFrame: 进程数据
        """
        if not self.trace_conn:
            logging.warning('trace_conn未建立，无法获取进程缓存')
            return pd.DataFrame()
        return self.get_process_data()

    def get_frame_type(self, frame: dict) -> str:
        """获取帧的类型（进程名）

        Args:
            frame: 帧数据字典

        Returns:
            str: 'ui'/'render'/'sceneboard'
        """
        ipid = frame.get('ipid')
        if ipid is None:
            return PROCESS_TYPE_UI

        # 检查缓存是否存在，如果不存在则先获取
        process_cache_data = self.get_process_cache()
        if process_cache_data.empty:
            logging.warning('process缓存为空，无法获取进程类型')
            return PROCESS_TYPE_UI

        # 从缓存中查找进程名
        process_info = process_cache_data[process_cache_data['ipid'] == ipid]

        if process_info.empty:
            return PROCESS_TYPE_UI

        process_name = process_info['name'].iloc[0]

        # 根据进程名返回类型
        if process_name == PROCESS_NAME_RENDER_SERVICE:
            return PROCESS_TYPE_RENDER
        if process_name == PROCESS_NAME_SCENEBOARD:
            return PROCESS_TYPE_SCENEBOARD
        return PROCESS_TYPE_UI

    def parse_frame_slice_db(self) -> dict[int, list[dict[str, Any]]]:
        """解析数据库文件，按vsync值分组数据

        结果按vsync值（key）从小到大排序
        只保留flag=0、1、3的帧（实际渲染的帧），排除flag=2的空帧

        帧标志 (flag) 定义：
        - flag = 0: 实际渲染帧不卡帧（正常帧）
        - flag = 1: 实际渲染帧卡帧（expectEndTime < actualEndTime为异常）
        - flag = 2: 数据不需要绘制（空帧，不参与卡顿分析）
        - flag = 3: rs进程与app进程起止异常（|expRsStartTime - expUiEndTime| < 1ms 正常，否则异常）

        Returns:
            Dict[int, List[Dict[str, Any]]]: 按vsync值分组的帧数据
        """
        if not self.trace_conn:
            logging.error('trace_conn未建立，无法解析帧数据')
            return {}

        try:
            cursor = self.trace_conn.cursor()

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
            vsync_groups: dict[int, list[dict[str, Any]]] = {}

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

            # 创建有序字典，按key值排序
            return dict(sorted(vsync_groups.items()))

        except sqlite3.Error as e:
            logging.error('数据库操作错误: %s', str(e))
            raise RuntimeError(f'数据库操作错误: {str(e)}') from e
        except Exception as e:
            logging.error('处理过程中发生错误: %s', str(e))
            raise RuntimeError(f'处理过程中发生错误: {str(e)}') from e

    # ==================== Public 接口：帧负载分析 ====================

    def add_frame_load(self, frame_load_data: dict) -> None:
        """添加帧负载数据到缓存

        Args:
            frame_load_data: 帧负载数据
        """
        # 清理数据中的NaN值
        cleaned_data = clean_frame_data(frame_load_data)

        # 按帧负载值排序插入
        frame_load = cleaned_data.get('frame_load', 0)
        insert_pos = self._find_insert_position(self._frame_loads_cache, frame_load)

        self._frame_loads_cache.insert(insert_pos, cleaned_data)

    def get_frame_loads(self) -> list:
        """获取所有帧负载数据

        Returns:
            list: 帧负载数据列表
        """
        return self._frame_loads_cache

    def get_top_frame_loads(self, top_count: int = 10) -> list:
        """获取前N个最高帧负载数据

        Args:
            top_count: 返回的帧负载数量

        Returns:
            list: 前N个最高帧负载数据
        """
        frame_loads = self.get_frame_loads()
        return frame_loads[:top_count]

    def get_frame_load_statistics(self) -> dict:
        """获取帧负载统计信息

        Returns:
            dict: 帧负载统计信息
        """
        frame_loads = self.get_frame_loads()

        if not frame_loads:
            return {
                'total_frames': 0,
                'total_load': 0,
                'avg_frame_load': 0,
                'max_frame_load': 0,
                'min_frame_load': 0,
                'high_load_frames': 0,
            }

        frame_load_values = [item.get('frame_load', 0) for item in frame_loads]
        total_load = int(sum(frame_load_values))

        return {
            'total_frames': len(frame_loads),
            'total_load': total_load,
            'average_load': float(total_load / len(frame_load_values)) if frame_load_values else 0.0,
            'max_load': int(max(frame_load_values)) if frame_load_values else 0,
            'min_load': int(min(frame_load_values)) if frame_load_values else 0,
            'high_load_frames': len([x for x in frame_load_values if x > HIGH_LOAD_THRESHOLD]),
        }

    # ==================== Public 接口：缓存管理 ====================

    def clear_cache(self) -> None:
        """清除所有缓存"""
        # 清除所有缓存
        self._frames_cache = None
        self._perf_samples_cache = None
        self._callchain_cache = None
        self._files_cache = None
        self._process_cache = None
        self._pid_cache = None
        self._tid_cache = None
        self._frame_loads_cache.clear()
        self._first_frame_timestamp_cache = None
        # 重置缓存命中率统计
        self.reset_cache_hit_stats()

    def get_cache_stats(self) -> dict:
        """获取缓存统计信息

        Returns:
            dict: 缓存统计信息
        """
        stats = {
            'frames_cached': self._frames_cache is not None,
            'perf_samples_cached': self._perf_samples_cache is not None,
            'callchain_cached': self._callchain_cache is not None,
            'files_cached': self._files_cache is not None,
            'process_cached': self._process_cache is not None,
            'pid_cached': self._pid_cache is not None,
            'tid_cached': self._tid_cache is not None,
            'frame_loads_cache_size': len(self._frame_loads_cache),
            'first_frame_timestamp_cached': self._first_frame_timestamp_cache is not None,
            'cache_hit_stats': self.get_cache_hit_stats(),
        }

        # 计算总内存使用量（估算）
        total_memory_estimate = 0
        for _cache_name, cache_df in [
            ('frames', self._frames_cache),
            ('perf_samples', self._perf_samples_cache),
            ('callchain', self._callchain_cache),
            ('files', self._files_cache),
            ('process', self._process_cache),
        ]:
            if cache_df is not None and not cache_df.empty:
                memory_estimate = int(cache_df.memory_usage(deep=True).sum())
                total_memory_estimate += memory_estimate

        stats['total_memory_estimate_bytes'] = total_memory_estimate
        stats['total_memory_estimate_mb'] = round(total_memory_estimate / (1024 * 1024), 2)

        return stats

    def get_cache_hit_stats(self) -> dict:
        """获取缓存命中率统计信息

        Returns:
            dict: 缓存命中率统计信息
        """
        stats = {}
        for data_type, hit_stats in self._cache_hit_stats.items():
            total_requests = hit_stats['hits'] + hit_stats['misses']
            hit_rate = hit_stats['hits'] / total_requests * 100 if total_requests > 0 else 0.0

            stats[data_type] = {
                'hits': hit_stats['hits'],
                'misses': hit_stats['misses'],
                'total_requests': total_requests,
                'hit_rate_percent': round(hit_rate, 2),
            }

        # 计算总体命中率
        total_hits = sum(data['hits'] for data in stats.values())
        total_requests = sum(data['total_requests'] for data in stats.values())
        overall_hit_rate = (total_hits / total_requests * 100) if total_requests > 0 else 0.0

        stats['overall'] = {
            'total_hits': total_hits,
            'total_requests': total_requests,
            'hit_rate_percent': round(overall_hit_rate, 2),
        }

        return stats

    def reset_cache_hit_stats(self) -> None:
        """重置缓存命中率统计"""
        for _, stats in self._cache_hit_stats.items():
            stats['hits'] = 0
            stats['misses'] = 0

    # ==================== Private 方法：数据获取辅助 ====================

    def _fetch_first_frame_timestamp(self) -> int:
        """从数据库获取第一帧时间戳

        Returns:
            int: 第一帧的时间戳（纳秒）
        """
        first_frame_timestamp = 0

        try:
            # 委托给数据访问层获取基准时间戳
            if not self.trace_conn:
                logging.warning('trace_conn未建立，无法获取基准时间戳')
                return 0
            first_frame_timestamp = self.get_benchmark_timestamp()
        except Exception as e:
            logging.warning('获取trace开始时间失败，使用备选方案: %s', str(e))
            # 备选方案：从缓存中获取所有帧数据并计算最小时间戳
            frames_df = self.get_frames_data()
            if not frames_df.empty:
                first_frame_timestamp = int(frames_df['ts'].min())

        return first_frame_timestamp

    # ==================== Private 方法：工具方法 ====================

    def _find_insert_position(self, frame_list: list, frame_load: int) -> int:
        """找到帧负载数据的插入位置（按降序排列）

        Args:
            frame_list: 帧负载数据列表
            frame_load: 要插入的帧负载值

        Returns:
            int: 插入位置
        """
        for i, item in enumerate(frame_list):
            if frame_load >= item.get('frame_load', 0):
                return i
        return len(frame_list)

    # ==================== Private 方法：数据库检查 ====================

    def _expand_arkweb_render_processes(self) -> None:
        """自动查找并添加ArkWeb render进程到app_pids列表

        ArkWeb使用多进程架构：主进程和render进程
        - 主进程：如 com.jd.hm.mall
        - render进程：如 .hm.mall:render 或 com.jd.hm.mall:render

        此方法会自动识别ArkWeb应用的render进程并添加到app_pids中
        """
        if not self.trace_conn or not self.app_pids:
            return

        try:
            cursor = self.trace_conn.cursor()
            original_pids = list(self.app_pids)

            # 查找所有以":render"结尾的进程（ArkWeb render进程）
            cursor.execute("""
                SELECT DISTINCT p.pid, p.name
                FROM process p
                WHERE p.name LIKE '%:render'
                AND p.name != 'render_service'
                AND p.name != 'rmrenderservice'
            """)

            all_render_processes = cursor.fetchall()

            if not all_render_processes:
                return

            # 对每个主进程，尝试匹配对应的render进程
            for main_pid in original_pids:
                # 查找主进程名
                cursor.execute('SELECT name FROM process WHERE pid = ? LIMIT 1', (main_pid,))
                result = cursor.fetchone()
                if not result:
                    continue

                main_process_name = result[0]

                # 如果主进程名不包含"."，可能不是ArkWeb，跳过
                if '.' not in main_process_name:
                    continue

                # 提取主进程名的关键部分（去掉com.前缀）
                main_key = main_process_name.split('.', 1)[-1] if '.' in main_process_name else main_process_name

                # 尝试匹配render进程
                for render_pid, render_process_name in all_render_processes:
                    # 检查render进程名是否包含主进程的关键部分
                    if (
                        main_key in render_process_name or main_process_name.split('.')[-1] in render_process_name
                    ) and render_pid not in self.app_pids:
                        self.app_pids.append(render_pid)
                        logging.info(
                            f'检测到ArkWeb render进程: {render_process_name} (PID={render_pid})，已添加到app_pids'
                        )

        except Exception as e:
            logging.warning(f'查找ArkWeb render进程失败: {e}')

    def _expand_arkweb_render_processes(self) -> None:
        """自动查找并添加ArkWeb render进程到app_pids列表

        ArkWeb使用多进程架构：主进程和render进程
        - 主进程：如 com.jd.hm.mall (PID=5489)
        - render进程：如 .hm.mall:render (PID=35301)

        此方法会自动识别ArkWeb应用的render进程并添加到app_pids中，
        确保CPU计算包含render进程的开销
        """
        if not self.trace_conn or not self.app_pids:
            return

        try:
            cursor = self.trace_conn.cursor()
            original_pids = list(self.app_pids)

            # 查找所有以":render"结尾的进程（ArkWeb render进程）
            cursor.execute("""
                SELECT DISTINCT p.pid, p.name
                FROM process p
                WHERE p.name LIKE '%:render'
                AND p.name != 'render_service'
                AND p.name != 'rmrenderservice'
            """)

            all_render_processes = cursor.fetchall()

            if not all_render_processes:
                return

            # 对每个主进程，尝试匹配对应的render进程
            for main_pid in original_pids:
                # 查找主进程名
                cursor.execute('SELECT name FROM process WHERE pid = ? LIMIT 1', (main_pid,))
                result = cursor.fetchone()
                if not result:
                    continue

                main_process_name = result[0]

                # 如果主进程名不包含"."，可能不是ArkWeb，跳过
                if '.' not in main_process_name:
                    continue

                # 提取主进程名的关键部分（去掉com.前缀）
                main_key = main_process_name.split('.', 1)[-1] if '.' in main_process_name else main_process_name

                # 尝试匹配render进程
                # 可能的匹配模式：
                # 1. com.jd.hm.mall -> com.jd.hm.mall:render
                # 2. com.jd.hm.mall -> .hm.mall:render (去掉com前缀)
                # 3. com.jd.hm.mall -> hm.mall:render
                for render_pid, render_process_name in all_render_processes:
                    if (
                        main_key in render_process_name or main_process_name.split('.')[-1] in render_process_name
                    ) and render_pid not in self.app_pids:
                        self.app_pids.append(render_pid)
                        logging.info(
                            f'检测到ArkWeb render进程: {render_process_name} (PID={render_pid})，已添加到app_pids'
                        )

        except Exception as e:
            logging.warning(f'查找ArkWeb render进程失败: {e}')

    def _check_perf_db_size(self, perf_db_path: str) -> None:
        """检查性能数据库文件大小

        Args:
            perf_db_path: perf数据库文件路径
        """
        if not perf_db_path or not os.path.exists(perf_db_path):
            return

        try:
            perf_file_size = os.path.getsize(perf_db_path) / (1024 * 1024)  # MB
            logging.info('性能数据库大小: %.1f MB', perf_file_size)

            if perf_file_size > PERF_DB_SIZE_ERROR_MB:
                logging.error('性能数据库过大 (%.1f MB)，可能导致内存不足或处理超时', perf_file_size)
            elif perf_file_size > PERF_DB_SIZE_WARNING_MB:
                logging.warning('性能数据库较大 (%.1f MB)，处理可能需要较长时间', perf_file_size)
        except Exception as e:
            logging.warning('无法检查性能数据库文件大小: %s', str(e))

    # ==================== Public 接口：连接管理 ====================

    def close_connections(self) -> None:
        """关闭数据库连接"""
        if self.trace_conn:
            try:
                self.trace_conn.close()
            except Exception as e:
                logging.warning('关闭trace数据库连接失败: %s', str(e))
            finally:
                self.trace_conn = None

        if self.perf_conn:
            try:
                self.perf_conn.close()
            except Exception as e:
                logging.warning('关闭perf数据库连接失败: %s', str(e))
            finally:
                self.perf_conn = None
