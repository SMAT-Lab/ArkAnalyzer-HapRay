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
from typing import Dict, List, Any, Optional

import pandas as pd

from .frame_core_load_calculator import FrameLoadCalculator
from .frame_core_cache_manager import FrameCacheManager
from .frame_time_utils import FrameTimeUtils
from .frame_data_parser import validate_database_compatibility


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
            self,
            trace_db_path: str,
            perf_db_path: str,
            app_pids: list,
            step_id: str = None
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
        # 验证数据库兼容性
        if not validate_database_compatibility(trace_db_path):
            return None

        # 连接trace数据库
        trace_conn = sqlite3.connect(trace_db_path)
        perf_conn = sqlite3.connect(perf_db_path)

        try:
            # ==================== 标准化缓存检查和使用 ====================
            # 在分析开始前，确保所有需要的数据都已缓存
            if step_id:
                # 预加载analyzer需要的基础数据
                FrameCacheManager.preload_analyzer_data(
                    trace_conn, perf_conn, step_id, app_pids
                )
                # logging.info("预加载数据结果: %s", preload_result)

                # 确保帧负载数据缓存已初始化
                FrameCacheManager.ensure_data_cached('frame_loads', step_id=step_id)

            # 使用复杂查询接口获取空帧详细信息
            trace_df = FrameCacheManager.get_empty_frames_with_details(trace_conn, app_pids)

            if trace_df.empty:
                # logging.info("未找到符合条件的帧")
                return None

            # 获取总负载
            total_load_query = "SELECT SUM(event_count) as total_load FROM perf_sample"
            total_load_result = pd.read_sql_query(total_load_query, perf_conn)

            # 安全处理total_load，处理None和NaN情况
            if total_load_result.empty or total_load_result['total_load'].iloc[0] is None or pd.isna(
                    total_load_result['total_load'].iloc[0]):
                total_load = 0
                logging.warning("perf_sample表中没有找到有效的event_count数据，设置total_load为0")
            else:
                total_load = total_load_result['total_load'].iloc[0]
                if total_load <= 0:
                    logging.warning("total_load计算结果为0或负数: %s，设置total_load为0", total_load)
                    total_load = 0

            # 获取所有perf样本
            perf_df = FrameCacheManager.get_perf_samples(perf_conn, step_id)

            # 为每个帧创建时间区间
            trace_df['start_time'] = trace_df['ts']
            trace_df['end_time'] = trace_df['ts'] + trace_df['dur']

            # 获取第一帧时间戳用于相对时间计算
            # 从缓存中获取第一帧时间戳
            if step_id:
                try:
                    # 从缓存中获取第一帧时间戳
                    first_frame_time = FrameCacheManager.get_first_frame_timestamp(trace_conn, step_id)
                except Exception:
                    # 如果获取缓存失败，则使用空帧中的最小时间戳作为备选
                    first_frame_time = int(trace_df['ts'].min()) if not trace_df.empty else 0
            else:
                # 如果无法获取step_id，则使用空帧中的最小时间戳作为备选
                first_frame_time = int(trace_df['ts'].min()) if not trace_df.empty else 0

            # 初始化结果列表
            frame_loads = []
            empty_frame_load = 0  # 主线程空帧总负载（即空刷主线程负载）
            background_thread_load = 0  # 后台线程空帧总负载

            # 对每个帧进行分析 - 优先使用缓存中的帧负载数据
            for _, frame in trace_df.iterrows():
                # 检查缓存中是否已有该帧的负载数据
                # pylint: disable=duplicate-code
                cached_frame_loads = FrameCacheManager.get_frame_loads(step_id) if step_id else []
                cached_frame = None

                for cached in cached_frame_loads:
                    if (cached.get('ts') == frame['ts']
                            and cached.get('dur') == frame['dur']
                            and cached.get('thread_id') == frame['tid']):
                        cached_frame = cached
                        break

                if cached_frame:
                    # 使用缓存中的帧负载数据
                    frame_load = cached_frame.get('frame_load', 0)
                    sample_callchains = cached_frame.get('sample_callchains', [])
                    # logging.debug("使用缓存的帧负载数据: ts=%s, load=%s", frame['ts'], frame_load)

                    # 如果缓存中没有sample_callchains，尝试补充
                    if not sample_callchains:
                        # logging.debug("缓存中缺少sample_callchains，尝试补充: ts=%s", frame['ts'])
                        # 直接调用analyze_single_frame重新分析
                        try:
                            frame_load, sample_callchains = self.load_calculator.analyze_single_frame(
                                frame, perf_df, perf_conn, step_id)
                            # logging.debug("重新分析帧调用链: ts=%s, load=%s", frame['ts'], frame_load)
                        except Exception as e:
                            # 如果分析失败，使用默认值
                            frame_load = cached_frame.get('frame_load', 0)
                            sample_callchains = []
                            logging.warning("重新分析帧调用链失败: ts=%s, error=%s", frame['ts'], str(e))
                else:
                    # 缓存中没有，执行帧负载分析
                    try:
                        frame_load, sample_callchains = self.load_calculator.analyze_single_frame(
                            frame, perf_df, perf_conn, step_id)
                        # logging.debug("执行帧负载分析: ts=%s, load=%s", frame['ts'], frame_load)
                    except Exception as e:
                        # 如果分析失败，使用默认值
                        frame_load = 0
                        sample_callchains = []
                        logging.warning("执行帧负载分析失败: ts=%s, error=%s", frame['ts'], str(e))
                # pylint: enable=duplicate-code

                if frame['is_main_thread'] == 1:
                    empty_frame_load += frame_load
                else:
                    background_thread_load += frame_load

                frame_loads.append({
                    'ts': FrameTimeUtils.convert_to_relative_nanoseconds(frame['ts'], first_frame_time),
                    'dur': frame['dur'],
                    'ipid': frame['ipid'],
                    'itid': frame['itid'],
                    'pid': frame['pid'],
                    'tid': frame['tid'],
                    'callstack_id': frame['callstack_id'],
                    'process_name': frame['process_name'],
                    'thread_name': frame['thread_name'],
                    'callstack_name': frame['callstack_name'],
                    'frame_load': frame_load,
                    'is_main_thread': frame['is_main_thread'],
                    'vsync': frame.get('vsync') if pd.notna(frame.get('vsync')) else None,  # 安全处理NaN
                    'flag': frame.get('flag') if pd.notna(frame.get('flag')) else 0,  # 安全处理NaN
                    'type': frame.get('type') if pd.notna(frame.get('type')) else 0,  # 安全处理NaN
                    'sample_callchains': sorted(sample_callchains, key=lambda x: x['event_count'], reverse=True)
                })

            # 转换为DataFrame并按负载排序
            result_df = pd.DataFrame(frame_loads)
            if not result_df.empty:
                # 分别获取主线程和后台线程的top5帧
                main_thread_frames = result_df[result_df['is_main_thread'] == 1].sort_values('frame_load',
                                                                                             ascending=False).head(5)
                background_thread_frames = (result_df[result_df['is_main_thread'] == 0]
                                            .sort_values('frame_load', ascending=False).head(5))

                # 只统计主线程空帧负载和后台线程负载
                if total_load > 0:
                    empty_frame_percentage = (empty_frame_load / total_load) * 100
                    background_thread_percentage = (background_thread_load / total_load) * 100
                else:
                    empty_frame_percentage = 0.0
                    background_thread_percentage = 0.0
                    logging.warning("total_load为0，无法计算百分比，设置为0")

                # 构建结果字典
                return {
                    "status": "success",
                    "summary": {
                        "total_load": int(total_load),
                        "empty_frame_load": int(empty_frame_load),
                        "empty_frame_percentage": float(empty_frame_percentage),
                        "background_thread_load": int(background_thread_load),
                        "background_thread_percentage": float(background_thread_percentage),
                        "total_empty_frames": int(len(trace_df[trace_df['is_main_thread'] == 1])),
                        "empty_frames_with_load": int(len([f for f in frame_loads if f['is_main_thread'] == 1]))
                    },
                    "top_frames": {
                        "main_thread_empty_frames": main_thread_frames.to_dict('records'),
                        "background_thread": background_thread_frames.to_dict('records')
                    }
                }

            # logging.info("未找到任何帧负载数据")
            return None

        except Exception as e:
            logging.error("分析空帧时发生异常: %s", str(e))
            return None

        finally:
            trace_conn.close()
            perf_conn.close()

    def analyze_empty_frame_loads(
            self,
            trace_df: pd.DataFrame,
            perf_df: pd.DataFrame,
            perf_conn,
            step_id: str = None
    ) -> List[Dict[str, Any]]:  # pylint: disable=duplicate-code
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
                if (cached.get('ts') == frame['ts']
                        and cached.get('dur') == frame['dur']
                        and cached.get('thread_id') == frame['tid']):
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
                        frame, perf_df, perf_conn, step_id)
                    # logging.debug("执行帧负载分析: ts=%s, load=%s", frame['ts'], frame_load)
                except Exception as e:
                    # 如果分析失败，使用默认值
                    frame_load = 0
                    sample_callchains = []
                    logging.warning("帧负载分析失败: ts=%s, error=%s", frame['ts'], str(e))
            # pylint: enable=duplicate-code

            frame_loads.append({
                'ts': frame['ts'],
                'dur': frame['dur'],
                'frame_load': frame_load,
                'sample_callchains': sample_callchains,
                'is_main_thread': frame.get('is_main_thread', 0)
            })

        return frame_loads

    def get_empty_frame_statistics(
            self,
            frame_loads: List[Dict[str, Any]],
            total_load: int
    ) -> Dict[str, Any]:
        """计算空帧统计信息

        Args:
            frame_loads: 帧负载列表
            total_load: 总负载

        Returns:
            Dict: 统计信息
        """
        if not frame_loads:
            return {
                "total_empty_frames": 0,
                "empty_frame_load": 0,
                "empty_frame_percentage": 0.0,
                "background_thread_load": 0,
                "background_thread_percentage": 0.0
            }

        # 分离主线程和后台线程
        main_thread_frames = [f for f in frame_loads if f.get('is_main_thread') == 1]
        background_thread_frames = [f for f in frame_loads if f.get('is_main_thread') != 1]

        # 计算负载
        empty_frame_load = int(sum(f['frame_load'] for f in main_thread_frames))  # 确保返回Python原生int类型
        background_thread_load = int(sum(f['frame_load'] for f in background_thread_frames))  # 确保返回Python原生int类型

        # 计算百分比
        empty_frame_percentage = (empty_frame_load / total_load) * 100 if total_load > 0 else 0
        background_thread_percentage = (background_thread_load / total_load) * 100 if total_load > 0 else 0

        return {
            "total_empty_frames": len(main_thread_frames),
            "empty_frame_load": empty_frame_load,
            "empty_frame_percentage": empty_frame_percentage,
            "background_thread_load": background_thread_load,
            "background_thread_percentage": background_thread_percentage,
            "frames_with_load": len([f for f in main_thread_frames if f['frame_load'] > 0])
        }
