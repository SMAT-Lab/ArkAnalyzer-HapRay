# pylint: disable=R0917
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
from typing import Any

import pandas as pd

from .frame_core_cache_manager import FrameCacheManager


class FrameLoadCalculator:
    """帧负载计算器

    负责计算帧的负载和调用链分析，包括：
    1. 帧负载计算
    2. 调用链分析
    3. 样本调用链构建
    4. VSync过滤
    """

    def __init__(self, debug_vsync_enabled: bool = False):
        """
        初始化帧负载计算器

        Args:
            debug_vsync_enabled: VSync调试开关，True时正常判断，False时永远不触发VSync条件
        """
        self.debug_vsync_enabled = debug_vsync_enabled

    def analyze_perf_callchain(
        self,
        perf_conn,
        callchain_id: int,
        callchain_cache: pd.DataFrame = None,
        files_cache: pd.DataFrame = None,
        step_id: str = None,
    ) -> list[dict[str, Any]]:
        """分析perf样本的调用链信息

        Args:
            perf_conn: perf数据库连接
            callchain_id: 调用链ID
            callchain_cache: 缓存的callchain数据
            files_cache: 缓存的文件数据
            step_id: 步骤ID，用于缓存key

        Returns:
            List[Dict]: 调用链信息列表，每个元素包含symbol和path信息
        """
        callchain_start_time = time.time()

        try:
            # 如果没有缓存，先获取缓存
            cache_check_start = time.time()
            if callchain_cache is None or callchain_cache.empty:
                # logging.info("callchain_cache为空，从数据库获取")
                callchain_cache = FrameCacheManager.get_callchain_cache(perf_conn, step_id)
            if files_cache is None or files_cache.empty:
                # logging.info("files_cache为空，从数据库获取")
                files_cache = FrameCacheManager.get_files_cache(perf_conn, step_id)
            cache_check_time = time.time() - cache_check_start

            # 确定缓存key
            key_start = time.time()
            cache_key = step_id if step_id else str(perf_conn)
            # logging.info("分析调用链: callchain_id=%s, cache_key=%s", callchain_id, cache_key)
            key_time = time.time() - key_start

            # 检查缓存是否为空
            cache_validate_start = time.time()
            if (
                cache_key not in FrameCacheManager._callchain_cache  # pylint: disable=protected-access
                or FrameCacheManager._callchain_cache[cache_key].empty  # pylint: disable=protected-access
                or cache_key not in FrameCacheManager._files_cache  # pylint: disable=protected-access
                or FrameCacheManager._files_cache[cache_key].empty
            ):  # pylint: disable=protected-access
                logging.warning('缓存数据为空，无法分析调用链: cache_key=%s', cache_key)
                return []
            cache_validate_time = time.time() - cache_validate_start

            # 从缓存中获取callchain数据
            callchain_lookup_start = time.time()
            callchain_cache = FrameCacheManager._callchain_cache[cache_key]  # pylint: disable=protected-access
            callchain_records = (
                callchain_cache[callchain_cache['callchain_id'] == callchain_id]  # pylint: disable=protected-access
            )
            callchain_lookup_time = time.time() - callchain_lookup_start

            # logging.info("找到callchain记录数: %s", len(callchain_records))

            if callchain_records.empty:
                # logging.info("未找到callchain_id=%s的记录", callchain_id)
                total_time = time.time() - callchain_start_time
                if total_time > 0.01:  # 只记录耗时超过0.01秒的调用链分析
                    logging.debug(
                        '[%s] 调用链分析耗时: %.6f秒 (无记录), '
                        '缓存检查%.6f秒, 键生成%.6f秒, '
                        '缓存验证%.6f秒, 记录查找%.6f秒',
                        step_id,
                        total_time,
                        cache_check_time,
                        key_time,
                        cache_validate_time,
                        callchain_lookup_time,
                    )
                return []

            # 构建调用链信息
            build_start = time.time()
            callchain_info = []
            file_lookup_total = 0

            for _, record in callchain_records.iterrows():
                # 从缓存中获取文件信息
                file_start = time.time()
                files_cache = FrameCacheManager._files_cache[cache_key]  # pylint: disable=protected-access
                file_mask = (files_cache['file_id'] == record['file_id']) & (
                    files_cache['serial_id'] == record['symbol_id']
                )
                file_info = files_cache[file_mask]  # pylint: disable=protected-access
                file_time = time.time() - file_start
                file_lookup_total += file_time

                symbol = file_info['symbol'].iloc[0] if not file_info.empty else 'unknown'
                path = file_info['path'].iloc[0] if not file_info.empty else 'unknown'

                callchain_info.append(
                    {
                        'depth': int(record['depth']),
                        'file_id': int(record['file_id']),
                        'path': str(path),
                        'symbol_id': int(record['symbol_id']),
                        'symbol': str(symbol),
                    }
                )

            build_time = time.time() - build_start

            # 总耗时统计
            total_time = time.time() - callchain_start_time

            # 只记录耗时较长的调用链分析（超过0.01秒）
            if total_time > 0.01:
                logging.debug(
                    '[%s] 调用链分析耗时: %.6f秒, callchain_id: %s, 记录数: %d',
                    step_id,
                    total_time,
                    callchain_id,
                    len(callchain_records),
                )
                logging.debug(
                    '[%s] 各阶段耗时: '
                    '缓存检查%.6f秒, 键生成%.6f秒, '
                    '缓存验证%.6f秒, 记录查找%.6f秒, '
                    '构建%.6f秒, 文件查找%.6f秒',
                    step_id,
                    cache_check_time,
                    key_time,
                    cache_validate_time,
                    callchain_lookup_time,
                    build_time,
                    file_lookup_total,
                )

            # logging.info("构建的调用链信息: 长度=%s", len(callchain_info))
            return callchain_info

        except Exception as e:
            logging.error('分析调用链失败: %s', str(e))
            return []

    def analyze_single_frame(self, frame, perf_df, perf_conn, step_id):
        """分析单个帧的负载和调用链，返回frame_load和sample_callchains

        这是从原始FrameAnalyzer.analyze_single_frame方法迁移的代码
        """
        frame_start_time = time.time()

        # 在函数内部获取缓存
        cache_start = time.time()
        callchain_cache = FrameCacheManager.get_callchain_cache(perf_conn, step_id)
        files_cache = FrameCacheManager.get_files_cache(perf_conn, step_id)
        cache_time = time.time() - cache_start

        frame_load = 0
        sample_callchains = []

        # 计算帧的开始和结束时间
        time_calc_start = time.time()
        frame_start_time_ts = frame.get('start_time', frame.get('ts', 0))
        frame_end_time_ts = frame.get('end_time', frame.get('ts', 0) + frame.get('dur', 0))
        time_calc_time = time.time() - time_calc_start

        # 数据过滤
        filter_start = time.time()
        mask = (
            (perf_df['timestamp_trace'] >= frame_start_time_ts)
            & (perf_df['timestamp_trace'] <= frame_end_time_ts)
            & (perf_df['thread_id'] == frame['tid'])
        )
        frame_samples = perf_df[mask]
        filter_time = time.time() - filter_start

        if frame_samples.empty:
            # logging.info("analyze_single_frame: 帧时间窗口内无样本, ts=%s, 时间窗口=[%s, %s], tid=%s",
            #              frame.get('ts'), frame_start_time_ts, frame_end_time_ts, frame.get('tid'))
            total_time = time.time() - frame_start_time
            if total_time > 0.1:  # 只记录耗时超过0.1秒的帧
                logging.debug(
                    '[%s] 空帧分析耗时: %.6f秒 (无样本), 缓存%.6f秒, 时间计算%.6f秒, 过滤%.6f秒',
                    step_id,
                    total_time,
                    cache_time,
                    time_calc_time,
                    filter_time,
                )
            return frame_load, sample_callchains

        # logging.info("analyze_single_frame: 找到样本, ts=%s, 时间窗口=[%s, %s], tid=%s, 样本数=%s",
        #              frame.get('ts'), frame_start_time_ts, frame_end_time_ts, frame.get('tid'), len(frame_samples))

        # 样本分析
        sample_analysis_start = time.time()
        callchain_analysis_total = 0
        vsync_filter_total = 0
        sample_count = 0

        for _, sample in frame_samples.iterrows():
            sample_count += 1
            if not pd.notna(sample['callchain_id']):
                continue

            try:
                # 调用链分析
                callchain_start = time.time()
                callchain_info = self.analyze_perf_callchain(
                    perf_conn, int(sample['callchain_id']), callchain_cache, files_cache, step_id
                )
                callchain_time = time.time() - callchain_start
                callchain_analysis_total += callchain_time

                if callchain_info and len(callchain_info) > 0:
                    # VSync过滤
                    vsync_start = time.time()
                    is_vsync_chain = False
                    for i in range(len(callchain_info) - 1):
                        current_symbol = callchain_info[i]['symbol']
                        next_symbol = callchain_info[i + 1]['symbol']
                        event_count = sample['event_count']

                        if not current_symbol or not next_symbol:
                            continue

                        if self.debug_vsync_enabled and (
                            'OHOS::Rosen::VSyncCallBackListener::OnReadable' in current_symbol
                            and 'OHOS::Rosen::VSyncCallBackListener::HandleVsyncCallbacks' in next_symbol
                            and event_count < 2000000
                        ):
                            is_vsync_chain = True
                            break
                    vsync_time = time.time() - vsync_start
                    vsync_filter_total += vsync_time

                    if not is_vsync_chain:
                        frame_load += sample['event_count']
                        try:
                            sample_load_percentage = (sample['event_count'] / frame_load) * 100
                            sample_callchains.append(
                                {
                                    'timestamp': int(sample['timestamp_trace']),
                                    'event_count': int(sample['event_count']),
                                    'load_percentage': float(sample_load_percentage),
                                    'callchain': callchain_info,
                                }
                            )
                        except Exception as e:
                            logging.error(
                                '处理样本时出错: %s, sample: %s, frame_load: %s', str(e), sample.to_dict(), frame_load
                            )
                            continue

            except Exception as e:
                logging.error('分析调用链时出错: %s', str(e))
                continue

        sample_analysis_time = time.time() - sample_analysis_start

        # 保存帧负载数据到缓存
        cache_save_start = time.time()
        if step_id:
            frame_load_data = {
                'ts': frame.get('ts', frame.get('start_time', 0)),
                'dur': frame.get('dur', frame.get('end_time', 0) - frame.get('start_time', 0)),
                'frame_load': frame_load,
                'thread_id': frame.get('tid'),
                'thread_name': frame.get('thread_name', 'unknown'),
                'process_name': frame.get('process_name', 'unknown'),
                'type': frame.get('type', 0),
                'vsync': frame.get('vsync', 'unknown'),
                'flag': frame.get('flag'),
                'sample_callchains': sample_callchains,
            }
            FrameCacheManager.add_frame_load(step_id, frame_load_data)
        cache_save_time = time.time() - cache_save_start

        # 总耗时统计
        total_time = time.time() - frame_start_time

        # 只记录耗时较长的帧分析（超过0.1秒）
        if total_time > 0.1:
            logging.debug(
                '[%s] 单帧分析耗时: %.6f秒, 样本数: %d, 有效样本: %d',
                step_id,
                total_time,
                len(frame_samples),
                sample_count,
            )
            logging.debug(
                '[%s] 各阶段耗时: 缓存获取%.6f秒, 时间计算%.6f秒, 数据过滤%.6f秒, 样本分析%.6f秒, 缓存保存%.6f秒',
                step_id,
                cache_time,
                time_calc_time,
                filter_time,
                sample_analysis_time,
                cache_save_time,
            )
            logging.debug(
                '[%s] 样本分析详情: 调用链分析%.6f秒, VSync过滤%.6f秒',
                step_id,
                callchain_analysis_total,
                vsync_filter_total,
            )

        return frame_load, sample_callchains

    def calculate_frame_load(
        self,
        frame: dict[str, Any],
        perf_df: pd.DataFrame,
        perf_conn,
        step_id: str = None,
        callchain_cache: pd.DataFrame = None,
        files_cache: pd.DataFrame = None,
        include_vsync_filter: bool = True,
    ) -> tuple[int, list[dict[str, Any]]]:
        """计算单个帧的负载和调用链

        Args:
            frame: 帧数据字典，必须包含 'start_time', 'end_time', 'tid' 字段
            perf_df: perf样本DataFrame，包含 timestamp_trace, thread_id, event_count, callchain_id
            perf_conn: perf数据库连接
            step_id: 步骤ID，用于缓存
            callchain_cache: 缓存的callchain数据
            files_cache: 缓存的文件数据
            include_vsync_filter: 是否包含VSync过滤

        Returns:
            Tuple[int, List[Dict]]: (frame_load, sample_callchains)
        """
        frame_load = 0
        sample_callchains = []

        # 构建时间窗口和线程过滤条件
        # 计算帧的开始和结束时间
        frame_start_time = frame.get('start_time', frame.get('ts', 0))
        frame_end_time = frame.get('end_time', frame.get('ts', 0) + frame.get('dur', 0))

        mask = (
            (perf_df['timestamp_trace'] >= frame_start_time)
            & (perf_df['timestamp_trace'] <= frame_end_time)
            & (perf_df['thread_id'] == frame['tid'])
        )
        frame_samples = perf_df[mask]

        if frame_samples.empty:
            return frame_load, sample_callchains

        # 计算总负载（用于百分比计算）
        total_frame_load = frame_samples['event_count'].sum()

        # logging.info("帧分析开始: ts=%s, dur=%s, tid=%s, 时间窗口=[%s, %s], 样本数=%s, 总负载=%s",
        #              frame.get('ts'), frame.get('dur'), frame.get('tid'),
        #              frame_start_time, frame_end_time, len(frame_samples), total_frame_load)

        for _, sample in frame_samples.iterrows():
            if not pd.notna(sample['callchain_id']):
                # logging.info("跳过无效callchain_id的样本: callchain_id=%s", sample['callchain_id'])
                continue

            try:
                # 分析调用链
                callchain_info = self.analyze_perf_callchain(
                    perf_conn, int(sample['callchain_id']), callchain_cache, files_cache, step_id
                )

                if not callchain_info or len(callchain_info) == 0:
                    # logging.info("调用链分析结果为空: callchain_id=%s", sample['callchain_id'])
                    continue

                # VSync过滤（可选）
                if include_vsync_filter and self._is_vsync_chain(callchain_info, sample['event_count']):
                    # logging.info("VSync过滤掉调用链: callchain_id=%s, event_count=%s",
                    #              sample['callchain_id'], sample['event_count'])
                    continue

                # 累加负载
                frame_load += sample['event_count']

                # 构建样本调用链信息
                try:
                    # 防止除零错误
                    if total_frame_load > 0:
                        sample_load_percentage = (sample['event_count'] / total_frame_load) * 100
                    else:
                        sample_load_percentage = 0.0
                    sample_callchains.append(
                        {
                            'timestamp': int(sample['timestamp_trace']),
                            'event_count': int(sample['event_count']),
                            'load_percentage': float(sample_load_percentage),
                            'callchain': callchain_info,
                        }
                    )
                    # logging.info("成功添加调用链: callchain_id=%s, event_count=%s, 调用链长度=%s",
                    #              sample['callchain_id'], sample['event_count'], len(callchain_info))
                except Exception as e:
                    logging.error(
                        '处理样本时出错: %s, sample: %s, total_frame_load: %s',
                        str(e),
                        sample.to_dict(),
                        total_frame_load,
                    )
                    continue

            except Exception as e:
                logging.error('分析调用链时出错: %s', str(e))
                continue

        # logging.info("帧分析完成: ts=%s, frame_load=%s, sample_callchains数量=%s",
        #              frame.get('ts'), frame_load, len(sample_callchains))

        # 保存帧负载数据到缓存
        if step_id:
            frame_load_data = {
                'ts': frame.get('ts', frame.get('start_time', 0)),
                'dur': frame.get('dur', frame.get('end_time', 0) - frame.get('start_time', 0)),
                'frame_load': frame_load,
                'thread_id': frame.get('tid'),
                'thread_name': frame.get('thread_name', 'unknown'),
                'process_name': frame.get('process_name', 'unknown'),
                'type': frame.get('type', 0),  # 修正：使用type字段
                'vsync': frame.get('vsync', 'unknown'),
                'flag': frame.get('flag'),
                'sample_callchains': sample_callchains,
            }
            FrameCacheManager.add_frame_load(step_id, frame_load_data)

        return frame_load, sample_callchains

    def calculate_frame_load_simple(self, frame: dict[str, Any], perf_df: pd.DataFrame) -> int:
        """简单计算帧负载（不包含调用链分析）

        Args:
            frame: 帧数据字典，必须包含 'ts', 'dur', 'tid' 字段
            perf_df: perf样本DataFrame

        Returns:
            int: 帧负载
        """
        frame_start_time = frame['ts']
        frame_end_time = frame['ts'] + frame['dur']

        # 使用向量化操作进行过滤
        mask = (
            (perf_df['timestamp_trace'] >= frame_start_time)
            & (perf_df['timestamp_trace'] <= frame_end_time)
            & (perf_df['thread_id'] == frame['tid'])
        )
        frame_samples = perf_df[mask]

        if frame_samples.empty:
            return 0

        return int(frame_samples['event_count'].sum())

    def calculate_all_frame_loads_fast(self, frames: pd.DataFrame, perf_df: pd.DataFrame) -> list[dict[str, Any]]:
        """快速计算所有帧的负载值，不分析调用链

        Args:
            frames: 帧数据DataFrame
            perf_df: perf样本DataFrame

        Returns:
            List[Dict]: 帧负载数据列表
        """
        start_time = time.time()
        frame_loads = []

        # 记录数据量
        total_frames = len(frames)
        total_perf_samples = len(perf_df)
        logging.info('开始快速计算帧负载: 帧数=%d, 性能样本数=%d', total_frames, total_perf_samples)

        # 批量计算开始
        calc_start = time.time()
        for i, (_, frame) in enumerate(frames.iterrows()):
            # 每1000帧记录一次进度
            if i % 1000 == 0 and i > 0:
                elapsed = time.time() - calc_start
                rate = i / elapsed if elapsed > 0 else 0
                logging.info(
                    '帧负载计算进度: %d/%d (%.1f%%), 速率: %.1f帧/秒', i, total_frames, i / total_frames * 100, rate
                )

            # 使用现有的简单方法，只计算负载值
            frame_load = self.calculate_frame_load_simple(frame, perf_df)

            # 确保时间戳字段正确
            frame_loads.append(
                {
                    'ts': int(frame['ts']),  # 确保时间戳是整数
                    'dur': int(frame['dur']),  # 确保持续时间是整数
                    'frame_load': frame_load,
                    'thread_id': int(frame['tid']),  # 确保线程ID是整数
                    'thread_name': frame.get('thread_name', 'unknown'),
                    'process_name': frame.get('process_name', 'unknown'),
                    'type': int(frame.get('type', 0)),  # 确保类型是整数
                    'vsync': frame.get('vsync', 'unknown'),
                    'flag': int(frame.get('flag', 0)) if pd.notna(frame.get('flag')) else 0,  # 确保flag是整数
                    'is_main_thread': int(frame.get('is_main_thread', 0)),  # 确保主线程标志是整数
                    'sample_callchains': [],  # 空列表，不保存调用链
                }
            )

        calc_time = time.time() - calc_start
        total_time = time.time() - start_time

        # 计算统计信息
        if frame_loads:
            loads = [f['frame_load'] for f in frame_loads]
            avg_load = sum(loads) / len(loads)
            max_load = max(loads)
            processing_rate = total_frames / calc_time if calc_time > 0 else 0
        else:
            avg_load = max_load = processing_rate = 0

        logging.info('快速帧负载计算完成: 总耗时=%.3f秒, 计算耗时=%.3f秒', total_time, calc_time)
        logging.info('计算结果: 平均负载=%.1f, 最大负载=%d, 处理速率=%.1f帧/秒', avg_load, max_load, processing_rate)

        return frame_loads

    def identify_frames_for_callchain_analysis(
        self, frame_loads: list[dict[str, Any]], stuttered_frames: list[dict[str, Any]] = None
    ) -> list[dict[str, Any]]:
        """识别需要调用链分析的帧（用于前10帧分析）

        Args:
            frame_loads: 帧负载数据列表
            stuttered_frames: 卡顿帧列表（可选）

        Returns:
            List[Dict]: 需要分析调用链的帧列表
        """

        # 1. 按负载排序，获取前10帧
        sorted_frames = sorted(frame_loads, key=lambda x: x['frame_load'], reverse=True)
        top_10_frames = sorted_frames[:10]

        # 2. 卡顿帧（从外部传入）
        stuttered_frame_ids = set()
        if stuttered_frames:
            for frame in stuttered_frames:
                stuttered_frame_ids.add((frame['ts'], frame['dur'], frame['tid']))

        # 3. 空刷帧（type=1的帧）
        empty_frames = [f for f in frame_loads if f.get('type') == 1]

        # 4. 合并需要分析的帧
        frames_to_analyze = []
        analyzed_frame_ids = set()

        # 添加前10帧
        for frame in top_10_frames:
            frame_id = (frame['ts'], frame['dur'], frame['tid'])
            if frame_id not in analyzed_frame_ids:
                frames_to_analyze.append(frame)
                analyzed_frame_ids.add(frame_id)

        # 添加卡顿帧
        for frame in frame_loads:
            frame_id = (frame['ts'], frame['dur'], frame['tid'])
            if frame_id in stuttered_frame_ids and frame_id not in analyzed_frame_ids:
                frames_to_analyze.append(frame)
                analyzed_frame_ids.add(frame_id)

        # 添加空刷帧
        for frame in empty_frames:
            frame_id = (frame['ts'], frame['dur'], frame['tid'])
            if frame_id not in analyzed_frame_ids:
                frames_to_analyze.append(frame)
                analyzed_frame_ids.add(frame_id)

        return frames_to_analyze

    def _is_vsync_chain(self, callchain_info: list[dict], event_count: int) -> bool:
        """判断是否为VSync调用链

        Args:
            callchain_info: 调用链信息
            event_count: 事件计数

        Returns:
            bool: 是否为VSync调用链
        """
        if not self.debug_vsync_enabled:
            return False

        for i in range(len(callchain_info) - 1):
            current_symbol = callchain_info[i]['symbol']
            next_symbol = callchain_info[i + 1]['symbol']

            if not current_symbol or not next_symbol:
                continue

            if (
                'OHOS::Rosen::VSyncCallBackListener::OnReadable' in current_symbol
                and 'OHOS::Rosen::VSyncCallBackListener::HandleVsyncCallbacks' in next_symbol
                and event_count < 2000000
            ):
                return True

        return False

    def batch_calculate_frame_loads(
        self,
        frames: list[dict[str, Any]],
        perf_df: pd.DataFrame,
        perf_conn,
        step_id: str = None,
        callchain_cache: pd.DataFrame = None,
        files_cache: pd.DataFrame = None,
        include_vsync_filter: bool = True,
    ) -> list[tuple[int, list[dict[str, Any]]]]:
        """批量计算多个帧的负载

        Args:
            frames: 帧数据列表
            perf_df: perf样本DataFrame
            perf_conn: perf数据库连接
            step_id: 步骤ID
            callchain_cache: 缓存的callchain数据
            files_cache: 缓存的文件数据
            include_vsync_filter: 是否包含VSync过滤

        Returns:
            List[Tuple]: 每个帧的(load, callchains)元组列表
        """
        results = []
        for frame in frames:
            load, callchains = self.calculate_frame_load(
                frame, perf_df, perf_conn, step_id, callchain_cache, files_cache, include_vsync_filter
            )
            results.append((load, callchains))
        return results
