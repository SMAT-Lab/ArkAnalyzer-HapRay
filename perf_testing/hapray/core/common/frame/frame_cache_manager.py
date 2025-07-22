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
import pandas as pd
from typing import List


class FrameCacheManager:
    """帧分析缓存管理器
    
    负责管理所有与帧分析相关的缓存数据，包括：
    1. callchain缓存
    2. files缓存
    3. process缓存
    4. PID/TID缓存
    """

    # 类变量用于存储缓存
    _callchain_cache = {}  # 缓存callchain数据，格式: {step_id: pd.DataFrame}
    _files_cache = {}      # 缓存files数据，格式: {step_id: pd.DataFrame}
    _pid_cache = {}        # 缓存pid数据，格式: {step_id: [pids]}
    _tid_cache = {}        # 缓存tid数据，格式: {step_id: [tids]}
    _process_cache = {}    # 缓存process数据，格式: {step_id: pd.DataFrame}

    @staticmethod
    def update_pid_tid_cache(step_id: str, trace_df: pd.DataFrame) -> None:
        """根据trace_df中的数据更新PID和TID缓存

        Args:
            step_id: 步骤ID，如'step1'或'1'
            trace_df: 包含pid和tid信息的DataFrame
        """
        try:
            if trace_df.empty:
                return

            # 提取唯一的PID和TID
            unique_pids = set(trace_df['pid'].dropna().unique())
            unique_tids = set(trace_df['tid'].dropna().unique())

            # 更新PID缓存
            FrameCacheManager._pid_cache[step_id] = list(unique_pids)

            # 更新TID缓存
            FrameCacheManager._tid_cache[step_id] = list(unique_tids)

            logging.debug("从trace_df更新缓存: %s, PIDs: %s, TIDs: %s", step_id, len(unique_pids), len(unique_tids))

        except Exception as e:
            logging.error("更新PID/TID缓存失败: %s", str(e))

    @staticmethod
    def get_callchain_cache(perf_conn, step_id: str = None) -> pd.DataFrame:
        """获取并缓存perf_callchain表的数据

        Args:
            perf_conn: perf数据库连接
            step_id: 步骤ID，用作缓存key

        Returns:
            pd.DataFrame: callchain缓存数据
        """
        # 如果没有提供step_id，使用连接对象作为key
        cache_key = step_id if step_id else str(perf_conn)

        # 如果已有缓存且不为空，直接返回
        if cache_key in FrameCacheManager._callchain_cache and not FrameCacheManager._callchain_cache[cache_key].empty:
            logging.debug("使用已存在的callchain缓存，共 %s 条记录", len(FrameCacheManager._callchain_cache[cache_key]))
            return FrameCacheManager._callchain_cache[cache_key]

        try:
            callchain_cache = pd.read_sql_query("""
                SELECT
                    id,
                    callchain_id,
                    depth,
                    file_id,
                    symbol_id
                FROM perf_callchain
            """, perf_conn)

            # 保存到类变量
            FrameCacheManager._callchain_cache[cache_key] = callchain_cache
            logging.debug("缓存了 %s 条callchain记录，key: %s", len(callchain_cache), cache_key)
            return callchain_cache

        except Exception as e:
            logging.error("获取callchain缓存数据失败: %s", str(e))
            return pd.DataFrame()

    @staticmethod
    def get_files_cache(perf_conn, step_id: str = None) -> pd.DataFrame:
        """获取并缓存perf_files表的数据

        Args:
            perf_conn: perf数据库连接
            step_id: 步骤ID，用作缓存key

        Returns:
            pd.DataFrame: files缓存数据
        """
        # 如果没有提供step_id，使用连接对象作为key
        cache_key = step_id if step_id else str(perf_conn)

        # 如果已有缓存且不为空，直接返回
        if cache_key in FrameCacheManager._files_cache and not FrameCacheManager._files_cache[cache_key].empty:
            logging.debug("使用已存在的files缓存，共 %s 条记录", len(FrameCacheManager._files_cache[cache_key]))
            return FrameCacheManager._files_cache[cache_key]

        try:
            files_cache = pd.read_sql_query("""
                SELECT
                    file_id,
                    serial_id,
                    symbol,
                    path
                FROM perf_files
            """, perf_conn)

            # 保存到类变量
            FrameCacheManager._files_cache[cache_key] = files_cache
            logging.debug("缓存了 %s 条files记录，key: %s", len(files_cache), cache_key)
            return files_cache

        except Exception as e:
            logging.error("获取files缓存数据失败: %s", str(e))
            return pd.DataFrame()

    @staticmethod
    def get_process_cache(trace_conn, step_id: str = None) -> pd.DataFrame:
        """获取并缓存process表的数据

        Args:
            trace_conn: trace数据库连接
            step_id: 步骤ID，用作缓存key

        Returns:
            pd.DataFrame: process缓存数据
        """
        # 如果没有提供step_id，使用连接对象作为key
        cache_key = step_id if step_id else str(trace_conn)

        # 如果已有缓存且不为空，直接返回
        if cache_key in FrameCacheManager._process_cache and not FrameCacheManager._process_cache[cache_key].empty:
            logging.debug("使用已存在的process缓存，共 %s 条记录", len(FrameCacheManager._process_cache[cache_key]))
            return FrameCacheManager._process_cache[cache_key]

        try:
            process_cache = pd.read_sql_query("""
                SELECT
                    ipid,
                    name
                FROM process
            """, trace_conn)

            # 保存到类变量
            FrameCacheManager._process_cache[cache_key] = process_cache
            logging.debug("缓存了 %s 条process记录，key: %s", len(process_cache), cache_key)
            return process_cache

        except Exception as e:
            logging.error("获取process缓存数据失败: %s", str(e))
            return pd.DataFrame()

    @staticmethod
    def get_process_cache_by_key(cache_key: str) -> pd.DataFrame:
        """通过缓存key获取process缓存数据

        Args:
            cache_key: 缓存key

        Returns:
            pd.DataFrame: process缓存数据
        """
        if cache_key in FrameCacheManager._process_cache:
            return FrameCacheManager._process_cache[cache_key]
        return pd.DataFrame()

    @staticmethod
    def clear_cache(step_id: str = None) -> None:
        """清除指定步骤的缓存数据

        Args:
            step_id: 步骤ID，如果为None则清除所有缓存
        """
        if step_id:
            FrameCacheManager._callchain_cache.pop(step_id, None)
            FrameCacheManager._files_cache.pop(step_id, None)
            FrameCacheManager._pid_cache.pop(step_id, None)
            FrameCacheManager._tid_cache.pop(step_id, None)
            FrameCacheManager._process_cache.pop(step_id, None)
            logging.debug("已清除步骤 %s 的缓存", step_id)
        else:
            FrameCacheManager._callchain_cache.clear()
            FrameCacheManager._files_cache.clear()
            FrameCacheManager._pid_cache.clear()
            FrameCacheManager._tid_cache.clear()
            FrameCacheManager._process_cache.clear()
            logging.debug("已清除所有缓存")

    @staticmethod
    def get_cache_stats() -> dict:
        """获取缓存统计信息

        Returns:
            dict: 缓存统计信息
        """
        return {
            "callchain_cache_size": len(FrameCacheManager._callchain_cache),
            "files_cache_size": len(FrameCacheManager._files_cache),
            "pid_cache_size": len(FrameCacheManager._pid_cache),
            "tid_cache_size": len(FrameCacheManager._tid_cache),
            "process_cache_size": len(FrameCacheManager._process_cache)
        } 