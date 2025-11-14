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

from .frame_constants import PERF_RECORDS_ERROR, PERF_RECORDS_WARNING


class FramePerfAccessor:
    """Perf数据库访问器 - 专门处理perf数据库的所有操作

    主要职责：
    1. 从perf数据库读取原始数据（性能采样、调用链、文件等）
    2. 执行SQL查询和数据过滤
    3. 标准化数据格式，处理NaN值
    4. 提供统一的perf数据访问接口

    注意：本类不负责缓存管理，只负责数据读取和标准化
    """

    def __init__(self, perf_conn):
        """初始化FramePerfAccessor

        Args:
            perf_conn: perf数据库连接
        """
        self.perf_conn = perf_conn

    # ==================== 公共数据访问方法 ====================

    def get_perf_samples(self) -> pd.DataFrame:
        """获取性能采样数据

        Returns:
            pd.DataFrame: 标准化的性能采样数据
        """
        start_time = time.time()

        # 先检查数据量
        try:
            count_query = 'SELECT COUNT(*) as total FROM perf_sample'
            total_records = pd.read_sql_query(count_query, self.perf_conn)['total'].iloc[0]

            if total_records > PERF_RECORDS_WARNING:  # 超过警告阈值
                logging.warning('性能数据量较大 (%d 条记录)，预计需要较长时间处理', total_records)
            elif total_records > PERF_RECORDS_ERROR:  # 超过错误阈值
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
            perf_df = pd.read_sql_query(query, self.perf_conn)

            elapsed_time = time.time() - start_time

            if elapsed_time > 30:  # 超过30秒
                logging.warning('性能数据加载耗时较长: %.2f秒', elapsed_time)

            # 标准化字段
            return self._standardize_perf_sample_data(perf_df)

        except Exception as e:
            logging.error('性能数据加载失败: %s', str(e))
            return pd.DataFrame()

    def get_callchain_cache(self) -> pd.DataFrame:
        """获取调用链缓存数据

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

        callchain_df = pd.read_sql_query(query, self.perf_conn)

        # 标准化字段
        return self._standardize_perf_callchain_data(callchain_df)

    def get_files_cache(self) -> pd.DataFrame:
        """获取文件缓存数据

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

        files_df = pd.read_sql_query(query, self.perf_conn)

        # 标准化字段
        return self._standardize_perf_files_data(files_df)

    def get_total_load_for_pids(self, app_pids: list[int]) -> int:
        """获取指定进程的总负载

        Args:
            app_pids: 应用进程ID列表

        Returns:
            int: 总负载值
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

        query = f"""
            SELECT SUM(event_count) as total_load
            FROM perf_sample
            WHERE thread_id IN ({','.join('?' * len(valid_pids))})
        """

        try:
            result = self.perf_conn.execute(query, valid_pids).fetchone()
            total_load = result[0] if result and result[0] else 0
            return int(total_load)
        except Exception as e:
            logging.error('获取总负载失败: %s', str(e))
            return 0

    # ==================== 数据标准化方法 ====================

    def _standardize_perf_sample_data(self, perf_df: pd.DataFrame) -> pd.DataFrame:
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

    def _standardize_perf_callchain_data(self, callchain_df: pd.DataFrame) -> pd.DataFrame:
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

    def _standardize_perf_files_data(self, files_df: pd.DataFrame) -> pd.DataFrame:
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
