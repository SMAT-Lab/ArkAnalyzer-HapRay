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
from typing import List, Dict

import pandas as pd


class FrameDbAdvancedAccessor:
    """复杂联合查询数据访问层 - 专门处理多表关联的复杂SQL查询

    主要职责：
    1. 复杂的多表联合查询
    2. 业务特定的数据过滤和聚合
    3. 查询结果缓存管理
    4. 与FrameCacheManager集成
    """

    @staticmethod
    def get_empty_frames_with_details(trace_conn, app_pids: List[int], step_id: str = None) -> pd.DataFrame:  # pylint: disable=unused-argument
        """获取空帧详细信息（包含进程、线程、调用栈信息）

        Args:
            trace_conn: trace数据库连接
            app_pids: 应用进程ID列表
            step_id: 步骤ID，用于缓存

        Returns:
            pd.DataFrame: 包含详细信息的空帧数据
        """
        # 验证app_pids参数
        if not app_pids or not isinstance(app_pids, (list, tuple)) or len(app_pids) == 0:
            logging.warning("app_pids参数无效，返回空DataFrame")
            return pd.DataFrame()

        # 过滤掉无效的PID值
        valid_pids = [pid for pid in app_pids if pd.notna(pid) and isinstance(pid, (int, float))]
        if not valid_pids:
            logging.warning("没有有效的PID值，返回空DataFrame")
            return pd.DataFrame()

        query = f"""
        WITH filtered_frames AS (
            -- 首先获取符合条件的帧
            SELECT fs.ts, fs.dur, fs.ipid, fs.itid, fs.callstack_id, fs.vsync, fs.flag, fs.type
            FROM frame_slice fs
            WHERE fs.flag = 2
            AND fs.type = 0
        ),
        process_filtered AS (
            -- 通过process表过滤出app_pids中的帧
            SELECT ff.*, p.pid, p.name as process_name, t.tid, t.name as thread_name, t.is_main_thread
            FROM filtered_frames ff
            JOIN process p ON ff.ipid = p.ipid
            JOIN thread t ON ff.itid = t.itid
            WHERE p.pid IN ({','.join('?' * len(valid_pids))})
        )
        -- 最后获取调用栈信息
        SELECT pf.*, cs.name as callstack_name
        FROM process_filtered pf
        LEFT JOIN callstack cs ON pf.callstack_id = cs.id
        ORDER BY pf.ts
        """

        try:
            result_df = pd.read_sql_query(query, trace_conn, params=valid_pids)
            # logging.info("获取空帧详细信息: %d 条记录", len(result_df))
            return result_df
        except Exception as e:
            logging.error("获取空帧详细信息失败: %s", str(e))
            return pd.DataFrame()

    @staticmethod
    def get_stuttered_frames_with_context(trace_conn, step_id: str = None) -> pd.DataFrame:  # pylint: disable=unused-argument
        """获取卡顿帧上下文信息

        Args:
            trace_conn: trace数据库连接
            step_id: 步骤ID，用于缓存

        Returns:
            pd.DataFrame: 包含上下文信息的卡顿帧数据
        """
        query = """
        WITH stuttered_frames AS (
            -- 获取卡顿帧
            SELECT fs.*,
                   p.name as process_name, p.pid,
                   t.name as thread_name, t.is_main_thread,
                   cs.name as callstack_name
            FROM frame_slice fs
            LEFT JOIN process p ON fs.ipid = p.ipid
            LEFT JOIN thread t ON fs.itid = t.itid
            LEFT JOIN callstack cs ON fs.callstack_id = cs.id
            WHERE fs.flag IN (1, 3)  -- 卡顿帧和进程异常帧
            AND fs.type = 0  -- 实际帧
        ),
        frame_context AS (
            -- 添加上下文信息
            SELECT sf.*,
                   LAG(sf.ts) OVER (PARTITION BY sf.vsync ORDER BY sf.ts) as prev_frame_ts,
                   LEAD(sf.ts) OVER (PARTITION BY sf.vsync ORDER BY sf.ts) as next_frame_ts,
                   LAG(sf.dur) OVER (PARTITION BY sf.vsync ORDER BY sf.ts) as prev_frame_dur,
                   LEAD(sf.dur) OVER (PARTITION BY sf.vsync ORDER BY sf.ts) as next_frame_dur
            FROM stuttered_frames sf
        )
        SELECT * FROM frame_context
        ORDER BY ts
        """

        try:
            result_df = pd.read_sql_query(query, trace_conn)
            # logging.info("获取卡顿帧上下文信息: %d 条记录", len(result_df))
            return result_df
        except Exception as e:
            logging.error("获取卡顿帧上下文信息失败: %s", str(e))
            return pd.DataFrame()

    @staticmethod
    def get_frame_load_analysis_data(trace_conn, perf_conn, app_pids: List[int],
                                     step_id: str = None) -> Dict[str, pd.DataFrame]:  # pylint: disable=unused-argument
        """获取帧负载分析所需的完整数据

        Args:
            trace_conn: trace数据库连接
            perf_conn: perf数据库连接
            app_pids: 应用进程ID列表
            step_id: 步骤ID，用于缓存

        Returns:
            Dict[str, pd.DataFrame]: 包含各种分析数据的字典
        """
        # 验证app_pids参数
        if not app_pids or not isinstance(app_pids, (list, tuple)) or len(app_pids) == 0:
            logging.warning("app_pids参数无效，返回空数据")
            return {
                'frames': pd.DataFrame(),
                'perf_samples': pd.DataFrame(),
                'callchains': pd.DataFrame(),
                'files': pd.DataFrame()
            }

        # 过滤掉无效的PID值
        valid_pids = [pid for pid in app_pids if pd.notna(pid) and isinstance(pid, (int, float))]
        if not valid_pids:
            logging.warning("没有有效的PID值，返回空数据")
            return {
                'frames': pd.DataFrame(),
                'perf_samples': pd.DataFrame(),
                'callchains': pd.DataFrame(),
                'files': pd.DataFrame()
            }

        try:
            # 获取帧数据
            frames_query = f"""
            SELECT
                fs.ts, fs.dur, fs.ipid, fs.itid,
                fs.flag, fs.type, fs.callstack_id,
                fs.vsync, fs.type_desc,
                t.tid, t.name as thread_name, t.is_main_thread,
                p.name as process_name, p.pid
            FROM frame_slice fs
            LEFT JOIN thread t ON fs.itid = t.itid
            LEFT JOIN process p ON fs.ipid = p.ipid
            WHERE fs.flag IN (0, 1, 2, 3)
            AND p.pid IN ({','.join('?' * len(valid_pids))})
            ORDER BY fs.ts
            """

            frames_df = pd.read_sql_query(frames_query, trace_conn, params=valid_pids)

            # 获取性能样本数据
            perf_query = """
            SELECT
                callchain_id, timestamp_trace, thread_id, event_count,
                event_type_id, cpu_id, thread_state
            FROM perf_sample
            ORDER BY timestamp_trace
            """

            perf_df = pd.read_sql_query(perf_query, perf_conn)

            # 获取调用链数据
            callchain_query = """
            SELECT
                callchain_id, depth, ip, vaddr_in_file, file_id, symbol_id, name
            FROM perf_callchain
            ORDER BY callchain_id, depth
            """

            callchain_df = pd.read_sql_query(callchain_query, perf_conn)

            # 获取文件信息
            files_query = """
            SELECT
                file_id, serial_id, symbol, path
            FROM perf_files
            ORDER BY file_id, serial_id
            """

            files_df = pd.read_sql_query(files_query, perf_conn)

            result = {
                'frames': frames_df,
                'perf_samples': perf_df,
                'callchains': callchain_df,
                'files': files_df
            }

            # logging.info("获取帧负载分析数据: frames=%d, perf_samples=%d, callchains=%d, files=%d",
            #              len(frames_df), len(perf_df), len(callchain_df), len(files_df))

            return result

        except Exception as e:
            logging.error("获取帧负载分析数据失败: %s", str(e))
            return {
                'frames': pd.DataFrame(),
                'perf_samples': pd.DataFrame(),
                'callchains': pd.DataFrame(),
                'files': pd.DataFrame()
            }

    @staticmethod
    def get_frame_statistics_by_process(trace_conn, app_pids: List[int], step_id: str = None) -> pd.DataFrame:  # pylint: disable=unused-argument
        """按进程获取帧统计信息

        Args:
            trace_conn: trace数据库连接
            app_pids: 应用进程ID列表
            step_id: 步骤ID，用于缓存

        Returns:
            pd.DataFrame: 按进程分组的帧统计信息
        """
        # 验证app_pids参数
        if not app_pids or not isinstance(app_pids, (list, tuple)) or len(app_pids) == 0:
            logging.warning("app_pids参数无效，返回空DataFrame")
            return pd.DataFrame()

        # 过滤掉无效的PID值
        valid_pids = [pid for pid in app_pids if pd.notna(pid) and isinstance(pid, (int, float))]
        if not valid_pids:
            logging.warning("没有有效的PID值，返回空DataFrame")
            return pd.DataFrame()

        query = f"""
        SELECT
            p.pid,
            p.name as process_name,
            COUNT(*) as total_frames,
            SUM(CASE WHEN fs.flag = 0 THEN 1 ELSE 0 END) as normal_frames,
            SUM(CASE WHEN fs.flag = 1 THEN 1 ELSE 0 END) as stuttered_frames,
            SUM(CASE WHEN fs.flag = 2 THEN 1 ELSE 0 END) as empty_frames,
            SUM(CASE WHEN fs.flag = 3 THEN 1 ELSE 0 END) as process_error_frames,
            SUM(CASE WHEN fs.type = 0 THEN 1 ELSE 0 END) as actual_frames,
            SUM(CASE WHEN fs.type = 1 THEN 1 ELSE 0 END) as expect_frames,
            AVG(fs.dur) as avg_frame_duration,
            MAX(fs.dur) as max_frame_duration,
            MIN(fs.dur) as min_frame_duration
        FROM frame_slice fs
        JOIN process p ON fs.ipid = p.ipid
        WHERE p.pid IN ({','.join('?' * len(valid_pids))})
        GROUP BY p.pid, p.name
        ORDER BY total_frames DESC
        """

        try:
            result_df = pd.read_sql_query(query, trace_conn, params=valid_pids)
            # logging.info("获取进程帧统计信息: %d 个进程", len(result_df))
            return result_df
        except Exception as e:
            logging.error("获取进程帧统计信息失败: %s", str(e))
            return pd.DataFrame()

    @staticmethod
    def get_frame_timeline_analysis(trace_conn, app_pids: List[int], time_window_ms: int = 1000) -> pd.DataFrame:
        """获取帧时间线分析数据

        Args:
            trace_conn: trace数据库连接
            app_pids: 应用进程ID列表
            time_window_ms: 时间窗口大小（毫秒）

        Returns:
            pd.DataFrame: 时间线分析数据
        """
        # 验证app_pids参数
        if not app_pids or not isinstance(app_pids, (list, tuple)) or len(app_pids) == 0:
            logging.warning("app_pids参数无效，返回空DataFrame")
            return pd.DataFrame()

        # 过滤掉无效的PID值
        valid_pids = [pid for pid in app_pids if pd.notna(pid) and isinstance(pid, (int, float))]
        if not valid_pids:
            logging.warning("没有有效的PID值，返回空DataFrame")
            return pd.DataFrame()

        query = f"""
        WITH frame_windows AS (
            SELECT
                fs.*,
                p.name as process_name,
                t.name as thread_name,
                t.is_main_thread,
                (fs.ts / {time_window_ms * 1000000}) as window_id  -- 转换为纳秒
            FROM frame_slice fs
            JOIN process p ON fs.ipid = p.ipid
            JOIN thread t ON fs.itid = t.itid
            WHERE p.pid IN ({','.join('?' * len(valid_pids))})
        ),
        window_stats AS (
            SELECT
                window_id,
                COUNT(*) as frame_count,
                SUM(CASE WHEN flag = 1 THEN 1 ELSE 0 END) as stutter_count,
                SUM(CASE WHEN flag = 2 THEN 1 ELSE 0 END) as empty_count,
                AVG(dur) as avg_duration,
                MIN(ts) as window_start,
                MAX(ts) as window_end
            FROM frame_windows
            GROUP BY window_id
        )
        SELECT
            *,
            (window_end - window_start) / 1000000.0 as window_duration_ms,
            CASE
                WHEN frame_count > 0 THEN (stutter_count * 100.0 / frame_count)
                ELSE 0
            END as stutter_percentage
        FROM window_stats
        ORDER BY window_id
        """

        try:
            result_df = pd.read_sql_query(query, trace_conn, params=valid_pids)
            # logging.info("获取帧时间线分析数据: %d 个时间窗口", len(result_df))
            return result_df
        except Exception as e:
            logging.error("获取帧时间线分析数据失败: %s", str(e))
            return pd.DataFrame()

    @staticmethod
    def get_perf_samples_with_callchain(perf_conn) -> pd.DataFrame:
        """获取性能样本及其调用链信息

        Args:
            perf_conn: perf数据库连接

        Returns:
            pd.DataFrame: 包含调用链信息的性能样本数据
        """
        query = """
        SELECT
            ps.*,
            pc.depth, pc.ip, pc.vaddr_in_file, pc.file_id, pc.symbol_id, pc.name as function_name,
            pf.symbol, pf.path
        FROM perf_sample ps
        LEFT JOIN perf_callchain pc ON ps.callchain_id = pc.callchain_id
        LEFT JOIN perf_files pf ON pc.file_id = pf.file_id AND pc.symbol_id = pf.serial_id
        ORDER BY ps.timestamp_trace, pc.depth
        """

        try:
            result_df = pd.read_sql_query(query, perf_conn)
            # logging.info("获取性能样本调用链信息: %d 条记录", len(result_df))
            return result_df
        except Exception as e:
            logging.error("获取性能样本调用链信息失败: %s", str(e))
            return pd.DataFrame()

    @staticmethod
    def get_thread_performance_analysis(trace_conn, app_pids: List[int]) -> pd.DataFrame:
        """获取线程性能分析数据

        Args:
            trace_conn: trace数据库连接
            app_pids: 应用进程ID列表

        Returns:
            pd.DataFrame: 线程性能分析数据
        """
        # 验证app_pids参数
        if not app_pids or not isinstance(app_pids, (list, tuple)) or len(app_pids) == 0:
            logging.warning("app_pids参数无效，返回空DataFrame")
            return pd.DataFrame()

        # 过滤掉无效的PID值
        valid_pids = [pid for pid in app_pids if pd.notna(pid) and isinstance(pid, (int, float))]
        if not valid_pids:
            logging.warning("没有有效的PID值，返回空DataFrame")
            return pd.DataFrame()

        query = f"""
        WITH thread_frames AS (
            SELECT
                t.tid, t.name as thread_name, t.is_main_thread,
                p.pid, p.name as process_name,
                COUNT(fs.id) as frame_count,
                AVG(fs.dur) as avg_frame_duration,
                SUM(CASE WHEN fs.flag = 1 THEN 1 ELSE 0 END) as stutter_count,
                SUM(CASE WHEN fs.flag = 2 THEN 1 ELSE 0 END) as empty_count
            FROM thread t
            JOIN process p ON t.ipid = p.ipid
            LEFT JOIN frame_slice fs ON t.itid = fs.itid
            WHERE p.pid IN ({','.join('?' * len(valid_pids))})
            GROUP BY t.tid, t.name, t.is_main_thread, p.pid, p.name
        ),
        thread_perf AS (
            SELECT
                thread_id,
                COUNT(*) as perf_sample_count,
                AVG(event_count) as avg_event_count,
                COUNT(DISTINCT callchain_id) as unique_callchain_count
            FROM perf_sample
            GROUP BY thread_id
        )
        SELECT
            tf.*,
            tp.perf_sample_count,
            tp.avg_event_count,
            tp.unique_callchain_count
        FROM thread_frames tf
        LEFT JOIN thread_perf tp ON tf.tid = tp.thread_id
        ORDER BY tf.frame_count DESC
        """

        try:
            result_df = pd.read_sql_query(query, trace_conn, params=valid_pids)
            # logging.info("获取线程性能分析数据: %d 个线程", len(result_df))
            return result_df
        except Exception as e:
            logging.error("获取线程性能分析数据失败: %s", str(e))
            return pd.DataFrame()
