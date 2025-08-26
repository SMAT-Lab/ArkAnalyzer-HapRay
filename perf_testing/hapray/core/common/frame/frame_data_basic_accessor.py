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
import time

import pandas as pd


class FrameDbBasicAccessor:
    """帧数据访问器 - 负责所有数据库读取和数据标准化

    主要职责：
    1. 从trace和perf数据库读取原始数据
    2. 执行SQL查询和数据过滤
    3. 标准化数据格式，处理NaN值
    4. 提供统一的数据访问接口

    注意：本类不负责缓存管理，只负责数据读取和标准化
    """

    # ==================== 公共数据访问方法 ====================

    @staticmethod
    def get_frames_data(trace_conn, app_pids: list = None) -> pd.DataFrame:
        """获取标准化的帧数据，统一管理所有frame_slice数据访问

        Args:
            trace_conn: trace数据库连接
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

        frames_df = pd.read_sql_query(query, trace_conn)

        # 标准化字段，处理NaN值
        frames_df = FrameDbBasicAccessor._standardize_frames_data(frames_df)

        # 如果指定了app_pids，返回过滤后的数据
        if app_pids is not None and isinstance(app_pids, list | tuple) and len(app_pids) > 0:
            # 过滤掉NaN值，确保只包含有效的数字
            valid_pids = [pid for pid in app_pids if pd.notna(pid) and isinstance(pid, int | float)]
            if valid_pids:
                return frames_df[frames_df['pid'].isin(valid_pids)]

        return frames_df

    @staticmethod
    def get_perf_samples(perf_conn) -> pd.DataFrame:
        """获取性能采样数据

        Args:
            perf_conn: perf数据库连接
            step_id: 步骤ID，用作缓存key

        Returns:
            pd.DataFrame: 标准化的性能采样数据
        """
        start_time = time.time()
        logging.info('开始加载性能采样数据...')

        # 先检查数据量
        try:
            count_query = 'SELECT COUNT(*) as total FROM perf_sample'
            total_records = pd.read_sql_query(count_query, perf_conn)['total'].iloc[0]
            logging.info('性能数据库记录总数: %d', total_records)

            if total_records > 1000000:  # 超过100万条记录
                logging.warning('性能数据量较大 (%d 条记录)，预计需要较长时间处理', total_records)
            elif total_records > 5000000:  # 超过500万条记录
                logging.error('性能数据量过大 (%d 条记录)，可能导致内存不足', total_records)

        except Exception as e:
            logging.warning('无法获取记录总数: %s', str(e))
            total_records = 0

        query = """
        SELECT
            perf_sample.id,                    -- 唯一标识
            perf_sample.callchain_id,          -- 关联perf_callchain表callchain_id
            perf_sample.timeStamp as timestamp, -- 未进行时钟源同步的时间戳（修正字段名）
            perf_sample.thread_id,             -- 线程号
            perf_sample.event_count,           -- 采样统计
            perf_sample.event_type_id,         -- 事件类型编号
            perf_sample.timestamp_trace,       -- 时钟源同步后的时间戳
            perf_sample.cpu_id,                -- cpu核编号
            perf_sample.thread_state           -- 线程状态
        FROM perf_sample
        ORDER BY perf_sample.timeStamp
        """

        try:
            logging.info('执行性能数据查询...')
            perf_df = pd.read_sql_query(query, perf_conn)

            elapsed_time = time.time() - start_time
            logging.info('性能数据加载完成！耗时: %.2f秒，实际记录数: %d', elapsed_time, len(perf_df))

            if elapsed_time > 30:  # 超过30秒
                logging.warning('性能数据加载耗时较长: %.2f秒', elapsed_time)

            # 标准化字段
            return FrameDbBasicAccessor._standardize_perf_sample_data(perf_df)

        except Exception as e:
            elapsed_time = time.time() - start_time
            logging.error('性能数据加载失败！耗时: %.2f秒，错误: %s', elapsed_time, str(e))
            return pd.DataFrame()

    @staticmethod
    def get_callchain_cache(perf_conn) -> pd.DataFrame:
        """获取调用链缓存数据

        Args:
            perf_conn: perf数据库连接
            step_id: 步骤ID，用作缓存key

        Returns:
            pd.DataFrame: 标准化的调用链数据
        """
        query = """
        SELECT
            perf_callchain.id,                 -- 唯一标识
            perf_callchain.callchain_id,       -- 标识一组调用堆栈
            perf_callchain.depth,              -- 调用栈深度
            perf_callchain.ip,                 -- 函数ip
            perf_callchain.vaddr_in_file,      -- 函数在文件中的虚拟地址
            perf_callchain.file_id,            -- 与perf_files中的file_id字段相关联
            perf_callchain.symbol_id,          -- 与perf_files中的serial_id相关联
            perf_callchain.name                -- 函数名
        FROM perf_callchain
        ORDER BY perf_callchain.callchain_id, perf_callchain.depth
        """

        callchain_df = pd.read_sql_query(query, perf_conn)

        # 标准化字段
        return FrameDbBasicAccessor._standardize_perf_callchain_data(callchain_df)

    @staticmethod
    def get_files_cache(perf_conn) -> pd.DataFrame:
        """获取文件缓存数据

        Args:
            perf_conn: perf数据库连接
            step_id: 步骤ID，用作缓存key

        Returns:
            pd.DataFrame: 标准化的文件数据
        """
        query = """
        SELECT
            perf_files.id,                     -- 唯一标识
            perf_files.file_id,                -- 文件编号
            perf_files.serial_id,              -- 一个文件中可能有多个函数，serial_id表示函数的编号
            perf_files.symbol,                 -- 函数名
            perf_files.path                    -- 文件路径
        FROM perf_files
        ORDER BY perf_files.file_id, perf_files.serial_id
        """

        files_df = pd.read_sql_query(query, perf_conn)

        # 标准化字段
        return FrameDbBasicAccessor._standardize_perf_files_data(files_df)

    @staticmethod
    def get_process_cache(trace_conn) -> pd.DataFrame:
        """获取进程缓存数据

        Args:
            trace_conn: trace数据库连接
            step_id: 步骤ID，用作缓存key

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

        process_df = pd.read_sql_query(query, trace_conn)

        # 标准化字段
        return FrameDbBasicAccessor._standardize_process_data(process_df)

    @staticmethod
    def get_callstack_data(trace_conn, name_pattern: str = None) -> pd.DataFrame:
        """获取调用栈数据

        Args:
            trace_conn: trace数据库连接
            step_id: 步骤ID，用作缓存key
            name_pattern: 调用名称模式匹配

        Returns:
            pd.DataFrame: 标准化的调用栈数据
        """
        query = """
        SELECT
            callstack.id,                      -- 唯一标识
            callstack.ts,                      -- 数据事件上报时间戳
            callstack.dur,                     -- 调用时长
            callstack.callid,                  -- 调用者的ID
            callstack.cat,                     -- 表示当前栈帧属于哪个业务
            callstack.name,                    -- 调用名称
            callstack.depth,                   -- 调用深度
            callstack.cookie,                  -- 异步调用的cookie值
            callstack.parent_id,               -- 父调用的id
            callstack.argsetid,                -- 调用的参数列表
            callstack.chainId,                 -- 分布式数据中的chainId
            callstack.spanId,                  -- 分布式调用关联关系
            callstack.parentSpanId,            -- 分布式调用关联关系
            callstack.flag                     -- 分布式调用标志
        FROM callstack
        """
        params = []

        if name_pattern:
            query += ' WHERE callstack.name LIKE ?'
            params.append(name_pattern)

        query += ' ORDER BY callstack.ts'

        callstack_df = pd.read_sql_query(query, trace_conn, params=params)

        # 标准化字段
        return FrameDbBasicAccessor._standardize_callstack_data(callstack_df)

    @staticmethod
    def get_thread_data(trace_conn, is_main_thread: bool = None) -> pd.DataFrame:
        """获取线程数据

        Args:
            trace_conn: trace数据库连接
            step_id: 步骤ID，用作缓存key
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

        thread_df = pd.read_sql_query(query, trace_conn, params=params)

        # 标准化字段
        return FrameDbBasicAccessor._standardize_thread_data(thread_df)

    @staticmethod
    def get_process_data(trace_conn, process_name_pattern: str = None) -> pd.DataFrame:
        """获取进程数据

        Args:
            trace_conn: trace数据库连接
            step_id: 步骤ID，用作缓存key
            process_name_pattern: 进程名称模式匹配

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
        """
        params = []

        if process_name_pattern:
            query += ' WHERE process.name LIKE ?'
            params.append(process_name_pattern)

        query += ' ORDER BY process.id'

        process_df = pd.read_sql_query(query, trace_conn, params=params)

        # 标准化字段
        return FrameDbBasicAccessor._standardize_process_data(process_df)

    @staticmethod
    def get_symbol_data(perf_conn, symbol_pattern: str = None) -> pd.DataFrame:
        """获取符号数据，支持模式匹配

        Args:
            perf_conn: perf数据库连接
            step_id: 步骤ID，用作缓存key
            symbol_pattern: 符号名称模式匹配

        Returns:
            pd.DataFrame: 符号数据
        """
        # 构建查询 - 从perf_files表获取symbol信息
        query = """
        SELECT
            perf_files.id,                    -- 唯一标识
            perf_files.file_id,               -- 文件编号
            perf_files.serial_id,             -- 函数编号
            perf_files.symbol,                -- 函数名
            perf_files.path                   -- 文件路径
        FROM perf_files
        """
        params = []

        if symbol_pattern:
            query += ' WHERE perf_files.symbol LIKE ?'
            params.append(symbol_pattern)

        query += ' ORDER BY perf_files.symbol'

        symbol_df = pd.read_sql_query(query, perf_conn, params=params)

        # 标准化字段
        return FrameDbBasicAccessor._standardize_perf_files_data(symbol_df)

    # ==================== 专用过滤方法 ====================

    @staticmethod
    def get_frames_by_filter(
        trace_conn, flag: int = None, frame_type: int = None, app_pids: list = None
    ) -> pd.DataFrame:
        """根据条件过滤帧数据

        Args:
            trace_conn: trace数据库连接
            flag: 帧标志过滤
            frame_type: 帧类型过滤
            app_pids: 应用进程ID列表

        Returns:
            pd.DataFrame: 过滤后的帧数据
        """
        frames_df = FrameDbBasicAccessor.get_frames_data(trace_conn, app_pids)

        if flag is not None:
            frames_df = frames_df[frames_df['flag'] == flag]

        if frame_type is not None:
            frames_df = frames_df[frames_df['type'] == frame_type]

        return frames_df

    @staticmethod
    def get_stuttered_frames(trace_conn, app_pids: list = None) -> pd.DataFrame:
        """获取卡顿帧数据"""
        return FrameDbBasicAccessor.get_frames_by_filter(trace_conn, flag=1, app_pids=app_pids)

    @staticmethod
    def get_actual_frames(trace_conn, app_pids: list = None) -> pd.DataFrame:
        """获取实际帧数据"""
        return FrameDbBasicAccessor.get_frames_by_filter(trace_conn, frame_type=0, app_pids=app_pids)

    @staticmethod
    def get_empty_frames(trace_conn, app_pids: list = None) -> pd.DataFrame:
        """获取空帧数据"""
        return FrameDbBasicAccessor.get_frames_by_filter(trace_conn, flag=2, app_pids=app_pids)

    @staticmethod
    def get_main_threads(trace_conn) -> pd.DataFrame:
        """获取主线程数据"""
        return FrameDbBasicAccessor.get_thread_data(trace_conn, is_main_thread=True)

    @staticmethod
    def get_perf_samples_by_thread(perf_conn) -> dict:
        """按线程分组获取性能采样数据

        Args:
            perf_conn: perf数据库连接

        Returns:
            dict: 按线程ID分组的性能采样数据
        """
        perf_df = FrameDbBasicAccessor.get_perf_samples(perf_conn)

        if perf_df.empty:
            return {}

        # 按线程ID分组
        grouped_data = {}
        for thread_id, group in perf_df.groupby('thread_id'):
            grouped_data[thread_id] = group.to_dict('records')

        return grouped_data

    @staticmethod
    def get_frame_statistics(trace_conn) -> dict:
        """获取帧统计信息

        Args:
            trace_conn: trace数据库连接

        Returns:
            dict: 帧统计信息
        """
        frames_df = FrameDbBasicAccessor.get_frames_data(trace_conn)

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
            'actual_frames': len(frames_df[frames_df['type'] == 0]),
            'expect_frames': len(frames_df[frames_df['type'] == 1]),
            'stuttered_frames': len(frames_df[frames_df['flag'] == 1]),
            'empty_frames': len(frames_df[frames_df['flag'] == 2]),
            'normal_frames': len(frames_df[frames_df['flag'] == 0]),
        }

    # ==================== 数据标准化方法 ====================

    @staticmethod
    def _standardize_frames_data(frames_df: pd.DataFrame) -> pd.DataFrame:
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
        frames_df['is_actual_frame'] = (frames_df['type'] == 0).astype(int)
        frames_df['is_expect_frame'] = (frames_df['type'] == 1).astype(int)

        # 添加帧状态标识字段
        frames_df['is_normal_frame'] = (frames_df['flag'] == 0).astype(int)  # 不卡顿
        frames_df['is_stuttered_frame'] = (frames_df['flag'] == 1).astype(int)  # 卡帧
        frames_df['is_no_draw_frame'] = (frames_df['flag'] == 2).astype(int)  # 不需要绘制
        frames_df['is_rs_app_abnormal'] = (frames_df['flag'] == 3).astype(int)  # RS与APP异常

        return frames_df

    @staticmethod
    def _standardize_callstack_data(callstack_df: pd.DataFrame) -> pd.DataFrame:
        """标准化调用栈数据

        Args:
            callstack_df: 原始调用栈数据

        Returns:
            pd.DataFrame: 标准化后的调用栈数据
        """
        # 处理数值字段的NaN值
        numeric_fields = ['id', 'ts', 'dur', 'callid', 'depth', 'cookie', 'parent_id', 'argsetid']
        for field in numeric_fields:
            if field in callstack_df.columns:
                callstack_df[field] = pd.to_numeric(callstack_df[field], errors='coerce').fillna(0)

        # 处理字符串字段的NaN值
        string_fields = ['cat', 'name', 'chainId', 'spanId', 'parentSpanId', 'flag']
        for field in string_fields:
            if field in callstack_df.columns:
                callstack_df[field] = callstack_df[field].fillna('')

        # 添加计算字段
        callstack_df['end_ts'] = callstack_df['ts'] + callstack_df['dur']

        # 添加调用类型标识字段
        callstack_df['is_async_call'] = (callstack_df['cookie'].notna() & (callstack_df['cookie'] != 0)).astype(int)
        callstack_df['is_sync_call'] = (callstack_df['cookie'].isna() | (callstack_df['cookie'] == 0)).astype(int)
        callstack_df['is_distributed_call'] = (
            callstack_df['chainId'].notna() & (callstack_df['chainId'] != '')
        ).astype(int)
        callstack_df['is_sender'] = (callstack_df['flag'] == 'C').astype(int)
        callstack_df['is_receiver'] = (callstack_df['flag'] == 'S').astype(int)

        return callstack_df

    @staticmethod
    def _standardize_perf_sample_data(perf_df: pd.DataFrame) -> pd.DataFrame:
        """标准化性能采样数据

        Args:
            perf_df: 原始性能采样数据

        Returns:
            pd.DataFrame: 标准化后的性能采样数据
        """
        # 检查DataFrame是否为空
        if perf_df.empty:
            logging.warning('perf_df为空，返回空的DataFrame')
            return perf_df

        # 处理数值字段的NaN值
        numeric_fields = [
            'id',
            'callchain_id',
            'timestamp_trace',
            'thread_id',
            'event_count',
            'event_type_id',
            'cpu_id',
        ]
        for field in numeric_fields:
            if field in perf_df.columns:
                perf_df[field] = pd.to_numeric(perf_df[field], errors='coerce').fillna(0)
            else:
                logging.warning('perf_df中缺少字段: %s', field)
                perf_df[field] = 0

        # 处理字符串字段的NaN值
        if 'thread_state' in perf_df.columns:
            perf_df['thread_state'] = perf_df['thread_state'].fillna('-')
        else:
            logging.warning('perf_df中缺少thread_state字段')
            perf_df['thread_state'] = '-'

        # 添加计算字段（使用timestamp_trace作为主要时间字段）
        if 'timestamp_trace' in perf_df.columns:
            perf_df['time_sync_diff'] = 0  # 如果只有timestamp_trace，时间差设为0
        else:
            logging.warning('perf_df中缺少timestamp_trace字段')
            perf_df['time_sync_diff'] = 0

        # 添加线程状态标识字段
        perf_df['is_running'] = (perf_df['thread_state'] == 'Running').astype(int)
        perf_df['is_suspended'] = (perf_df['thread_state'] == 'Suspend').astype(int)
        perf_df['is_other_state'] = (
            (perf_df['thread_state'] != 'Running') & (perf_df['thread_state'] != 'Suspend')
        ).astype(int)

        return perf_df

    @staticmethod
    def _standardize_perf_callchain_data(callchain_df: pd.DataFrame) -> pd.DataFrame:
        """标准化性能调用链数据

        Args:
            callchain_df: 原始性能调用链数据

        Returns:
            pd.DataFrame: 标准化后的性能调用链数据
        """
        # 处理数值字段的NaN值
        numeric_fields = ['id', 'callchain_id', 'depth', 'ip', 'vaddr_in_file', 'file_id', 'symbol_id']
        for field in numeric_fields:
            if field in callchain_df.columns:
                callchain_df[field] = pd.to_numeric(callchain_df[field], errors='coerce').fillna(0)

        # 处理字符串字段的NaN值
        if 'name' in callchain_df.columns:
            callchain_df['name'] = callchain_df['name'].fillna('unknown')

        # 添加计算字段
        callchain_df['addr_offset'] = callchain_df['ip'] - callchain_df['vaddr_in_file']

        # 添加调用栈层级标识字段
        callchain_df['is_top_level'] = (callchain_df['depth'] == 0).astype(int)
        callchain_df['is_leaf_level'] = (
            callchain_df['depth'] == callchain_df.groupby('callchain_id')['depth'].transform('max')
        ).astype(int)

        return callchain_df

    @staticmethod
    def _standardize_perf_files_data(files_df: pd.DataFrame) -> pd.DataFrame:
        """标准化性能文件数据

        Args:
            files_df: 原始性能文件数据

        Returns:
            pd.DataFrame: 标准化后的性能文件数据
        """
        # 处理数值字段的NaN值
        numeric_fields = ['id', 'file_id', 'serial_id']
        for field in numeric_fields:
            if field in files_df.columns:
                files_df[field] = pd.to_numeric(files_df[field], errors='coerce').fillna(0)

        # 处理字符串字段的NaN值
        string_fields = ['symbol', 'path']
        for field in string_fields:
            if field in files_df.columns:
                files_df[field] = files_df[field].fillna('')

        # 添加计算字段
        if 'path' in files_df.columns:
            files_df['file_name'] = files_df['path'].apply(lambda x: x.split('/')[-1] if x else '')
            files_df['file_extension'] = files_df['file_name'].apply(lambda x: x.split('.')[-1] if '.' in x else '')
            files_df['file_directory'] = files_df['path'].apply(lambda x: '/'.join(x.split('/')[:-1]) if x else '')

        # 添加函数类型标识字段
        if 'symbol' in files_df.columns:
            files_df['is_constructor'] = files_df['symbol'].str.contains('::', na=False).astype(int)
            files_df['is_template'] = files_df['symbol'].str.contains('<', na=False).astype(int)

        return files_df

    @staticmethod
    def _standardize_thread_data(thread_df: pd.DataFrame) -> pd.DataFrame:
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

    @staticmethod
    def _standardize_process_data(process_df: pd.DataFrame) -> pd.DataFrame:
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

    # ==================== 工具方法 ====================

    @staticmethod
    def _clean_frame_data(frame_data: dict) -> dict:  # pylint: disable=duplicate-code
        """清理帧数据中的NaN值，确保JSON序列化安全"""

        cleaned_data = {}
        for key, value in frame_data.items():
            if key == 'frame_samples':
                # 跳过frame_samples字段，它会在后续处理中被移除
                continue
            if key == 'index':
                # 跳过index字段，它会在后续处理中被移除
                continue
            if pd.isna(value):
                # 处理NaN值
                if isinstance(value, (int, float)):
                    cleaned_data[key] = 0
                else:
                    cleaned_data[key] = None
            elif hasattr(value, 'dtype') and hasattr(value, 'item'):
                # numpy类型
                if pd.isna(value):
                    cleaned_data[key] = 0
                else:
                    cleaned_data[key] = value.item()
            else:
                cleaned_data[key] = value

        return cleaned_data

    @staticmethod
    def get_benchmark_timestamp(trace_conn) -> int:
        """获取基准时间戳（与HiSmartPerf工具保持一致）

        HiSmartPerf工具使用trace_range表的start_ts作为基准时间戳来计算相对时间。
        为了确保我们的分析结果与HiSmartPerf工具一致，我们也使用相同的基准点。

        Args:
            trace_conn: trace数据库连接

        Returns:
            int: 基准时间戳（纳秒）
        """
        try:
            cursor = trace_conn.cursor()
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

            # 如果frame_slice表中也没有数据，尝试从perf_sample表获取
            cursor.execute('SELECT MIN(timestamp_trace) FROM perf_sample WHERE timestamp_trace IS NOT NULL')
            result = cursor.fetchone()
            if result and result[0] is not None:
                return int(result[0])

            return 0
        except Exception as e:
            logging.warning('获取基准时间戳失败: %s', str(e))
            return 0

    @staticmethod
    def extract_pid_tid_info(trace_df: pd.DataFrame) -> tuple:
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
            unique_pids = set(trace_df['pid'].dropna().unique())
            unique_tids = set(trace_df['tid'].dropna().unique())

            # logging.debug("提取PID/TID信息: PIDs: %s, TIDs: %s", len(unique_pids), len(unique_tids))

            return list(unique_pids), list(unique_tids)

        except Exception as e:
            logging.error('提取PID/TID信息失败: %s', str(e))
            return [], []
