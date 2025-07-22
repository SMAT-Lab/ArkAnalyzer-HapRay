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
from typing import Dict, Any, List, Optional

import pandas as pd

from .frame_cache_manager import FrameCacheManager
from .frame_load_calculator import FrameLoadCalculator
from .frame_data_parser import validate_database_compatibility


class EmptyFrameAnalyzer:
    """空帧分析器
    
    专门用于分析空帧（flag=2, type=0）的负载情况，包括：
    1. 空帧负载计算
    2. 主线程vs后台线程分析
    3. 空帧调用链分析
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
        scene_dir: str = None,
        step_id: str = None
    ) -> Optional[dict]:
        """分析空帧（flag=2, type=0）的负载情况

        参数:
        - trace_db_path: str，trace数据库文件路径
        - perf_db_path: str，perf数据库文件路径
        - app_pids: list，应用进程ID列表
        - scene_dir: str，场景目录路径，用于更新缓存
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
            # 执行查询获取帧信息
            query = f"""
            WITH filtered_frames AS (
                -- 首先获取符合条件的帧
                SELECT fs.ts, fs.dur, fs.ipid, fs.itid, fs.callstack_id
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
                WHERE p.pid IN ({','.join('?' * len(app_pids))})
            )
            -- 最后获取调用栈信息
            SELECT pf.*, cs.name as callstack_name
            FROM process_filtered pf
            JOIN callstack cs ON pf.callstack_id = cs.id
            """

            # 获取帧信息
            trace_df = pd.read_sql_query(query, trace_conn, params=app_pids)

            # 更新PID和TID缓存（如果提供了scene_dir和step_id）
            if scene_dir and step_id:
                FrameCacheManager.update_pid_tid_cache(step_id, trace_df)

            if trace_df.empty:
                logging.info("未找到符合条件的帧")
                return None

            # 获取总负载
            total_load_query = "SELECT SUM(event_count) as total_load FROM perf_sample"
            total_load = pd.read_sql_query(total_load_query, perf_conn)['total_load'].iloc[0]

            # 获取所有perf样本
            perf_query = "SELECT callchain_id, timestamp_trace, thread_id, event_count FROM perf_sample"
            perf_df = pd.read_sql_query(perf_query, perf_conn)

            # 为每个帧创建时间区间
            trace_df['start_time'] = trace_df['ts']
            trace_df['end_time'] = trace_df['ts'] + trace_df['dur']

            # 初始化结果列表
            frame_loads = []
            empty_frame_load = 0  # 主线程空帧总负载（即空刷主线程负载）
            background_thread_load = 0  # 后台线程空帧总负载

            # 对每个帧进行分析 - 使用模块化的负载计算器
            for _, frame in trace_df.iterrows():
                frame_load, sample_callchains = self.load_calculator.analyze_single_frame(
                    frame, perf_df, perf_conn, step_id)
                    
                if frame['is_main_thread'] == 1:
                    empty_frame_load += frame_load
                else:
                    background_thread_load += frame_load
                    
                frame_loads.append({
                    'ts': frame['ts'],
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
                empty_frame_percentage = (empty_frame_load / total_load) * 100
                background_thread_percentage = (background_thread_load / total_load) * 100

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

            logging.info("未找到任何帧负载数据")
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
    ) -> List[Dict[str, Any]]:
        """分析多个空帧的负载情况

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

        # 对每个帧进行分析
        for _, frame in trace_df.iterrows():
            frame_load, sample_callchains = self.load_calculator.analyze_single_frame(
                frame, perf_df, perf_conn, step_id)

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
        empty_frame_load = sum(f['frame_load'] for f in main_thread_frames)
        background_thread_load = sum(f['frame_load'] for f in background_thread_frames)

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