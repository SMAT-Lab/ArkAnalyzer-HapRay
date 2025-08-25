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
import sqlite3
import time
from typing import Any, Optional

import pandas as pd

from .frame_core_cache_manager import FrameCacheManager
from .frame_core_load_calculator import FrameLoadCalculator
from .frame_data_advanced_accessor import FrameDbAdvancedAccessor
from .frame_data_parser import validate_database_compatibility
from .frame_time_utils import FrameTimeUtils


class EmptyFrameAnalyzer:
    """空帧分析器

    专门用于分析空帧（flag=2, type=0）的负载情况，包括：
    1. 空帧负载计算
    2. 主线程vs后台线程分析
    3. 空帧调用链分析

    帧标志 (flag) 定义：
    - flag = 0: 实际渲染帧不卡帧（正常帧）
    - flag = 1: 实际渲染帧卡帧（expectEndTime < actualEndTime为异常）
    - flag = 2: 数据不需要绘制（空帧，本分析器专门分析此类帧）
    - flag = 3: rs进程与app进程起止异常（|expRsStartTime - expUiEndTime| < 1ms 正常，否则异常）
    """

    def __init__(self, debug_vsync_enabled: bool = False):
        """
        初始化空帧分析器

        Args:
            debug_vsync_enabled: VSync调试开关
        """
        self.load_calculator = FrameLoadCalculator(debug_vsync_enabled)

    def analyze_empty_frames(
        self, trace_db_path: str, perf_db_path: str, app_pids: list, step_id: str = None
    ) -> Optional[dict]:
        """分析空帧（flag=2, type=0）的负载情况

        空帧定义：flag=2 表示数据不需要绘制（没有frameNum信息）

        参数:
        - trace_db_path: str，trace数据库文件路径
        - perf_db_path: str，perf数据库文件路径
        - app_pids: list，应用进程ID列表
        - step_id: str，步骤ID，用于更新缓存

        返回:
        - dict，包含分析结果
        """
        total_start_time = time.time()

        # 阶段1：数据库兼容性验证
        validate_start = time.time()
        if not validate_database_compatibility(trace_db_path):
            logging.error('[%s] Trace数据库兼容性验证失败', step_id)
            return None
        validate_time = time.time() - validate_start

        # 阶段2：数据库连接
        conn_start = time.time()
        try:
            trace_conn = sqlite3.connect(trace_db_path)
            perf_conn = sqlite3.connect(perf_db_path)
        except Exception as e:
            logging.error('[%s] 数据库连接失败: %s', step_id, str(e))
            return None
        conn_time = time.time() - conn_start

        try:
            # 阶段3：缓存检查
            cache_check_start = time.time()
            # 获取缓存数据但不使用，仅用于性能统计
            _ = FrameCacheManager.get_frame_loads(step_id) if step_id else []
            cache_check_time = time.time() - cache_check_start

            # 阶段4：通过数据访问器获取空帧数据
            query_start = time.time()
            trace_df = FrameDbAdvancedAccessor.get_empty_frames_with_details(trace_conn, app_pids)
            query_time = time.time() - query_start

            if trace_df.empty:
                logging.info('[%s] 未找到空帧数据', step_id)
                return None

            # 阶段5：通过数据访问器获取总负载数据
            total_load_start = time.time()
            total_load = FrameDbAdvancedAccessor.get_total_load_for_pids(perf_conn, app_pids)
            total_load_time = time.time() - total_load_start

            # 阶段6：通过缓存管理器获取性能样本
            perf_start = time.time()
            perf_df = FrameCacheManager.get_perf_samples(perf_conn, step_id)
            perf_time = time.time() - perf_start

            # 阶段7：数据预处理
            data_prep_start = time.time()
            trace_df = trace_df.copy()
            trace_df['start_time'] = trace_df['ts']
            trace_df['end_time'] = trace_df['ts'] + trace_df['dur']
            data_prep_time = time.time() - data_prep_start

            # 阶段8：快速帧负载计算（不分析调用链）
            fast_calc_start = time.time()
            frame_loads = self.load_calculator.calculate_all_frame_loads_fast(trace_df, perf_df)
            fast_calc_time = time.time() - fast_calc_start
            logging.info(
                '[%s] 快速帧负载计算完成: 耗时=%.3f秒, 计算了%d个帧', step_id, fast_calc_time, len(frame_loads)
            )

            # 阶段9：识别Top帧进行调用链分析
            top_analysis_start = time.time()
            # 按负载排序，获取前10帧进行详细调用链分析
            sorted_frames = sorted(frame_loads, key=lambda x: x['frame_load'], reverse=True)
            top_10_frames = sorted_frames[:10]

            # 只对Top 10帧进行调用链分析
            for frame_data in top_10_frames:
                # 找到对应的原始帧数据
                frame_mask = (
                    (trace_df['ts'] == frame_data['ts'])
                    & (trace_df['dur'] == frame_data['dur'])
                    & (trace_df['tid'] == frame_data['thread_id'])
                )
                original_frame = trace_df[frame_mask].iloc[0] if not trace_df[frame_mask].empty else None

                if original_frame is not None:
                    try:
                        # 只对Top 10帧进行调用链分析
                        _, sample_callchains = self.load_calculator.analyze_single_frame(
                            original_frame, perf_df, perf_conn, step_id
                        )
                        frame_data['sample_callchains'] = sample_callchains
                    except Exception as e:
                        logging.warning('[%s] 帧调用链分析失败: ts=%s, error=%s', step_id, frame_data['ts'], str(e))
                        frame_data['sample_callchains'] = []
                else:
                    frame_data['sample_callchains'] = []

            # 对于非Top 10帧，设置空的调用链信息
            for frame_data in frame_loads:
                if frame_data not in top_10_frames:
                    frame_data['sample_callchains'] = []

            top_analysis_time = time.time() - top_analysis_start
            logging.info(
                '[%s] Top帧调用链分析完成: 耗时=%.3f秒, 分析了%d个Top帧', step_id, top_analysis_time, len(top_10_frames)
            )

            # 阶段10：结果构建
            result_build_start = time.time()
            result_df = pd.DataFrame(frame_loads)
            if not result_df.empty:
                # 获取第一帧时间戳用于相对时间计算
                first_frame_time = FrameCacheManager.get_first_frame_timestamp(trace_conn, step_id)

                # 分别获取主线程和后台线程的top5帧，并处理时间戳
                main_thread_frames = (
                    result_df[result_df['is_main_thread'] == 1].sort_values('frame_load', ascending=False).head(5)
                )
                background_thread_frames = (
                    result_df[result_df['is_main_thread'] == 0].sort_values('frame_load', ascending=False).head(5)
                )

                # 处理主线程帧的时间戳
                processed_main_thread_frames = []
                for _, frame in main_thread_frames.iterrows():
                    processed_frame = frame.to_dict()
                    # 使用原始时间戳进行相对时间转换
                    original_ts = frame.get('ts', 0)
                    # 转换为相对时间戳（纳秒）- 与卡顿帧分析器保持一致
                    processed_frame['ts'] = FrameTimeUtils.convert_to_relative_nanoseconds(
                        original_ts, first_frame_time
                    )
                    # 保存原始时间戳用于调试
                    processed_frame['original_ts'] = original_ts
                    processed_main_thread_frames.append(processed_frame)

                # 处理后台线程帧的时间戳
                processed_bg_thread_frames = []
                for _, frame in background_thread_frames.iterrows():
                    processed_frame = frame.to_dict()
                    # 使用原始时间戳进行相对时间转换
                    original_ts = frame.get('ts', 0)
                    # 转换为相对时间戳（纳秒）- 与卡顿帧分析器保持一致
                    processed_frame['ts'] = FrameTimeUtils.convert_to_relative_nanoseconds(
                        original_ts, first_frame_time
                    )
                    # 保存原始时间戳用于调试
                    processed_frame['original_ts'] = original_ts
                    processed_bg_thread_frames.append(processed_frame)

                # 计算统计信息
                empty_frame_load = int(sum(f['frame_load'] for f in frame_loads if f.get('is_main_thread') == 1))
                background_thread_load = int(sum(f['frame_load'] for f in frame_loads if f.get('is_main_thread') != 1))

                if total_load > 0:
                    empty_frame_percentage = (empty_frame_load / total_load) * 100
                    background_thread_percentage = (background_thread_load / total_load) * 100
                else:
                    empty_frame_percentage = 0.0
                    background_thread_percentage = 0.0
                    logging.warning('total_load为0，无法计算百分比，设置为0')

                # 构建结果字典
                result = {
                    'status': 'success',
                    'summary': {
                        'total_load': int(total_load),
                        'empty_frame_load': int(empty_frame_load),
                        'empty_frame_percentage': float(empty_frame_percentage),
                        'background_thread_load': int(background_thread_load),
                        'background_thread_percentage': float(background_thread_percentage),
                        'total_empty_frames': int(len(trace_df[trace_df['is_main_thread'] == 1])),
                        'empty_frames_with_load': int(len([f for f in frame_loads if f.get('is_main_thread') == 1])),
                    },
                    'top_frames': {
                        'main_thread_empty_frames': processed_main_thread_frames,
                        'background_thread': processed_bg_thread_frames,
                    },
                }
            else:
                result = None

            result_build_time = time.time() - result_build_start

            # 总耗时统计
            total_time = time.time() - total_start_time
            logging.info('[%s] 空帧分析总耗时: %.3f秒', step_id, total_time)
            logging.info(
                '[%s] 各阶段耗时占比: '
                '验证%.1f%%, '
                '连接%.1f%%, '
                '缓存检查%.1f%%, '
                '查询%.1f%%, '
                '总负载%.1f%%, '
                '性能样本%.1f%%, '
                '预处理%.1f%%, '
                '快速计算%.1f%%, '
                'Top帧分析%.1f%%, '
                '结果构建%.1f%%',
                step_id,
                validate_time / total_time * 100,
                conn_time / total_time * 100,
                cache_check_time / total_time * 100,
                query_time / total_time * 100,
                total_load_time / total_time * 100,
                perf_time / total_time * 100,
                data_prep_time / total_time * 100,
                fast_calc_time / total_time * 100,
                top_analysis_time / total_time * 100,
                result_build_time / total_time * 100,
            )

            return result

        except Exception as e:
            logging.error('[%s] 分析空帧时发生异常: %s', step_id, str(e))
            return None

        finally:
            trace_conn.close()
            perf_conn.close()

    def analyze_empty_frame_loads(
        self, trace_df: pd.DataFrame, perf_df: pd.DataFrame, perf_conn, step_id: str = None
    ) -> list[dict[str, Any]]:  # pylint: disable=duplicate-code
        """分析空帧负载数据

        Args:
            trace_df: 包含空帧信息的DataFrame
            perf_df: 包含perf样本的DataFrame
            perf_conn: perf数据库连接
            step_id: 步骤ID

        Returns:
            List[Dict]: 每个帧的负载分析结果
        """
        frame_loads = []

        # 为每个帧创建时间区间
        trace_df = trace_df.copy()
        trace_df['start_time'] = trace_df['ts']
        trace_df['end_time'] = trace_df['ts'] + trace_df['dur']

        # 对每个帧进行分析 - 优先使用缓存中的帧负载数据
        for _, frame in trace_df.iterrows():
            # 检查缓存中是否已有该帧的负载数据
            # pylint: disable=duplicate-code
            cached_frame_loads = FrameCacheManager.get_frame_loads(step_id) if step_id else []
            cached_frame = None

            for cached in cached_frame_loads:
                if (
                    cached.get('ts') == frame['ts']
                    and cached.get('dur') == frame['dur']
                    and cached.get('thread_id') == frame['tid']
                ):
                    cached_frame = cached
                    break

            if cached_frame:
                # 使用缓存中的帧负载数据
                frame_load = cached_frame.get('frame_load', 0)
                sample_callchains = cached_frame.get('sample_callchains', [])
                # logging.debug("使用缓存的帧负载数据: ts=%s, load=%s", frame['ts'], frame_load)
            else:
                # 缓存中没有，执行帧负载分析
                try:
                    frame_load, sample_callchains = self.load_calculator.analyze_single_frame(
                        frame, perf_df, perf_conn, step_id
                    )
                    # logging.debug("执行帧负载分析: ts=%s, load=%s", frame['ts'], frame_load)
                except Exception as e:
                    # 如果分析失败，使用默认值
                    frame_load = 0
                    sample_callchains = []
                    logging.warning('帧负载分析失败: ts=%s, error=%s', frame['ts'], str(e))
            # pylint: enable=duplicate-code

            frame_loads.append(
                {
                    'ts': frame['ts'],
                    'dur': frame['dur'],
                    'frame_load': frame_load,
                    'sample_callchains': sample_callchains,
                    'is_main_thread': frame.get('is_main_thread', 0),
                }
            )

        return frame_loads

    def get_empty_frame_statistics(self, frame_loads: list[dict[str, Any]], total_load: int) -> dict[str, Any]:
        """计算空帧统计信息

        Args:
            frame_loads: 帧负载列表
            total_load: 总负载

        Returns:
            Dict: 统计信息
        """
        if not frame_loads:
            return {
                'total_empty_frames': 0,
                'empty_frame_load': 0,
                'empty_frame_percentage': 0.0,
                'background_thread_load': 0,
                'background_thread_percentage': 0.0,
            }

        # 分离主线程和后台线程
        main_thread_frames = [f for f in frame_loads if f.get('is_main_thread') == 1]
        background_thread_frames = [f for f in frame_loads if f.get('is_main_thread') != 1]

        # 计算负载
        empty_frame_load = int(sum(f['frame_load'] for f in main_thread_frames))  # 确保返回Python原生int类型
        background_thread_load = int(
            sum(f['frame_load'] for f in background_thread_frames)
        )  # 确保返回Python原生int类型

        # 计算百分比
        empty_frame_percentage = (empty_frame_load / total_load) * 100 if total_load > 0 else 0
        background_thread_percentage = (background_thread_load / total_load) * 100 if total_load > 0 else 0

        return {
            'total_empty_frames': len(main_thread_frames),
            'empty_frame_load': empty_frame_load,
            'empty_frame_percentage': empty_frame_percentage,
            'background_thread_load': background_thread_load,
            'background_thread_percentage': background_thread_percentage,
            'frames_with_load': len([f for f in main_thread_frames if f['frame_load'] > 0]),
        }
