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
from typing import Any, Optional

import pandas as pd

from .frame_core_cache_manager import FrameCacheManager


class VSyncAnomalyAnalyzer:
    """VSync异常分析器

    专门用于分析VSync信号的异常情况，包括：
    1. VSync频率异常检测（高频/低频时间段）
    2. VSync与帧的不匹配检测
    3. 异常率统计
    """

    def __init__(self, cache_manager: FrameCacheManager = None):
        """
        初始化VSync异常分析器

        Args:
            cache_manager: 缓存管理器实例
        """
        self.cache_manager = cache_manager

    def analyze_vsync_anomalies(self, app_pids: list) -> Optional[dict[str, Any]]:
        """分析VSync异常

        Returns:
            Optional[dict[str, Any]]: VSync异常分析结果，如果没有数据或分析失败则返回None
        """

        try:
            # 使用FrameCacheManager获取已缓存的帧数据
            frames_df = self.cache_manager.get_frames_data(app_pids)

            if frames_df.empty:
                logging.info('No frame data found for VSync analysis')
                return None

            # 分析VSync异常
            result = self._analyze_vsync_anomalies_impl(frames_df)

            if result is None:
                logging.info('No VSync anomaly data found')
                return None

            return result

        except Exception as e:
            logging.error('VSync anomaly analysis failed: %s', str(e))
            return None

    def _analyze_vsync_anomalies_impl(self, frames_df: pd.DataFrame) -> Optional[dict[str, Any]]:
        """分析VSync异常实现"""
        try:
            # 获取第一帧时间戳用于相对时间计算
            first_frame_time = self.cache_manager.get_first_frame_timestamp()

            # 1. 按vsync分组分析
            vsync_groups = self._group_frames_by_vsync(frames_df)

            if vsync_groups.empty:
                logging.info('No valid VSync groups found')
                return None

            # 2. 计算VSync间隔（使用相对时间戳）
            vsync_intervals = self._calculate_vsync_intervals(vsync_groups, first_frame_time)

            # 3. 检测各种异常
            frequency_anomalies = self._detect_frequency_anomalies(vsync_intervals)
            frame_mismatches = self._detect_frame_mismatches(vsync_groups, first_frame_time)

            return {
                'statistics': {
                    'total_vsync_signals': len(vsync_groups),
                    'frequency_anomalies_count': len(frequency_anomalies),
                    'frame_mismatch_count': len(frame_mismatches),
                    'anomaly_rate': self._calculate_anomaly_rate(vsync_groups, frequency_anomalies, frame_mismatches),
                },
                'frequency_anomalies': frequency_anomalies,
                'frame_mismatches': frame_mismatches,
            }

        except Exception as e:
            logging.error('Error in VSync anomaly analysis: %s', str(e))
            return None

    def _group_frames_by_vsync(self, frames_df: pd.DataFrame) -> pd.DataFrame:
        """按vsync分组帧数据"""
        # 过滤掉vsync为空的记录
        valid_frames = frames_df[frames_df['vsync'].notna()].copy()

        if valid_frames.empty:
            return pd.DataFrame()

        # 按vsync分组，计算统计信息
        vsync_groups = (
            valid_frames.groupby('vsync')
            .agg(
                {
                    'ts': ['min', 'max', 'count'],
                    'type': list,
                    'flag': list,
                    'dur': 'sum',
                    'thread_name': 'first',
                    'process_name': 'first',
                }
            )
            .reset_index()
        )

        # 重命名列
        vsync_groups.columns = [
            'vsync',
            'start_time',
            'end_time',
            'frame_count',
            'types',
            'flags',
            'total_duration',
            'thread_name',
            'process_name',
        ]

        # 按时间排序
        return vsync_groups.sort_values('start_time')

    def _calculate_vsync_intervals(self, vsync_groups: pd.DataFrame, first_frame_time: int) -> list[dict[str, Any]]:
        """计算VSync间隔"""
        intervals = []

        for i in range(1, len(vsync_groups)):
            current_vsync = vsync_groups.iloc[i]
            previous_vsync = vsync_groups.iloc[i - 1]

            interval = current_vsync['start_time'] - previous_vsync['start_time']
            frequency = 1_000_000_000 / interval if interval > 0 else 0

            intervals.append(
                {
                    'vsync1': previous_vsync['vsync'],
                    'vsync2': current_vsync['vsync'],
                    'interval': interval,
                    'frequency': frequency,
                    'ts': previous_vsync['start_time'] - first_frame_time,  # 使用相对时间戳
                }
            )

        return intervals

    def _detect_frequency_anomalies(self, vsync_intervals: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """检测VSync频率异常"""
        # 正常VSync频率范围：30-120Hz (8.33ms - 33.3ms间隔)
        normal_interval_min = 8.33 * 1_000_000  # 8.33ms in ns (120Hz)
        normal_interval_max = 33.3 * 1_000_000  # 33.3ms in ns (30Hz)

        return self._detect_frequency_time_periods(vsync_intervals, normal_interval_min, normal_interval_max)

    def _detect_frequency_time_periods(
        self, vsync_intervals: list[dict[str, Any]], normal_interval_min: int, normal_interval_max: int
    ) -> list[dict[str, Any]]:
        """检测VSync频率的时间段异常"""
        if len(vsync_intervals) < 3:  # 至少需要3个间隔才能形成时间段
            return []

        time_period_anomalies = []

        # 检测持续高频时间段
        high_freq_periods = self._find_continuous_anomaly_periods(
            vsync_intervals, normal_interval_min, is_high_freq=True
        )

        for period in high_freq_periods:
            avg_frequency = 1_000_000_000 / period['avg_interval']
            time_period_anomalies.append(
                {
                    'type': 'high_frequency_period',
                    'start_vsync': int(period['start_vsync']),
                    'end_vsync': int(period['end_vsync']),
                    'start_ts': int(period['start_ts']),
                    'end_ts': int(period['end_ts']),
                    'duration': int(period['duration']),
                    'interval_count': int(period['interval_count']),
                    'avg_interval': int(period['avg_interval']),
                    'avg_frequency': float(avg_frequency),
                    'min_frequency': float(period['min_frequency']),
                    'max_frequency': float(period['max_frequency']),
                    'severity': period['severity'],
                    'description': (
                        f'持续高频时间段: {period["interval_count"]}个间隔, '
                        f'平均{avg_frequency:.1f}Hz, 持续{period["duration"] / 1_000_000:.1f}ms'
                    ),
                }
            )

        # 检测持续低频时间段
        low_freq_periods = self._find_continuous_anomaly_periods(
            vsync_intervals, normal_interval_max, is_high_freq=False
        )

        for period in low_freq_periods:
            avg_frequency = 1_000_000_000 / period['avg_interval']
            time_period_anomalies.append(
                {
                    'type': 'low_frequency_period',
                    'start_vsync': int(period['start_vsync']),
                    'end_vsync': int(period['end_vsync']),
                    'start_ts': int(period['start_ts']),
                    'end_ts': int(period['end_ts']),
                    'duration': int(period['duration']),
                    'interval_count': int(period['interval_count']),
                    'avg_interval': int(period['avg_interval']),
                    'avg_frequency': float(avg_frequency),
                    'min_frequency': float(period['min_frequency']),
                    'max_frequency': float(period['max_frequency']),
                    'severity': period['severity'],
                    'description': (
                        f'持续低频时间段: {period["interval_count"]}个间隔, '
                        f'平均{avg_frequency:.1f}Hz, 持续{period["duration"] / 1_000_000:.1f}ms'
                    ),
                }
            )

        return time_period_anomalies

    def _find_continuous_anomaly_periods(
        self, vsync_intervals: list[dict[str, Any]], threshold: int, is_high_freq: bool
    ) -> list[dict[str, Any]]:
        """查找连续的异常时间段"""
        periods = []
        current_period = None

        for _, interval_data in enumerate(vsync_intervals):
            interval = interval_data['interval']
            frequency = 1_000_000_000 / interval if interval > 0 else 0

            # 判断是否为异常间隔
            is_anomaly = interval < threshold if is_high_freq else interval > threshold

            if is_anomaly:
                if current_period is None:
                    # 开始新的异常时间段
                    current_period = {
                        'start_vsync': interval_data['vsync1'],
                        'end_vsync': interval_data['vsync2'],
                        'start_ts': interval_data['ts'],
                        'end_ts': interval_data['ts'] + interval,
                        'duration': interval,
                        'interval_count': 1,
                        'total_interval': interval,
                        'min_frequency': frequency,
                        'max_frequency': frequency,
                    }
                else:
                    # 继续当前异常时间段
                    current_period['end_vsync'] = interval_data['vsync2']
                    current_period['end_ts'] = interval_data['ts'] + interval
                    current_period['duration'] = current_period['end_ts'] - current_period['start_ts']
                    current_period['interval_count'] += 1
                    current_period['total_interval'] += interval
                    current_period['min_frequency'] = min(current_period['min_frequency'], frequency)
                    current_period['max_frequency'] = max(current_period['max_frequency'], frequency)
            elif current_period is not None:
                # 结束当前异常时间段
                if current_period['interval_count'] >= 3:  # 至少3个连续异常间隔
                    current_period['avg_interval'] = current_period['total_interval'] / current_period['interval_count']
                    current_period['severity'] = self._calculate_period_severity(current_period, is_high_freq)
                    periods.append(current_period)
                current_period = None

        # 处理最后一个时间段
        if current_period is not None and current_period['interval_count'] >= 3:
            current_period['avg_interval'] = current_period['total_interval'] / current_period['interval_count']
            current_period['severity'] = self._calculate_period_severity(current_period, is_high_freq)
            periods.append(current_period)

        return periods

    def _calculate_period_severity(self, period: dict[str, Any], is_high_freq: bool) -> str:
        """计算时间段异常的严重程度"""
        if is_high_freq:
            # 高频异常：根据平均频率和持续时间判断
            avg_freq = 1_000_000_000 / period['avg_interval']
            duration_ms = period['duration'] / 1_000_000

            if avg_freq > 200 or duration_ms > 100:  # 超过200Hz或持续100ms以上
                return 'high'
            if avg_freq > 150 or duration_ms > 50:  # 超过150Hz或持续50ms以上
                return 'medium'
            return 'low'

        # 低频异常：根据平均频率和持续时间判断
        avg_freq = 1_000_000_000 / period['avg_interval']
        duration_ms = period['duration'] / 1_000_000

        if avg_freq < 15 or duration_ms > 200:  # 低于15Hz或持续200ms以上
            return 'high'
        if avg_freq < 20 or duration_ms > 100:  # 低于20Hz或持续100ms以上
            return 'medium'
        return 'low'

    def _detect_frame_mismatches(self, vsync_groups: pd.DataFrame, first_frame_time: int) -> list[dict[str, Any]]:
        """检测VSync与帧的不匹配异常"""
        mismatches = []

        for _, row in vsync_groups.iterrows():
            types = row['types']
            actual_frames = types.count(0)  # type=0 表示实际帧
            expect_frames = types.count(1)  # type=1 表示期望帧

            if actual_frames == 0:
                mismatches.append(
                    {
                        'type': 'no_actual_frame',
                        'vsync': int(row['vsync']),
                        'expect_frames': int(expect_frames),
                        'description': f'VSync {int(row["vsync"])} 只有期望帧，没有实际渲染帧',
                        'ts': int(row['start_time'] - first_frame_time),
                        'thread_name': str(row['thread_name']),
                        'process_name': str(row['process_name']),
                    }
                )
            if expect_frames == 0:
                mismatches.append(
                    {
                        'type': 'no_expect_frame',
                        'vsync': int(row['vsync']),
                        'actual_frames': int(actual_frames),
                        'description': f'VSync {int(row["vsync"])} 只有实际帧，没有期望帧',
                        'ts': int(row['start_time'] - first_frame_time),
                        'thread_name': str(row['thread_name']),
                        'process_name': str(row['process_name']),
                    }
                )

        return mismatches

    def _calculate_anomaly_rate(
        self, vsync_groups: pd.DataFrame, frequency_anomalies: list, frame_mismatches: list
    ) -> float:
        """计算异常率"""
        total_vsync = len(vsync_groups)
        if total_vsync == 0:
            return 0.0

        total_anomalies = len(frequency_anomalies) + len(frame_mismatches)
        anomaly_rate = (total_anomalies / total_vsync) * 100

        return round(anomaly_rate, 2)
