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

from .frame_data_advanced_accessor import FrameDbAdvancedAccessor
from .frame_data_basic_accessor import FrameDbBasicAccessor


class FrameCacheManager:  # pylint: disable=too-many-public-methods
    """帧缓存管理器 - 负责缓存管理和数据访问委托

    主要职责：
    1. 管理各种数据缓存（帧数据、性能数据、调用链等）
    2. 提供统一的数据访问接口，委托给FrameDbBasicAccessor
    3. 实现缓存策略和缓存管理
    4. 提供帧负载分析和统计功能

    注意：本类不直接访问数据库，所有数据访问都委托给FrameDbBasicAccessor
    """

    # ==================== 缓存字典 ====================
    _callchain_cache = {}
    _files_cache = {}
    _pid_cache = {}
    _tid_cache = {}
    _process_cache = {}
    _frame_loads_cache = {}
    _frames_cache = {}
    _perf_samples_cache = {}
    _first_frame_timestamp_cache = {}  # 第一帧时间戳缓存

    # 缓存命中率统计
    _cache_hit_stats = {
        'frames': {'hits': 0, 'misses': 0},
        'perf_samples': {'hits': 0, 'misses': 0},
        'callchain': {'hits': 0, 'misses': 0},
        'files': {'hits': 0, 'misses': 0},
        'process': {'hits': 0, 'misses': 0},
        'first_frame_timestamp': {'hits': 0, 'misses': 0},
    }

    # ==================== 标准化缓存使用模式 ====================

    @staticmethod
    def ensure_data_cached(
        data_type: str, trace_conn=None, perf_conn=None, step_id: str = None, app_pids: list = None
    ) -> bool:
        """确保指定类型的数据已缓存，如果没有则获取并缓存

        标准化的缓存使用模式，供所有analyzer使用

        Args:
            data_type: 数据类型，支持以下类型：
                - 'frames': 帧数据
                - 'perf_samples': 性能采样数据
                - 'callchain': 调用链数据
                - 'files': 文件数据
                - 'process': 进程数据
                - 'thread': 线程数据
                - 'frame_loads': 帧负载数据
            trace_conn: trace数据库连接
            perf_conn: perf数据库连接
            step_id: 步骤ID
            app_pids: 应用进程ID列表
            **kwargs: 其他参数

        Returns:
            bool: 是否成功确保数据已缓存
        """
        # 统一使用step_id作为缓存键，如果没有step_id则使用连接对象ID
        cache_key = step_id if step_id else f'conn_{id(trace_conn or perf_conn)}'

        try:
            if data_type == 'frames':
                # 检查帧数据缓存
                if cache_key not in FrameCacheManager._frames_cache or FrameCacheManager._frames_cache[cache_key].empty:
                    if trace_conn is None:
                        raise ValueError('获取帧数据需要trace_conn')
                    FrameCacheManager.get_frames_data(trace_conn, step_id, app_pids)

            elif data_type == 'perf_samples':
                # 检查性能采样数据缓存
                if (
                    cache_key not in FrameCacheManager._perf_samples_cache
                    or FrameCacheManager._perf_samples_cache[cache_key].empty
                ):
                    if perf_conn is None:
                        raise ValueError('获取性能采样数据需要perf_conn')
                    FrameCacheManager.get_perf_samples(perf_conn, step_id)

            elif data_type == 'callchain':
                # 检查调用链数据缓存
                if (
                    cache_key not in FrameCacheManager._callchain_cache
                    or FrameCacheManager._callchain_cache[cache_key].empty
                ):
                    if perf_conn is None:
                        raise ValueError('获取调用链数据需要perf_conn')
                    FrameCacheManager.get_callchain_cache(perf_conn, step_id)

            elif data_type == 'files':
                # 检查文件数据缓存
                if cache_key not in FrameCacheManager._files_cache or FrameCacheManager._files_cache[cache_key].empty:
                    if perf_conn is None:
                        raise ValueError('获取文件数据需要perf_conn')
                    FrameCacheManager.get_files_cache(perf_conn, step_id)

            elif data_type == 'process':
                # 检查进程数据缓存
                if (
                    cache_key not in FrameCacheManager._process_cache
                    or FrameCacheManager._process_cache[cache_key].empty
                ):
                    if trace_conn is None:
                        raise ValueError('获取进程数据需要trace_conn')
                    FrameCacheManager.get_process_cache(trace_conn, step_id)

            elif data_type == 'frame_loads':
                # 检查帧负载数据缓存
                if cache_key not in FrameCacheManager._frame_loads_cache:
                    # 帧负载数据需要特殊处理，这里只是检查缓存键是否存在
                    FrameCacheManager._frame_loads_cache[cache_key] = []

            else:
                logging.warning('未知的数据类型: %s', data_type)
                return False

            # logging.debug("确保数据已缓存: type=%s, cache_key=%s", data_type, cache_key)
            return True

        except Exception as e:
            logging.error('确保数据缓存失败: type=%s, cache_key=%s, error=%s', data_type, cache_key, str(e))
            return False

    @staticmethod
    def preload_analyzer_data(trace_conn, perf_conn, step_id: str = None, app_pids: list = None) -> dict:
        """为analyzer预加载所有需要的数据

        Args:
            trace_conn: trace数据库连接
            perf_conn: perf数据库连接
            step_id: 步骤ID
            app_pids: 应用进程ID列表

        Returns:
            dict: 预加载结果统计
        """
        required_data_types = ['frames', 'perf_samples', 'callchain', 'files', 'process']
        success_count = 0
        failed_types = []

        for data_type in required_data_types:
            if FrameCacheManager.ensure_data_cached(data_type, trace_conn, perf_conn, step_id, app_pids):
                success_count += 1
            else:
                failed_types.append(data_type)

        return {
            'total_types': len(required_data_types),
            'success_count': success_count,
            'failed_count': len(failed_types),
            'failed_types': failed_types,
            'step_id': step_id,
        }

        # logging.info("预加载analyzer数据完成: %s", result)

    @staticmethod
    def get_cache_hit_stats() -> dict:
        """获取缓存命中率统计信息

        Returns:
            dict: 缓存命中率统计信息
        """
        stats = {}
        for data_type, hit_stats in FrameCacheManager._cache_hit_stats.items():
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

    @staticmethod
    def reset_cache_hit_stats() -> None:
        """重置缓存命中率统计"""
        for _, stats in FrameCacheManager._cache_hit_stats.items():
            stats['hits'] = 0
            stats['misses'] = 0
        # logging.info("已重置缓存命中率统计")

    # ==================== 缓存管理方法 ====================

    @staticmethod
    def clear_cache(step_id: str = None) -> None:
        """清除缓存

        Args:
            step_id: 步骤ID，如果指定则只清除该步骤的缓存，否则清除所有缓存
        """
        if step_id:
            # 清除指定步骤的缓存
            FrameCacheManager._frames_cache.pop(step_id, None)
            FrameCacheManager._perf_samples_cache.pop(step_id, None)
            FrameCacheManager._callchain_cache.pop(step_id, None)
            FrameCacheManager._files_cache.pop(step_id, None)
            FrameCacheManager._process_cache.pop(step_id, None)
            FrameCacheManager._pid_cache.pop(step_id, None)
            FrameCacheManager._tid_cache.pop(step_id, None)
            FrameCacheManager._frame_loads_cache.pop(step_id, None)
            FrameCacheManager._first_frame_timestamp_cache.pop(step_id, None)
            # logging.info("已清除步骤 %s 的缓存", step_id)
        else:
            # 清除所有缓存
            FrameCacheManager._frames_cache.clear()
            FrameCacheManager._perf_samples_cache.clear()
            FrameCacheManager._callchain_cache.clear()
            FrameCacheManager._files_cache.clear()
            FrameCacheManager._process_cache.clear()
            FrameCacheManager._pid_cache.clear()
            FrameCacheManager._tid_cache.clear()
            FrameCacheManager._frame_loads_cache.clear()
            FrameCacheManager._first_frame_timestamp_cache.clear()
            # 重置缓存命中率统计
            FrameCacheManager.reset_cache_hit_stats()
            # logging.info("已清除所有缓存")

    @staticmethod
    def get_cache_stats() -> dict:
        """获取缓存统计信息

        Returns:
            dict: 缓存统计信息
        """
        stats = {
            'frames_cache_size': len(FrameCacheManager._frames_cache),
            'perf_samples_cache_size': len(FrameCacheManager._perf_samples_cache),
            'callchain_cache_size': len(FrameCacheManager._callchain_cache),
            'files_cache_size': len(FrameCacheManager._files_cache),
            'process_cache_size': len(FrameCacheManager._process_cache),
            'pid_cache_size': len(FrameCacheManager._pid_cache),
            'tid_cache_size': len(FrameCacheManager._tid_cache),
            'frame_loads_cache_size': len(FrameCacheManager._frame_loads_cache),
            'first_frame_timestamp_cache_size': len(FrameCacheManager._first_frame_timestamp_cache),
            'cache_hit_stats': FrameCacheManager.get_cache_hit_stats(),
        }

        # 计算总内存使用量（估算）
        total_memory_estimate = 0
        for _cache_name, cache_dict in [
            ('frames', FrameCacheManager._frames_cache),
            ('perf_samples', FrameCacheManager._perf_samples_cache),
            ('callchain', FrameCacheManager._callchain_cache),
            ('files', FrameCacheManager._files_cache),
            ('process', FrameCacheManager._process_cache),
        ]:
            for _key, df in cache_dict.items():
                if not df.empty:
                    # 估算DataFrame内存使用量
                    memory_estimate = int(df.memory_usage(deep=True).sum())  # 确保返回Python原生int类型
                    total_memory_estimate += memory_estimate

        stats['total_memory_estimate_bytes'] = total_memory_estimate
        stats['total_memory_estimate_mb'] = round(total_memory_estimate / (1024 * 1024), 2)

        return stats

    @staticmethod
    def preload_all_caches(trace_conn, perf_conn, step_id: str = None, app_pids: list = None) -> dict:
        """预加载所有缓存

        Args:
            trace_conn: trace数据库连接
            perf_conn: perf数据库连接
            step_id: 步骤ID
            app_pids: 应用进程ID列表

        Returns:
            dict: 预加载结果统计
        """
        if not step_id:
            logging.warning('预加载缓存需要指定step_id')
            return {}

        # logging.info("开始预加载步骤 %s 的所有缓存", step_id)

        preload_stats = {}

        try:
            # 预加载帧数据
            frames_df = FrameCacheManager.get_frames_data(trace_conn, step_id, app_pids)
            preload_stats['frames_count'] = len(frames_df)

            # 预加载性能采样数据
            perf_df = FrameCacheManager.get_perf_samples(perf_conn, step_id)
            preload_stats['perf_samples_count'] = len(perf_df)

            # 预加载调用链数据
            callchain_df = FrameCacheManager.get_callchain_cache(perf_conn, step_id)
            preload_stats['callchain_count'] = len(callchain_df)

            # 预加载文件数据
            files_df = FrameCacheManager.get_files_cache(perf_conn, step_id)
            preload_stats['files_count'] = len(files_df)

            # 预加载进程数据
            process_df = FrameCacheManager.get_process_cache(trace_conn, step_id)
            preload_stats['process_count'] = len(process_df)

            # logging.info("步骤 %s 缓存预加载完成: %s", step_id, preload_stats)

        except Exception as e:
            logging.error('预加载缓存失败: %s', str(e))
            preload_stats['error'] = str(e)

        return preload_stats

    @staticmethod
    def check_cache_status(step_id: str = None) -> dict:
        """检查缓存状态

        Args:
            step_id: 步骤ID，如果指定则检查该步骤的缓存状态，否则检查所有缓存状态

        Returns:
            dict: 缓存状态信息
        """
        if step_id:
            # 检查指定步骤的缓存状态
            status = {
                'step_id': step_id,
                'frames_cached': step_id in FrameCacheManager._frames_cache,
                'perf_samples_cached': step_id in FrameCacheManager._perf_samples_cache,
                'callchain_cached': step_id in FrameCacheManager._callchain_cache,
                'files_cached': step_id in FrameCacheManager._files_cache,
                'process_cached': step_id in FrameCacheManager._process_cache,
                'pid_cached': step_id in FrameCacheManager._pid_cache,
                'tid_cached': step_id in FrameCacheManager._tid_cache,
                'frame_loads_cached': step_id in FrameCacheManager._frame_loads_cache,
            }

            # 添加数据量信息
            if status['frames_cached']:
                status['frames_count'] = len(FrameCacheManager._frames_cache[step_id])
            if status['perf_samples_cached']:
                status['perf_samples_count'] = len(FrameCacheManager._perf_samples_cache[step_id])
            if status['callchain_cached']:
                status['callchain_count'] = len(FrameCacheManager._callchain_cache[step_id])
            if status['files_cached']:
                status['files_count'] = len(FrameCacheManager._files_cache[step_id])
            if status['process_cached']:
                status['process_count'] = len(FrameCacheManager._process_cache[step_id])
            if status['pid_cached']:
                status['pid_count'] = len(FrameCacheManager._pid_cache[step_id])
            if status['tid_cached']:
                status['tid_count'] = len(FrameCacheManager._tid_cache[step_id])
            if status['frame_loads_cached']:
                status['frame_loads_count'] = len(FrameCacheManager._frame_loads_cache[step_id])

        else:
            # 检查所有缓存状态
            status = {
                'total_cached_steps': len(FrameCacheManager._frames_cache),
                'cache_stats': FrameCacheManager.get_cache_stats(),
            }

        return status

    # ==================== 数据访问委托方法 ====================

    @staticmethod
    def get_first_frame_timestamp(trace_conn, step_id: str = None) -> int:
        """获取第一帧时间戳（带缓存）

        Args:
            trace_conn: trace数据库连接
            step_id: 步骤ID

        Returns:
            int: 第一帧的时间戳（纳秒）
        """
        # 统一使用step_id作为缓存键，如果没有step_id则使用连接对象ID
        cache_key = step_id if step_id else f'conn_{id(trace_conn)}'

        if cache_key in FrameCacheManager._first_frame_timestamp_cache:
            # 缓存命中
            FrameCacheManager._cache_hit_stats['first_frame_timestamp']['hits'] += 1
            return FrameCacheManager._first_frame_timestamp_cache[cache_key]

        # 缓存未命中
        FrameCacheManager._cache_hit_stats['first_frame_timestamp']['misses'] += 1

        # 优先从数据访问层获取基准时间戳（与HiSmartPerf工具保持一致）
        first_frame_timestamp = 0
        if trace_conn:
            try:
                # 委托给数据访问层获取基准时间戳
                first_frame_timestamp = FrameDbBasicAccessor.get_benchmark_timestamp(trace_conn)
            except Exception as e:
                logging.warning('获取trace开始时间失败，使用备选方案: %s', str(e))
                # 备选方案：从缓存中获取所有帧数据并计算最小时间戳
                frames_df = FrameCacheManager.get_frames_data(trace_conn, step_id)
                if not frames_df.empty:
                    first_frame_timestamp = int(frames_df['ts'].min())
        else:
            # 如果没有数据库连接，从缓存中获取
            frames_df = FrameCacheManager.get_frames_data(None, step_id)
            if not frames_df.empty:
                first_frame_timestamp = int(frames_df['ts'].min())

        # 缓存结果
        FrameCacheManager._first_frame_timestamp_cache[cache_key] = first_frame_timestamp
        return first_frame_timestamp

    @staticmethod
    def get_frames_data(trace_conn, step_id: str = None, app_pids: list = None) -> pd.DataFrame:
        """获取帧数据（带缓存）"""
        # 统一使用step_id作为缓存键，如果没有step_id则使用连接对象ID
        cache_key = step_id if step_id else f'conn_{id(trace_conn)}'

        if cache_key in FrameCacheManager._frames_cache and not FrameCacheManager._frames_cache[cache_key].empty:
            # 缓存命中
            FrameCacheManager._cache_hit_stats['frames']['hits'] += 1
            frames_df = FrameCacheManager._frames_cache[cache_key]
            if app_pids is None:
                return frames_df
            # 确保app_pids是有效的列表，并且过滤掉NaN值
            if isinstance(app_pids, (list, tuple)) and len(app_pids) > 0:
                # 过滤掉NaN值，确保只包含有效的数字
                valid_pids = [pid for pid in app_pids if pd.notna(pid) and isinstance(pid, (int, float))]
                if valid_pids:
                    return frames_df[frames_df['pid'].isin(valid_pids)]
            return frames_df

        # 缓存未命中
        FrameCacheManager._cache_hit_stats['frames']['misses'] += 1
        frames_df = FrameDbBasicAccessor.get_frames_data(trace_conn, app_pids)
        FrameCacheManager._frames_cache[cache_key] = frames_df

        # 更新PID和TID缓存（使用相同的缓存键）
        if step_id:
            pids, tids = FrameDbBasicAccessor.extract_pid_tid_info(frames_df)
            FrameCacheManager._pid_cache[cache_key] = pids
            FrameCacheManager._tid_cache[cache_key] = tids

        return frames_df

    @staticmethod
    def get_frames_by_filter(
        trace_conn, flag: int = None, frame_type: int = None, app_pids: list = None
    ) -> pd.DataFrame:
        """根据条件过滤帧数据"""
        return FrameDbBasicAccessor.get_frames_by_filter(trace_conn, flag, frame_type, app_pids)

    @staticmethod
    def get_perf_samples(perf_conn, step_id: str = None) -> pd.DataFrame:
        """获取性能采样数据（带缓存）"""
        # 统一使用step_id作为缓存键，如果没有step_id则使用连接对象ID
        cache_key = step_id if step_id else f'conn_{id(perf_conn)}'

        if (
            cache_key in FrameCacheManager._perf_samples_cache
            and not FrameCacheManager._perf_samples_cache[cache_key].empty
        ):
            # 缓存命中
            FrameCacheManager._cache_hit_stats['perf_samples']['hits'] += 1
            return FrameCacheManager._perf_samples_cache[cache_key]

        # 缓存未命中
        FrameCacheManager._cache_hit_stats['perf_samples']['misses'] += 1
        perf_df = FrameDbBasicAccessor.get_perf_samples(perf_conn)
        FrameCacheManager._perf_samples_cache[cache_key] = perf_df
        return perf_df

    @staticmethod
    def get_perf_samples_by_thread(perf_conn) -> dict:
        """按线程分组获取性能采样数据"""
        return FrameDbBasicAccessor.get_perf_samples_by_thread(perf_conn)

    @staticmethod
    def get_callchain_cache(perf_conn, step_id: str = None) -> pd.DataFrame:
        """获取调用链缓存数据（带缓存）"""
        # 统一使用step_id作为缓存键，如果没有step_id则使用连接对象ID
        cache_key = step_id if step_id else f'conn_{id(perf_conn)}'

        if cache_key in FrameCacheManager._callchain_cache and not FrameCacheManager._callchain_cache[cache_key].empty:
            # 缓存命中
            FrameCacheManager._cache_hit_stats['callchain']['hits'] += 1
            return FrameCacheManager._callchain_cache[cache_key]

        # 缓存未命中
        FrameCacheManager._cache_hit_stats['callchain']['misses'] += 1
        callchain_df = FrameDbBasicAccessor.get_callchain_cache(perf_conn)
        FrameCacheManager._callchain_cache[cache_key] = callchain_df
        return callchain_df

    @staticmethod
    def get_files_cache(perf_conn, step_id: str = None) -> pd.DataFrame:
        """获取文件缓存数据（带缓存）"""
        # 统一使用step_id作为缓存键，如果没有step_id则使用连接对象ID
        cache_key = step_id if step_id else f'conn_{id(perf_conn)}'

        if cache_key in FrameCacheManager._files_cache and not FrameCacheManager._files_cache[cache_key].empty:
            # 缓存命中
            FrameCacheManager._cache_hit_stats['files']['hits'] += 1
            return FrameCacheManager._files_cache[cache_key]

        # 缓存未命中
        FrameCacheManager._cache_hit_stats['files']['misses'] += 1
        files_df = FrameDbBasicAccessor.get_files_cache(perf_conn)
        FrameCacheManager._files_cache[cache_key] = files_df
        return files_df

    @staticmethod
    def get_process_cache(trace_conn, step_id: str = None) -> pd.DataFrame:
        """获取进程缓存数据（带缓存）"""
        # 统一使用step_id作为缓存键，如果没有step_id则使用连接对象ID
        cache_key = step_id if step_id else f'conn_{id(trace_conn)}'

        if cache_key in FrameCacheManager._process_cache and not FrameCacheManager._process_cache[cache_key].empty:
            # 缓存命中
            FrameCacheManager._cache_hit_stats['process']['hits'] += 1
            return FrameCacheManager._process_cache[cache_key]

        # 缓存未命中
        FrameCacheManager._cache_hit_stats['process']['misses'] += 1
        process_df = FrameDbBasicAccessor.get_process_cache(trace_conn)
        FrameCacheManager._process_cache[cache_key] = process_df
        return process_df

    @staticmethod
    def get_process_cache_by_key(cache_key: str) -> pd.DataFrame:
        """通过缓存key获取process缓存数据"""
        return FrameCacheManager._process_cache.get(cache_key, pd.DataFrame())

    @staticmethod
    def get_callstack_data(trace_conn, name_pattern: str = None) -> pd.DataFrame:
        """获取调用栈数据"""
        return FrameDbBasicAccessor.get_callstack_data(trace_conn, name_pattern)

    @staticmethod
    def get_thread_data(trace_conn, is_main_thread: bool = None) -> pd.DataFrame:
        """获取线程数据"""
        return FrameDbBasicAccessor.get_thread_data(trace_conn, is_main_thread)

    @staticmethod
    def get_process_data(trace_conn, process_name_pattern: str = None) -> pd.DataFrame:
        """获取进程数据"""
        return FrameDbBasicAccessor.get_process_data(trace_conn, process_name_pattern)

    @staticmethod
    def get_symbol_data(perf_conn, symbol_pattern: str = None) -> pd.DataFrame:
        """获取符号数据"""
        return FrameDbBasicAccessor.get_symbol_data(perf_conn, symbol_pattern)

    # ==================== 复杂联合查询委托方法 ====================

    @staticmethod
    def get_empty_frames_with_details(trace_conn, app_pids: list[int]) -> pd.DataFrame:
        """获取空帧详细信息（包含进程、线程、调用栈信息）"""
        return FrameDbAdvancedAccessor.get_empty_frames_with_details(trace_conn, app_pids)

    @staticmethod
    def get_stuttered_frames_with_context(trace_conn) -> pd.DataFrame:
        """获取卡顿帧上下文信息"""
        return FrameDbAdvancedAccessor.get_stuttered_frames_with_context(trace_conn)

    @staticmethod
    def get_frame_load_analysis_data(trace_conn, perf_conn, app_pids: list[int]) -> dict[str, pd.DataFrame]:
        """获取帧负载分析所需的完整数据"""
        return FrameDbAdvancedAccessor.get_frame_load_analysis_data(trace_conn, perf_conn, app_pids)

    @staticmethod
    def get_frame_statistics_by_process(trace_conn, app_pids: list[int]) -> pd.DataFrame:
        """按进程获取帧统计信息"""
        return FrameDbAdvancedAccessor.get_frame_statistics_by_process(trace_conn, app_pids)

    @staticmethod
    def get_frame_timeline_analysis(trace_conn, app_pids: list[int], time_window_ms: int = 1000) -> pd.DataFrame:
        """获取帧时间线分析数据"""
        return FrameDbAdvancedAccessor.get_frame_timeline_analysis(trace_conn, app_pids, time_window_ms)

    @staticmethod
    def get_perf_samples_with_callchain(perf_conn) -> pd.DataFrame:
        """获取带调用链的性能采样数据"""
        return FrameDbAdvancedAccessor.get_perf_samples_with_callchain(perf_conn)

    @staticmethod
    def get_thread_performance_analysis(trace_conn, app_pids: list[int]) -> pd.DataFrame:
        """获取线程性能分析数据"""
        return FrameDbAdvancedAccessor.get_thread_performance_analysis(trace_conn, app_pids)

    # ==================== 帧负载分析方法 ====================

    @staticmethod
    def add_frame_load(step_id: str, frame_load_data: dict) -> None:
        """添加帧负载数据到缓存

        Args:
            step_id: 步骤ID
            frame_load_data: 帧负载数据
        """
        if step_id not in FrameCacheManager._frame_loads_cache:
            FrameCacheManager._frame_loads_cache[step_id] = []

        # 清理数据中的NaN值
        cleaned_data = FrameCacheManager._clean_frame_data(frame_load_data)

        # 按帧负载值排序插入
        frame_load = cleaned_data.get('frame_load', 0)
        insert_pos = FrameCacheManager._find_insert_position(FrameCacheManager._frame_loads_cache[step_id], frame_load)

        FrameCacheManager._frame_loads_cache[step_id].insert(insert_pos, cleaned_data)

        # logging.debug("已添加帧负载数据到步骤 %s，当前缓存大小: %d",
        #              step_id, len(FrameCacheManager._frame_loads_cache[step_id]))

    @staticmethod
    def get_frame_loads(step_id: str) -> list:
        """获取指定步骤的所有帧负载数据

        Args:
            step_id: 步骤ID

        Returns:
            list: 帧负载数据列表
        """
        return FrameCacheManager._frame_loads_cache.get(step_id, [])

    @staticmethod
    def get_top_frame_loads(step_id: str, top_count: int = 10) -> list:
        """获取指定步骤的前N个最高帧负载数据

        Args:
            step_id: 步骤ID
            top_count: 返回的帧负载数量

        Returns:
            list: 前N个最高帧负载数据
        """
        frame_loads = FrameCacheManager.get_frame_loads(step_id)
        return frame_loads[:top_count]

    @staticmethod
    def get_frame_load_statistics(step_id: str) -> dict:
        """获取帧负载统计信息

        Args:
            step_id: 步骤ID

        Returns:
            dict: 帧负载统计信息
        """
        frame_loads = FrameCacheManager.get_frame_loads(step_id)

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
        total_load = int(sum(frame_load_values))  # 确保返回Python原生int类型

        return {
            'total_frames': len(frame_loads),
            'total_load': total_load,
            'average_load': float(total_load / len(frame_load_values)) if frame_load_values else 0.0,
            # 确保返回Python原生float类型
            'max_load': int(max(frame_load_values)) if frame_load_values else 0,  # 确保返回Python原生int类型
            'min_load': int(min(frame_load_values)) if frame_load_values else 0,  # 确保返回Python原生int类型
            'high_load_frames': len([x for x in frame_load_values if x > 80]),  # 高负载帧（>80%）
        }

    @staticmethod
    def analyze_frame_callchains(step_id: str, frame_ids: list, perf_conn) -> bool:
        """分析指定帧的调用链

        Args:
            step_id: 步骤ID
            frame_ids: 要分析的帧ID列表
            perf_conn: perf数据库连接

        Returns:
            bool: 分析是否成功
        """
        try:
            # 获取性能采样数据
            perf_df = FrameCacheManager.get_perf_samples(perf_conn, step_id)

            if perf_df.empty:
                logging.warning('步骤 %s 没有性能采样数据', step_id)
                return False

            # 分析缺失的调用链
            FrameCacheManager._analyze_missing_callchains(step_id, frame_ids, perf_conn)

            # logging.info("步骤 %s 的帧调用链分析完成", step_id)
            return True

        except Exception as e:
            logging.error('分析帧调用链失败: %s', str(e))
            return False

    @staticmethod
    def analyze_top_frame_callchains(step_id: str, top_count: int = 10, perf_conn=None) -> bool:
        """分析前N个最高帧负载的调用链

        Args:
            step_id: 步骤ID
            top_count: 分析的帧数量
            perf_conn: perf数据库连接

        Returns:
            bool: 分析是否成功
        """
        try:
            # 获取前N个最高帧负载
            top_frames = FrameCacheManager.get_top_frame_loads(step_id, top_count)

            if not top_frames:
                logging.warning('步骤 %s 没有帧负载数据', step_id)
                return False

            # 提取帧ID
            frame_ids = [frame.get('frame_id') for frame in top_frames if frame.get('frame_id')]

            if not frame_ids:
                logging.warning('步骤 %s 的帧负载数据中没有有效的帧ID', step_id)
                return False

            # 分析调用链
            return FrameCacheManager.analyze_frame_callchains(step_id, frame_ids, perf_conn)

        except Exception as e:
            logging.error('分析前N个帧调用链失败: %s', str(e))
            return False

    # ==================== 工具方法 ====================

    @staticmethod
    def _find_insert_position(frame_list: list, frame_load: int) -> int:
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

    @staticmethod
    def _clean_frame_data(frame_data: dict) -> dict:  # pylint: disable=duplicate-code
        """清理帧数据中的NaN值，确保JSON序列化安全"""

        cleaned_data = {}
        for key, value in frame_data.items():
            if key in ['frame_samples', 'index']:
                # 跳过frame_samples和index字段，它们会在后续处理中被移除
                continue

            cleaned_data[key] = FrameCacheManager._clean_single_value(value)

        return cleaned_data

    @staticmethod
    def _clean_single_value(value) -> any:
        """清理单个值，确保JSON序列化安全"""
        # 首先检查是否是numpy/pandas类型
        if hasattr(value, 'dtype') and hasattr(value, 'item'):
            return FrameCacheManager._clean_numpy_value(value)

        # 普通类型，安全地检查NaN
        return FrameCacheManager._clean_regular_value(value)

    @staticmethod
    def _clean_numpy_value(value) -> any:
        """清理numpy/pandas类型的值"""
        try:
            if hasattr(pd.isna(value), 'any'):
                # 如果是数组，检查是否有NaN
                if pd.isna(value).any():
                    return 0
                return value.item()

            # 如果是标量
            if pd.isna(value):
                return 0
            return value.item()
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _clean_regular_value(value) -> any:
        """清理普通类型的值"""
        try:
            if pd.isna(value):
                if isinstance(value, (int, float)):
                    return 0
                return None
            return value
        except (ValueError, TypeError):
            # 如果pd.isna()失败，直接使用原值
            return value

    @staticmethod
    def _analyze_missing_callchains(step_id: str, frame_ids: list, perf_conn) -> None:  # pylint: disable=unused-argument
        """分析缺失的调用链

        Args:
            step_id: 步骤ID
            frame_ids: 帧ID列表
            perf_conn: perf数据库连接
        """
        try:
            # 获取性能采样数据
            perf_df = FrameCacheManager.get_perf_samples(perf_conn, step_id)

            if perf_df.empty:
                logging.warning('步骤 %s 没有性能采样数据，无法分析调用链', step_id)
                return

            # 统计缺失的调用链
            missing_callchains = perf_df[perf_df['callchain_id'].isna() | (perf_df['callchain_id'] == 0)]

            if not missing_callchains.empty:
                logging.warning('步骤 %s 发现 %d 个缺失调用链的采样点', step_id, len(missing_callchains))

                # 按线程分组统计（已注释，避免未使用变量警告）
                # _thread_missing = missing_callchains.groupby('thread_id').size()
                # logging.info("按线程统计缺失调用链: %s", thread_missing.to_dict())

                # 按CPU分组统计（已注释，避免未使用变量警告）
                # _cpu_missing = missing_callchains.groupby('cpu_id').size()
                # logging.info("按CPU统计缺失调用链: %s", cpu_missing.to_dict())

            else:
                # logging.info("步骤 %s 所有采样点都有调用链信息", step_id)
                pass

        except Exception as e:
            logging.error('分析缺失调用链失败: %s', str(e))

    # ==================== PID/TID缓存管理方法 ====================

    @staticmethod
    def get_pid_cache(trace_conn, step_id: str = None) -> list:
        """获取PID缓存数据

        Args:
            trace_conn: trace数据库连接
            step_id: 步骤ID，用作缓存key

        Returns:
            list: PID列表
        """
        cache_key = step_id if step_id else f'conn_{id(trace_conn)}'
        return FrameCacheManager._pid_cache.get(cache_key, [])

    @staticmethod
    def get_tid_cache(trace_conn, step_id: str = None) -> list:
        """获取TID缓存数据

        Args:
            trace_conn: trace数据库连接
            step_id: 步骤ID，用作缓存key

        Returns:
            list: TID列表
        """
        cache_key = step_id if step_id else f'conn_{id(trace_conn)}'
        return FrameCacheManager._tid_cache.get(cache_key, [])

    @staticmethod
    def update_pid_tid_cache(step_id: str, trace_df: pd.DataFrame) -> None:
        """根据trace_df中的数据更新PID和TID缓存

        Args:
            step_id: 步骤ID
            trace_df: 包含pid和tid信息的DataFrame
        """
        pids, tids = FrameDbBasicAccessor.extract_pid_tid_info(trace_df)
        FrameCacheManager._pid_cache[step_id] = pids
        FrameCacheManager._tid_cache[step_id] = tids
