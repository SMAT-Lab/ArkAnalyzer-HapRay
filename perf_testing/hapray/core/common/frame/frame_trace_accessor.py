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

from .frame_constants import (
    FLAG_NO_DRAW,
    FLAG_NORMAL,
    FLAG_PROCESS_ERROR,
    FLAG_STUTTER,
    FRAME_TYPE_ACTUAL,
    FRAME_TYPE_EXPECT,
)
from .frame_utils import validate_app_pids


class FrameTraceAccessor:
    """Trace数据库访问器 - 专门处理trace数据库的所有操作

    主要职责：
    1. 从trace数据库读取原始数据（帧、进程、线程、调用栈等）
    2. 执行SQL查询和数据过滤
    3. 标准化数据格式，处理NaN值
    4. 提供统一的trace数据访问接口

    注意：本类不负责缓存管理，只负责数据读取和标准化
    """

    def __init__(self, trace_conn):
        """初始化FrameTraceAccessor

        Args:
            trace_conn: trace数据库连接
        """
        self.trace_conn = trace_conn

    def get_frames_data(self, app_pids: list = None) -> pd.DataFrame:
        """获取标准化的帧数据，统一管理所有frame_slice数据访问

        Args:
            app_pids: 应用进程ID列表，如果提供则只返回这些进程的数据

        Returns:
            pd.DataFrame: 标准化的帧数据
        """
        # 构建标准化的SQL查询 - 包含所有重要字段
        query = """
        SELECT
            frame_slice.ts,                    -- 数据上报时间戳
            frame_slice.dur,                   -- 帧渲染时长
            frame_slice.ipid,                  -- 进程内部id
            frame_slice.itid,                  -- 线程id
            frame_slice.flag,                  -- 帧状态标志
            frame_slice.type,                  -- 帧类型(0:实际, 1:期望)
            frame_slice.callstack_id,          -- 调用栈id
            frame_slice.vsync,                 -- 渲染帧组标识
            frame_slice.type_desc,             -- 帧类型描述
            frame_slice.src,                   -- 触发帧信息
            frame_slice.dst,                   -- 目标渲染帧
            frame_slice.depth,                 -- 深度信息(预留)
            frame_slice.frame_no,              -- 帧号(预留)
            thread.tid,                        -- 线程ID
            thread.name as thread_name,        -- 线程名称
            thread.is_main_thread,             -- 是否主线程
            process.name as process_name,      -- 进程名称
            process.pid                        -- 进程ID
        FROM frame_slice
        LEFT JOIN thread ON frame_slice.itid = thread.itid
        LEFT JOIN process ON frame_slice.ipid = process.ipid
        WHERE frame_slice.flag IS NOT NULL     -- 排除不完整数据(flag为空)
        ORDER BY frame_slice.ts
        """

        frames_df = pd.read_sql_query(query, self.trace_conn)

        # 标准化字段，处理NaN值
        frames_df = self._standardize_frames_data(frames_df)

        # 如果指定了app_pids，返回过滤后的数据
        valid_pids = validate_app_pids(app_pids)
        if valid_pids:
            return frames_df[frames_df['pid'].isin(valid_pids)]

        return frames_df

    def get_process_data(self) -> pd.DataFrame:
        """获取进程数据

        Returns:
            pd.DataFrame: 标准化的进程数据
        """
        query = """
        SELECT
            process.id,                        -- 进程在数据库重新定义的id
            process.ipid,                      -- TS内部进程id
            process.pid,                       -- 进程的真实id
            process.name,                      -- 进程名字
            process.start_ts,                  -- 开始时间
            process.switch_count,              -- 统计内部有多少个线程有切换
            process.thread_count,              -- 统计其线程个数
            process.slice_count,               -- 进程内有多少个线程有slice数据
            process.mem_count                  -- 进程是否有内存数据
        FROM process
        ORDER BY process.id
        """

        process_df = pd.read_sql_query(query, self.trace_conn)

        # 标准化字段
        return self._standardize_process_data(process_df)

    def get_thread_data(self, is_main_thread: bool = None) -> pd.DataFrame:
        """获取线程数据

        Args:
            is_main_thread: 是否主线程过滤

        Returns:
            pd.DataFrame: 标准化的线程数据
        """
        query = """
        SELECT
            thread.id,                         -- 唯一标识
            thread.itid,                       -- TS内部线程id
            thread.tid,                        -- 线程号
            thread.name,                       -- 线程名
            thread.start_ts,                   -- 开始时间
            thread.end_ts,                     -- 结束时间
            thread.ipid,                       -- 线程所属的进程id
            thread.is_main_thread,             -- 是否主线程
            thread.switch_count,               -- 当前线程的切换次数
            process.name as process_name,      -- 进程名称
            process.pid                        -- 进程ID
        FROM thread
        LEFT JOIN process ON thread.ipid = process.ipid
        """
        params = []

        if is_main_thread is not None:
            query += ' WHERE thread.is_main_thread = ?'
            params.append(1 if is_main_thread else 0)

        query += ' ORDER BY thread.id'

        thread_df = pd.read_sql_query(query, self.trace_conn, params=params)

        # 标准化字段
        return self._standardize_thread_data(thread_df)

    # ==================== 专用过滤方法 ====================

    def get_frames_by_filter(self, flag: int = None, frame_type: int = None, app_pids: list = None) -> pd.DataFrame:
        """根据条件过滤帧数据

        Args:
            flag: 帧标志过滤
            frame_type: 帧类型过滤
            app_pids: 应用进程ID列表

        Returns:
            pd.DataFrame: 过滤后的帧数据
        """
        frames_df = self.get_frames_data(app_pids)

        if flag is not None:
            frames_df = frames_df[frames_df['flag'] == flag]

        if frame_type is not None:
            frames_df = frames_df[frames_df['type'] == frame_type]

        return frames_df

    def get_stuttered_frames(self, app_pids: list = None) -> pd.DataFrame:
        """获取卡顿帧数据"""
        return self.get_frames_by_filter(flag=FLAG_STUTTER, app_pids=app_pids)

    def get_actual_frames(self, app_pids: list = None) -> pd.DataFrame:
        """获取实际帧数据"""
        return self.get_frames_by_filter(frame_type=FRAME_TYPE_ACTUAL, app_pids=app_pids)

    def get_empty_frames(self, app_pids: list = None) -> pd.DataFrame:
        """获取空帧数据"""
        return self.get_frames_by_filter(flag=FLAG_NO_DRAW, app_pids=app_pids)

    def get_main_threads(self) -> pd.DataFrame:
        """获取主线程数据"""
        return self.get_thread_data(is_main_thread=True)

    def get_frame_statistics(self) -> dict:
        """获取帧统计信息

        Returns:
            dict: 帧统计信息
        """
        frames_df = self.get_frames_data()

        if frames_df.empty:
            return {
                'total_frames': 0,
                'actual_frames': 0,
                'expect_frames': 0,
                'stuttered_frames': 0,
                'empty_frames': 0,
                'normal_frames': 0,
            }

        return {
            'total_frames': len(frames_df),
            'actual_frames': len(frames_df[frames_df['type'] == FRAME_TYPE_ACTUAL]),
            'expect_frames': len(frames_df[frames_df['type'] == FRAME_TYPE_EXPECT]),
            'stuttered_frames': len(frames_df[frames_df['flag'] == FLAG_STUTTER]),
            'empty_frames': len(frames_df[frames_df['flag'] == FLAG_NO_DRAW]),
            'normal_frames': len(frames_df[frames_df['flag'] == FLAG_NORMAL]),
        }

    # ==================== 高级查询方法 ====================

    def get_empty_frames_with_details(self, app_pids: list[int]) -> pd.DataFrame:
        """获取空帧详细信息（包含进程、线程、调用栈信息）

        Args:
            app_pids: 应用进程ID列表

        Returns:
            pd.DataFrame: 包含详细信息的空帧数据
        """
        # 验证app_pids参数
        valid_pids = validate_app_pids(app_pids)
        if not valid_pids:
            logging.warning('没有有效的PID值，返回空DataFrame')
            return pd.DataFrame()

        query = f"""
        WITH filtered_frames AS (
            -- 首先获取符合条件的帧
            SELECT fs.ts, fs.dur, fs.ipid, fs.itid, fs.callstack_id, fs.vsync, fs.flag, fs.type
            FROM frame_slice fs
            WHERE fs.flag = {FLAG_NO_DRAW}
            AND fs.type = {FRAME_TYPE_ACTUAL}
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
            return pd.read_sql_query(query, self.trace_conn, params=valid_pids)
        except Exception as e:
            logging.error('获取空帧详细信息失败: %s', str(e))
            return pd.DataFrame()

    # ==================== 工具方法 ====================

    def get_benchmark_timestamp(self) -> int:
        """获取基准时间戳（与HiSmartPerf工具保持一致）

        HiSmartPerf工具使用trace_range表的start_ts作为基准时间戳来计算相对时间。
        为了确保我们的分析结果与HiSmartPerf工具一致，我们也使用相同的基准点。

        Returns:
            int: 基准时间戳（纳秒）
        """
        try:
            cursor = self.trace_conn.cursor()
            # 优先从trace_range表获取start_ts作为基准时间戳（与HiSmartPerf工具一致）
            cursor.execute('SELECT start_ts FROM trace_range LIMIT 1')
            result = cursor.fetchone()
            if result and result[0] is not None:
                return int(result[0])

            # 如果trace_range表中没有数据，尝试获取frame_slice表的最小时间戳
            cursor.execute('SELECT MIN(ts) FROM frame_slice WHERE ts IS NOT NULL')
            result = cursor.fetchone()
            if result and result[0] is not None:
                return int(result[0])

            return 0
        except Exception as e:
            logging.warning('获取基准时间戳失败: %s', str(e))
            return 0

    @staticmethod
    def extract_pid_tid_info(trace_df: pd.DataFrame) -> tuple[list[int], list[int]]:
        """从trace_df中提取PID和TID信息

        Args:
            trace_df: 包含pid和tid信息的DataFrame

        Returns:
            tuple: (pids_list, tids_list) 提取的PID和TID列表
        """
        try:
            if trace_df.empty:
                return [], []

            # 提取唯一的PID和TID
            unique_pids = {int(pid) for pid in trace_df['pid'].dropna().unique() if pd.notna(pid)}
            unique_tids = {int(tid) for tid in trace_df['tid'].dropna().unique() if pd.notna(tid)}

            return list(unique_pids), list(unique_tids)

        except Exception as e:
            logging.error('提取PID/TID信息失败: %s', str(e))
            return [], []

    # ==================== 数据标准化方法 ====================

    def _standardize_frames_data(self, frames_df: pd.DataFrame) -> pd.DataFrame:
        """标准化帧数据，处理NaN值和字段类型

        Args:
            frames_df: 原始帧数据

        Returns:
            pd.DataFrame: 标准化后的帧数据
        """
        # 处理数值字段的NaN值
        numeric_fields = [
            'ts',
            'dur',
            'ipid',
            'itid',
            'flag',
            'type',
            'callstack_id',
            'vsync',
            'tid',
            'pid',
            'src',
            'dst',
            'depth',
            'frame_no',
        ]
        for field in numeric_fields:
            if field in frames_df.columns:
                frames_df[field] = pd.to_numeric(frames_df[field], errors='coerce').fillna(0)

        # 处理字符串字段的NaN值
        string_fields = ['thread_name', 'process_name', 'type_desc']
        for field in string_fields:
            if field in frames_df.columns:
                frames_df[field] = frames_df[field].fillna('unknown')

        # 处理布尔字段
        if 'is_main_thread' in frames_df.columns:
            frames_df['is_main_thread'] = frames_df['is_main_thread'].fillna(0).astype(int)

        # 添加计算字段
        frames_df['start_time'] = frames_df['ts']
        frames_df['end_time'] = frames_df['ts'] + frames_df['dur']

        # 添加帧类型标识字段
        frames_df['is_actual_frame'] = (frames_df['type'] == FRAME_TYPE_ACTUAL).astype(int)
        frames_df['is_expect_frame'] = (frames_df['type'] == FRAME_TYPE_EXPECT).astype(int)

        # 添加帧状态标识字段
        frames_df['is_normal_frame'] = (frames_df['flag'] == FLAG_NORMAL).astype(int)  # 不卡顿
        frames_df['is_stuttered_frame'] = (frames_df['flag'] == FLAG_STUTTER).astype(int)  # 卡帧
        frames_df['is_no_draw_frame'] = (frames_df['flag'] == FLAG_NO_DRAW).astype(int)  # 不需要绘制
        frames_df['is_rs_app_abnormal'] = (frames_df['flag'] == FLAG_PROCESS_ERROR).astype(int)  # RS与APP异常

        return frames_df

    def _standardize_thread_data(self, thread_df: pd.DataFrame) -> pd.DataFrame:
        """标准化线程数据

        Args:
            thread_df: 原始线程数据

        Returns:
            pd.DataFrame: 标准化后的线程数据
        """
        # 处理数值字段的NaN值
        numeric_fields = ['id', 'itid', 'tid', 'start_ts', 'end_ts', 'ipid', 'is_main_thread', 'switch_count', 'pid']
        for field in numeric_fields:
            if field in thread_df.columns:
                thread_df[field] = pd.to_numeric(thread_df[field], errors='coerce').fillna(0)

        # 处理字符串字段的NaN值
        string_fields = ['name', 'process_name']
        for field in string_fields:
            if field in thread_df.columns:
                thread_df[field] = thread_df[field].fillna('unknown')

        # 添加计算字段
        thread_df['thread_duration'] = thread_df['end_ts'] - thread_df['start_ts']

        # 添加线程类型标识字段
        thread_df['is_main_thread_bool'] = (thread_df['is_main_thread'] == 1).astype(int)
        thread_df['is_worker_thread'] = (thread_df['is_main_thread'] == 0).astype(int)

        return thread_df

    def _standardize_process_data(self, process_df: pd.DataFrame) -> pd.DataFrame:
        """标准化进程数据

        Args:
            process_df: 原始进程数据

        Returns:
            pd.DataFrame: 标准化后的进程数据
        """
        # 处理数值字段的NaN值
        numeric_fields = ['id', 'ipid', 'pid', 'start_ts', 'switch_count', 'thread_count', 'slice_count', 'mem_count']
        for field in numeric_fields:
            if field in process_df.columns:
                process_df[field] = pd.to_numeric(process_df[field], errors='coerce').fillna(0)

        # 处理字符串字段的NaN值
        if 'name' in process_df.columns:
            process_df['name'] = process_df['name'].fillna('unknown')

        # 添加计算字段
        process_df['active_thread_ratio'] = process_df['switch_count'] / process_df['thread_count'].replace(0, 1)
        process_df['slice_thread_ratio'] = process_df['slice_count'] / process_df['thread_count'].replace(0, 1)
        process_df['has_memory_data'] = (process_df['mem_count'] > 0).astype(int)
        process_df['has_slice_data'] = (process_df['slice_count'] > 0).astype(int)

        return process_df
