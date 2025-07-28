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
from typing import Dict, List, Tuple, Any

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
        step_id: str = None
    ) -> List[Dict[str, Any]]:
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
        try:
            # 如果没有缓存，先获取缓存
            if callchain_cache is None or callchain_cache.empty:
                # logging.info("callchain_cache为空，从数据库获取")
                callchain_cache = FrameCacheManager.get_callchain_cache(perf_conn, step_id)
            if files_cache is None or files_cache.empty:
                # logging.info("files_cache为空，从数据库获取")
                files_cache = FrameCacheManager.get_files_cache(perf_conn, step_id)

            # 确定缓存key
            cache_key = step_id if step_id else str(perf_conn)
            # logging.info("分析调用链: callchain_id=%s, cache_key=%s", callchain_id, cache_key)

            # 检查缓存是否为空
            if (cache_key not in FrameCacheManager._callchain_cache
                    or FrameCacheManager._callchain_cache[cache_key].empty
                    or cache_key not in FrameCacheManager._files_cache
                    or FrameCacheManager._files_cache[cache_key].empty):
                logging.warning("缓存数据为空，无法分析调用链: cache_key=%s", cache_key)
                            # logging.info("callchain_cache keys: %s", list(FrameCacheManager._callchain_cache.keys()))
            # logging.info("files_cache keys: %s", list(FrameCacheManager._files_cache.keys()))
                return []

            # 从缓存中获取callchain数据
            callchain_records = (
                FrameCacheManager._callchain_cache[cache_key][
                    FrameCacheManager._callchain_cache[cache_key]['callchain_id'] == callchain_id
                ]
            )

            # logging.info("找到callchain记录数: %s", len(callchain_records))

            if callchain_records.empty:
                # logging.info("未找到callchain_id=%s的记录", callchain_id)
                return []

            # 构建调用链信息
            callchain_info = []
            for _, record in callchain_records.iterrows():
                # 从缓存中获取文件信息
                file_mask = (
                    (FrameCacheManager._files_cache[cache_key]['file_id'] == record['file_id']) &
                    (FrameCacheManager._files_cache[cache_key]['serial_id'] == record['symbol_id'])
                )
                file_info = FrameCacheManager._files_cache[cache_key][file_mask]
                
                symbol = file_info['symbol'].iloc[0] if not file_info.empty else 'unknown'
                path = file_info['path'].iloc[0] if not file_info.empty else 'unknown'

                callchain_info.append({
                    'depth': int(record['depth']),
                    'file_id': int(record['file_id']),
                    'path': str(path),
                    'symbol_id': int(record['symbol_id']),
                    'symbol': str(symbol)
                })

            # logging.info("构建的调用链信息: 长度=%s", len(callchain_info))
            return callchain_info

        except Exception as e:
            logging.error("分析调用链失败: %s", str(e))
            return []

    def analyze_single_frame(self, frame, perf_df, perf_conn, step_id):
        """分析单个帧的负载和调用链，返回frame_load和sample_callchains

        这是从原始FrameAnalyzer.analyze_single_frame方法迁移的代码
        """
        # 在函数内部获取缓存
        callchain_cache = FrameCacheManager.get_callchain_cache(perf_conn, step_id)
        files_cache = FrameCacheManager.get_files_cache(perf_conn, step_id)
        frame_load = 0
        sample_callchains = []

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
            # logging.info("analyze_single_frame: 帧时间窗口内无样本, ts=%s, 时间窗口=[%s, %s], tid=%s", 
            #              frame.get('ts'), frame_start_time, frame_end_time, frame.get('tid'))
            return frame_load, sample_callchains

        # logging.info("analyze_single_frame: 找到样本, ts=%s, 时间窗口=[%s, %s], tid=%s, 样本数=%s", 
        #              frame.get('ts'), frame_start_time, frame_end_time, frame.get('tid'), len(frame_samples))

        for _, sample in frame_samples.iterrows():
            if not pd.notna(sample['callchain_id']):
                continue

            try:
                callchain_info = self.analyze_perf_callchain(
                    perf_conn,
                    int(sample['callchain_id']),
                    callchain_cache,
                    files_cache,
                    step_id
                )

                if callchain_info and len(callchain_info) > 0:
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

                    if not is_vsync_chain:
                        frame_load += sample['event_count']
                        try:
                            sample_load_percentage = (sample['event_count'] / frame_load) * 100
                            sample_callchains.append({
                                'timestamp': int(sample['timestamp_trace']),
                                'event_count': int(sample['event_count']),
                                'load_percentage': float(sample_load_percentage),
                                'callchain': callchain_info
                            })
                        except Exception as e:
                            logging.error(
                                "处理样本时出错: %s, sample: %s, frame_load: %s",
                                str(e), sample.to_dict(), frame_load
                            )
                            continue

            except Exception as e:
                logging.error("分析调用链时出错: %s", str(e))
                continue

        return frame_load, sample_callchains

    def calculate_frame_load(
        self,
        frame: Dict[str, Any],
        perf_df: pd.DataFrame,
        perf_conn,
        step_id: str = None,
        callchain_cache: pd.DataFrame = None,
        files_cache: pd.DataFrame = None,
        include_vsync_filter: bool = True
    ) -> Tuple[int, List[Dict[str, Any]]]:
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
                    perf_conn,
                    int(sample['callchain_id']),
                    callchain_cache,
                    files_cache,
                    step_id
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
                    sample_load_percentage = (sample['event_count'] / total_frame_load) * 100
                    sample_callchains.append({
                        'timestamp': int(sample['timestamp_trace']),
                        'event_count': int(sample['event_count']),
                        'load_percentage': float(sample_load_percentage),
                        'callchain': callchain_info
                    })
                    # logging.info("成功添加调用链: callchain_id=%s, event_count=%s, 调用链长度=%s", 
                    #              sample['callchain_id'], sample['event_count'], len(callchain_info))
                except Exception as e:
                    logging.error(
                        "处理样本时出错: %s, sample: %s, total_frame_load: %s",
                        str(e), sample.to_dict(), total_frame_load
                    )
                    continue

            except Exception as e:
                logging.error("分析调用链时出错: %s", str(e))
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
                'sample_callchains': sample_callchains
            }
            FrameCacheManager.add_frame_load(step_id, frame_load_data)

        return frame_load, sample_callchains

    def calculate_frame_load_simple(
        self,
        frame: Dict[str, Any],
        perf_df: pd.DataFrame
    ) -> int:
        """简单计算帧负载（不包含调用链分析）

        Args:
            frame: 帧数据字典，必须包含 'ts', 'dur', 'tid' 字段
            perf_df: perf样本DataFrame

        Returns:
            int: 帧负载
        """
        frame_start_time = frame["ts"]
        frame_end_time = frame["ts"] + frame["dur"]

        mask = (
            (perf_df['timestamp_trace'] >= frame_start_time)
            & (perf_df['timestamp_trace'] <= frame_end_time)
            & (perf_df['thread_id'] == frame['tid'])
        )
        frame_samples = perf_df[mask]

        if frame_samples.empty:
            return 0

        return int(frame_samples['event_count'].sum())

    def _is_vsync_chain(self, callchain_info: List[Dict], event_count: int) -> bool:
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

            if ('OHOS::Rosen::VSyncCallBackListener::OnReadable' in current_symbol
                    and 'OHOS::Rosen::VSyncCallBackListener::HandleVsyncCallbacks' in next_symbol
                    and event_count < 2000000):
                return True

        return False

    def batch_calculate_frame_loads(
        self,
        frames: List[Dict[str, Any]],
        perf_df: pd.DataFrame,
        perf_conn,
        step_id: str = None,
        callchain_cache: pd.DataFrame = None,
        files_cache: pd.DataFrame = None,
        include_vsync_filter: bool = True
    ) -> List[Tuple[int, List[Dict[str, Any]]]]:
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
                frame, perf_df, perf_conn, step_id,
                callchain_cache, files_cache, include_vsync_filter
            )
            results.append((load, callchains))
        return results
