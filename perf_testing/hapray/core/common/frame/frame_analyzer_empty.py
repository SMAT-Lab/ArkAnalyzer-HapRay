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
import traceback
from typing import Optional

import pandas as pd

from .frame_constants import TOP_FRAMES_FOR_CALLCHAIN
from .frame_core_cache_manager import FrameCacheManager
from .frame_core_load_calculator import FrameLoadCalculator
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

    def __init__(self, debug_vsync_enabled: bool = False, cache_manager: FrameCacheManager = None):
        """
        初始化空帧分析器

        Args:
            debug_vsync_enabled: VSync调试开关
            cache_manager: 缓存管理器实例
        """
        self.cache_manager = cache_manager
        self.load_calculator = FrameLoadCalculator(debug_vsync_enabled, cache_manager)
        
        # 新增：算法升级开关
        self.false_positive_filter_enabled = True  # 默认启用假阳性过滤
        self.wakeup_chain_enabled = True  # 默认启用唤醒链分析（只对Top N帧）

    def analyze_empty_frames(self) -> Optional[dict]:
        """分析空帧（flag=2, type=0）的负载情况

        空帧定义：flag=2 表示数据不需要绘制（没有frameNum信息）

        返回:
        - dict，包含分析结果
        """
        # 从cache_manager获取数据库连接和参数
        trace_conn = self.cache_manager.trace_conn
        perf_conn = self.cache_manager.perf_conn
        app_pids = self.cache_manager.app_pids

        if not trace_conn or not perf_conn:
            logging.error('数据库连接未建立')
            return None

        total_start_time = time.time()
        timing_stats = {}

        try:
            # 阶段1：加载数据
            trace_df, total_load, perf_df = self._load_empty_frame_data(app_pids, timing_stats)
            
            # 如果没有空刷帧，返回空结果（空刷帧数为0，CPU为0）
            if trace_df.empty:
                logging.info('应用进程没有空刷帧，返回空结果')
                return self._build_empty_result(total_load, timing_stats)
            
            # 【新增】假阳性过滤（在阶段1之后，阶段2之前）
            # 重要：必须对所有flag=2帧进行过滤
            if self.false_positive_filter_enabled:
                filter_start = time.time()
                trace_df = self._filter_false_positives(trace_df, trace_conn)
                timing_stats['false_positive_filter'] = time.time() - filter_start
                logging.info('假阳性过滤耗时: %.3f秒', timing_stats['false_positive_filter'])
                if trace_df.empty:
                    logging.info('假阳性过滤后没有剩余帧，返回空结果')
                    return self._build_empty_result(total_load, timing_stats)

            # 阶段2：数据预处理
            self._prepare_frame_data(trace_df, timing_stats)

            # 阶段3：快速帧负载计算
            frame_loads = self._calculate_frame_loads(trace_df, perf_df, timing_stats)

            # 阶段4：Top帧调用链分析
            self._analyze_top_frames_callchains(frame_loads, trace_df, perf_df, perf_conn, timing_stats)
            
            # 【新增】Top帧唤醒链分析（用于填充related_threads字段）
            if self.wakeup_chain_enabled:
                wakeup_start = time.time()
                self._analyze_top_frames_wakeup_chain(frame_loads, trace_df, trace_conn)
                timing_stats['wakeup_chain'] = time.time() - wakeup_start

            # 阶段5：结果构建
            result = self._build_result(frame_loads, trace_df, total_load, timing_stats)

            # 总耗时统计
            total_time = time.time() - total_start_time
            self._log_analysis_complete(total_time, timing_stats)

            return result

        except Exception as e:
            logging.error('分析空帧时发生异常: %s', str(e))
            logging.error('异常堆栈跟踪:\n%s', traceback.format_exc())
            return None

    def _load_empty_frame_data(self, app_pids: list, timing_stats: dict) -> tuple:
        """加载空帧相关数据

        Args:
            trace_conn: trace数据库连接
            perf_conn: perf数据库连接
            app_pids: 应用进程ID列表
            timing_stats: 耗时统计字典，函数内部会设置相关时间值

        Returns:
            tuple: (trace_df, total_load, perf_df)
        """
        # 获取空帧数据
        query_start = time.time()
        trace_df = self.cache_manager.get_empty_frames_with_details(app_pids)
        timing_stats['query'] = time.time() - query_start

        # 即使没有空刷帧，也获取总负载和perf数据，以便构建空结果
        # 获取总负载数据
        total_load_start = time.time()
        total_load = self.cache_manager.get_total_load_for_pids(app_pids)
        timing_stats['total_load'] = time.time() - total_load_start

        # 获取性能样本
        perf_start = time.time()
        perf_df = self.cache_manager.get_perf_samples() if self.cache_manager else pd.DataFrame()
        timing_stats['perf'] = time.time() - perf_start

        return trace_df, total_load, perf_df

    def _prepare_frame_data(self, trace_df: pd.DataFrame, timing_stats: dict) -> None:
        """数据预处理

        Args:
            trace_df: 帧数据DataFrame
            timing_stats: 耗时统计字典，函数内部会设置相关时间值
        """
        data_prep_start = time.time()
        trace_df['start_time'] = trace_df['ts']
        trace_df['end_time'] = trace_df['ts'] + trace_df['dur']
        timing_stats['data_prep'] = time.time() - data_prep_start

    def _calculate_frame_loads(self, trace_df: pd.DataFrame, perf_df: pd.DataFrame, timing_stats: dict) -> list:
        """快速帧负载计算

        Args:
            trace_df: 帧数据DataFrame
            perf_df: 性能数据DataFrame
            timing_stats: 耗时统计字典，函数内部会设置相关时间值

        Returns:
            list: 帧负载数据列表
        """
        fast_calc_start = time.time()
        frame_loads = self.load_calculator.calculate_all_frame_loads_fast(trace_df, perf_df)
        timing_stats['fast_calc'] = time.time() - fast_calc_start
        return frame_loads

    def _analyze_top_frames_callchains(
        self, frame_loads: list, trace_df: pd.DataFrame, perf_df: pd.DataFrame, perf_conn, timing_stats: dict
    ) -> None:
        """识别Top帧并进行调用链分析

        Args:
            frame_loads: 帧负载数据列表
            trace_df: 帧数据DataFrame
            perf_df: 性能数据DataFrame
            perf_conn: perf数据库连接
            timing_stats: 耗时统计字典，函数内部会设置相关时间值
        """
        top_analysis_start = time.time()

        # 按负载排序，获取前N帧进行详细调用链分析
        sorted_frames = sorted(frame_loads, key=lambda x: x['frame_load'], reverse=True)
        top_10_frames = sorted_frames[:TOP_FRAMES_FOR_CALLCHAIN]

        # 只对Top N帧进行调用链分析
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
                    _, sample_callchains = self.load_calculator.analyze_single_frame(
                        original_frame, perf_df, perf_conn, None
                    )
                    frame_data['sample_callchains'] = sample_callchains
                except Exception as e:
                    logging.warning('帧调用链分析失败: ts=%s, error=%s', frame_data['ts'], str(e))
                    frame_data['sample_callchains'] = []
            else:
                frame_data['sample_callchains'] = []

        # 对于非Top 10帧，设置空的调用链信息
        for frame_data in frame_loads:
            if frame_data not in top_10_frames:
                frame_data['sample_callchains'] = []

        timing_stats['top_analysis'] = time.time() - top_analysis_start

    def _build_empty_result(self, total_load: int, timing_stats: dict) -> dict:
        """构建空结果（当没有空刷帧时）
        
        Args:
            total_load: 总负载
            timing_stats: 耗时统计字典
            
        Returns:
            dict: 空结果字典
        """
        result_build_start = time.time()
        
        result = {
            'status': 'success',
            'summary': {
                'total_load': int(total_load) if total_load is not None else 0,
                'empty_frame_load': 0,
                'empty_frame_percentage': 0.0,
                'background_thread_load': 0,
                'background_thread_percentage': 0.0,
                'total_empty_frames': 0,
                'empty_frames_with_load': 0,
            },
            'top_frames': {
                'main_thread_empty_frames': [],
                'background_thread': [],
            },
        }
        
        timing_stats['result_build'] = time.time() - result_build_start
        return result

    def _build_result(self, frame_loads: list, trace_df: pd.DataFrame, total_load: int, timing_stats: dict) -> dict:
        """构建分析结果

        Args:
            frame_loads: 帧负载数据列表
            trace_df: 帧数据DataFrame
            total_load: 总负载
            timing_stats: 耗时统计字典，函数内部会设置相关时间值

        Returns:
            dict: 分析结果
        """
        result_build_start = time.time()
        result_df = pd.DataFrame(frame_loads)

        if result_df.empty:
            # 如果没有帧负载数据，返回空结果
            timing_stats['result_build'] = time.time() - result_build_start
            return self._build_empty_result(total_load, timing_stats)

        # 获取第一帧时间戳用于相对时间计算
        first_frame_time = self.cache_manager.get_first_frame_timestamp() if self.cache_manager else 0

        # 分别获取主线程和后台线程的top5帧
        main_thread_frames = (
            result_df[result_df['is_main_thread'] == 1].sort_values('frame_load', ascending=False).head(5)
        )
        background_thread_frames = (
            result_df[result_df['is_main_thread'] == 0].sort_values('frame_load', ascending=False).head(5)
        )

        # 处理主线程帧的时间戳
        processed_main_thread_frames = self._process_frame_timestamps(main_thread_frames, first_frame_time)

        # 处理后台线程帧的时间戳
        processed_bg_thread_frames = self._process_frame_timestamps(background_thread_frames, first_frame_time)

        # 计算统计信息
        # 注意：根据新的五阶段算法，CPU计算是进程级的，所以empty_frame_load应该包括所有空刷帧的CPU浪费
        # 但是为了保持输出格式兼容性，我们仍然分别计算主线程和后台线程的负载
        # empty_frame_load：所有空刷帧的进程级CPU浪费（主线程+后台线程）
        empty_frame_load = int(sum(f['frame_load'] for f in frame_loads))
        # background_thread_load：后台线程的空刷帧CPU浪费（用于兼容性，实际已包含在empty_frame_load中）
        background_thread_load = int(sum(f['frame_load'] for f in frame_loads if f.get('is_main_thread') != 1))

        if total_load > 0:
            empty_frame_percentage = (empty_frame_load / total_load) * 100
            background_thread_percentage = (background_thread_load / total_load) * 100
        else:
            empty_frame_percentage = 0.0
            background_thread_percentage = 0.0

        # 处理占比超过100%的情况
        # 原因：时间窗口扩展（±1ms）导致多个帧的CPU计算存在重叠，这是正常的设计
        percentage_warning = None
        display_percentage = empty_frame_percentage
        severity_level = None
        severity_description = None
        
        # 配置选项：是否限制显示占比为100%（当占比超过100%时）
        # 设置为True时，显示占比将被限制为100%，但原始占比值仍保留在empty_frame_percentage中
        # 设置为False时，显示占比等于原始占比值
        LIMIT_DISPLAY_PERCENTAGE = True  # 默认限制显示为100%
        
        # 根据占比判断严重程度
        if empty_frame_percentage < 3.0:
            severity_level = "normal"
            severity_description = "正常：空刷帧CPU占比小于3%，属于正常范围。"
        elif empty_frame_percentage < 10.0:
            severity_level = "moderate"
            severity_description = "较为严重：空刷帧CPU占比在3%-10%之间，建议关注并优化。"
        elif empty_frame_percentage <= 100.0:
            severity_level = "severe"
            severity_description = "严重：空刷帧CPU占比超过10%，需要优先优化。"
        else:  # > 100%
            severity_level = "extreme"
            severity_description = (
                f"极端异常：空刷帧CPU占比超过100% ({empty_frame_percentage:.2f}%)。"
                f"这是因为时间窗口扩展（±1ms）导致多个帧的CPU计算存在重叠。"
                f"这是正常的设计，不影响单个帧的CPU计算准确性。"
                f"建议查看原始占比值（empty_frame_percentage）和警告信息（percentage_warning）了解详情。"
            )
            percentage_warning = (
                f"注意：空刷帧占比超过100% ({empty_frame_percentage:.2f}%)，这是因为时间窗口扩展（±1ms）"
                f"导致多个帧的CPU计算存在重叠。这是正常的设计，不影响单个帧的CPU计算准确性。"
            )
            logging.warning(percentage_warning)
            
            # 如果启用限制，将显示占比限制为100%
            if LIMIT_DISPLAY_PERCENTAGE:
                display_percentage = 100.0
                logging.info(f"显示占比已限制为100%（原始占比：{empty_frame_percentage:.2f}%）")

        # 构建结果字典
        result = {
            'status': 'success',
            'summary': {
                'total_load': int(total_load),
                'empty_frame_load': int(empty_frame_load),
                'empty_frame_percentage': float(empty_frame_percentage),  # 原始占比值
                'empty_frame_percentage_display': float(display_percentage),  # 显示占比（如果超过100%可能被限制）
                'background_thread_load': int(background_thread_load),
                'background_thread_percentage': float(background_thread_percentage),
                'total_empty_frames': int(len(trace_df)),  # 所有空刷帧数量（包括主线程和后台线程）
                'empty_frames_with_load': int(len([f for f in frame_loads if f.get('frame_load', 0) > 0])),  # 有CPU负载的空刷帧数量
                # 严重程度评估
                'severity_level': severity_level,  # 严重程度级别：normal, moderate, severe, extreme
                'severity_description': severity_description,  # 严重程度说明
            },
            'top_frames': {
                'main_thread_empty_frames': processed_main_thread_frames,
                'background_thread': processed_bg_thread_frames,
            },
        }
        
        # 如果占比超过100%，添加警告信息
        if percentage_warning:
            result['summary']['percentage_warning'] = percentage_warning

        timing_stats['result_build'] = time.time() - result_build_start
        return result

    def _process_frame_timestamps(self, frames_df: pd.DataFrame, first_frame_time: int) -> list:
        """处理帧时间戳，转换为相对时间

        Args:
            frames_df: 帧数据DataFrame
            first_frame_time: 第一帧时间戳

        Returns:
            list: 处理后的帧列表
        """
        processed_frames = []
        for _, frame in frames_df.iterrows():
            processed_frame = frame.to_dict()
            original_ts = frame.get('ts', 0)
            # 转换为相对时间戳（纳秒）- 与卡顿帧分析器保持一致
            processed_frame['ts'] = FrameTimeUtils.convert_to_relative_nanoseconds(original_ts, first_frame_time)
            # 保存原始时间戳用于调试
            processed_frame['original_ts'] = original_ts
            processed_frames.append(processed_frame)
        return processed_frames

    def _log_analysis_complete(self, total_time: float, timing_stats: dict) -> None:
        """记录分析完成日志

        Args:
            total_time: 总耗时
            timing_stats: 各阶段耗时统计
        """
        logging.info('空帧分析总耗时: %.3f秒', total_time)
        logging.info(
            '各阶段耗时占比: '
            '缓存检查%.1f%%, '
            '查询%.1f%%, '
            '总负载%.1f%%, '
            '性能样本%.1f%%, '
            '假阳性过滤%.1f%%, '
            '预处理%.1f%%, '
            '快速计算%.1f%%, '
            'Top帧分析%.1f%%, '
            '唤醒链分析%.1f%%, '
            '结果构建%.1f%%',
            timing_stats.get('cache_check', 0) / total_time * 100 if total_time > 0 else 0,
            timing_stats.get('query', 0) / total_time * 100 if total_time > 0 else 0,
            timing_stats.get('total_load', 0) / total_time * 100 if total_time > 0 else 0,
            timing_stats.get('perf', 0) / total_time * 100 if total_time > 0 else 0,
            timing_stats.get('false_positive_filter', 0) / total_time * 100 if total_time > 0 else 0,
            timing_stats.get('data_prep', 0) / total_time * 100 if total_time > 0 else 0,
            timing_stats.get('fast_calc', 0) / total_time * 100 if total_time > 0 else 0,
            timing_stats.get('top_analysis', 0) / total_time * 100 if total_time > 0 else 0,
            timing_stats.get('wakeup_chain', 0) / total_time * 100 if total_time > 0 else 0,
            timing_stats.get('result_build', 0) / total_time * 100 if total_time > 0 else 0,
        )
    
    def _filter_false_positives(self, trace_df: pd.DataFrame, trace_conn) -> pd.DataFrame:
        """过滤假阳性帧（对所有flag=2帧进行过滤）
        
        假阳性定义：flag=2的帧，但通过NativeWindow API成功提交了内容
        
        检测方法：
        1. 预加载 NativeWindow API 事件（RequestBuffer, FlushBuffer等）
        2. 对每个 flag=2 帧，检查帧时间范围内是否有NativeWindow API提交事件
        3. 如果有，标记为假阳性并从DataFrame中过滤
        
        Args:
            trace_df: 包含flag=2帧的DataFrame
            trace_conn: trace数据库连接
        
        Returns:
            过滤假阳性后的DataFrame
        """
        if trace_df.empty:
            return trace_df
        
        # 计算时间范围
        # 注意：处理dur可能为NaN的情况，并确保类型为int
        min_ts = int(trace_df['ts'].min())
        # 过滤掉dur为NaN的帧，避免计算错误
        valid_dur_df = trace_df[trace_df['dur'].notna()]
        if valid_dur_df.empty:
            logging.warning('所有帧的dur都为NaN，无法计算时间范围')
            return trace_df
        max_ts = int((valid_dur_df['ts'] + valid_dur_df['dur']).max())
        
        # 预加载 NativeWindow API 事件
        # 注意：使用已验证的SQL结构（参考 wakeup_chain_analyzer.py:890）
        nw_events_query = """
        SELECT 
            c.callid as itid,
            c.ts
        FROM callstack c
        INNER JOIN thread t ON c.callid = t.id
        INNER JOIN process p ON t.ipid = p.ipid
        WHERE c.ts >= ? AND c.ts <= ?
        AND p.name NOT IN ('render_service', 'rmrenderservice', 'ohos.sceneboard')
        AND p.name NOT LIKE 'system_%'
        AND p.name NOT LIKE 'com.ohos.%'
        AND (c.name LIKE '%RequestBuffer%' 
             OR c.name LIKE '%FlushBuffer%' 
             OR c.name LIKE '%DoFlushBuffer%' 
             OR c.name LIKE '%NativeWindow%')
        """
        cursor = trace_conn.cursor()
        cursor.execute(nw_events_query, (min_ts, max_ts))
        nw_records = cursor.fetchall()
        
        # 构建事件缓存（按线程ID索引）
        from collections import defaultdict
        from bisect import bisect_left
        
        nw_events_cache = defaultdict(list)
        for itid, ts in nw_records:
            nw_events_cache[itid].append(ts)
        
        # 排序以便二分查找
        for itid in nw_events_cache:
            nw_events_cache[itid].sort()
        
        logging.info(f'预加载NativeWindow API事件: {len(nw_records)}条记录, {len(nw_events_cache)}个线程')
        
        # 过滤假阳性（使用DataFrame操作）
        def is_false_positive(row):
            try:
                frame_itid = row['itid']
                frame_start = row['ts']
                frame_end = row['ts'] + row['dur']
                
                if frame_itid in nw_events_cache:
                    event_timestamps = nw_events_cache[frame_itid]
                    idx = bisect_left(event_timestamps, frame_start)
                    if idx < len(event_timestamps) and event_timestamps[idx] <= frame_end:
                        return True
                return False
            except Exception as e:
                # 如果检查过程中出现异常，记录日志但不标记为假阳性（保守策略）
                logging.warning(f'假阳性检查异常: {e}, row={row.to_dict() if hasattr(row, "to_dict") else row}')
                return False
        
        # 标记假阳性
        false_positive_mask = trace_df.apply(is_false_positive, axis=1)
        false_positive_count = false_positive_mask.sum()
        
        # 过滤假阳性
        filtered_df = trace_df[~false_positive_mask].copy()
        
        logging.info(
            f'假阳性过滤: 过滤前={len(trace_df)}, 过滤后={len(filtered_df)}, '
            f'假阳性={false_positive_count} ({false_positive_count/len(trace_df)*100:.1f}%)'
        )
        
        return filtered_df
    
    def _analyze_top_frames_wakeup_chain(self, frame_loads: list, trace_df: pd.DataFrame, trace_conn) -> None:
        """对Top N帧进行唤醒链分析，填充related_threads字段
        
        注意：
        - 只对Top N帧进行唤醒链分析（性能考虑）
        - CPU计算是进程级的，不需要唤醒链分析
        - 唤醒链分析仅用于填充related_threads字段和根因分析
        
        Args:
            frame_loads: 帧负载数据列表
            trace_df: 帧数据DataFrame
            trace_conn: trace数据库连接
        """
        from .frame_constants import TOP_FRAMES_FOR_CALLCHAIN
        
        # 按负载排序，获取Top N帧
        sorted_frames = sorted(frame_loads, key=lambda x: x['frame_load'], reverse=True)
        top_n_frames = sorted_frames[:TOP_FRAMES_FOR_CALLCHAIN]
        
        logging.info(f'开始对Top {len(top_n_frames)}帧进行唤醒链分析...')
        
        # 只对Top N帧进行唤醒链分析
        for frame_data in top_n_frames:
            # 找到对应的原始帧数据
            frame_mask = (
                (trace_df['ts'] == frame_data['ts'])
                & (trace_df['dur'] == frame_data['dur'])
                & (trace_df['tid'] == frame_data['thread_id'])
            )
            original_frame = trace_df[frame_mask].iloc[0] if not trace_df[frame_mask].empty else None
            
            if original_frame is not None:
                try:
                    # 调用简化的唤醒链分析（只获取线程列表，不计算CPU）
                    related_threads = self._get_related_threads_simple(original_frame, trace_conn)
                    frame_data['related_threads'] = related_threads
                except Exception as e:
                    logging.warning(f'唤醒链分析失败: ts={frame_data["ts"]}, error={e}')
                    frame_data['related_threads'] = []
            else:
                frame_data['related_threads'] = []
        
        # 对于非Top N帧，设置空的related_threads
        for frame_data in frame_loads:
            if 'related_threads' not in frame_data:
                frame_data['related_threads'] = []
        
        logging.info(f'完成Top {len(top_n_frames)}帧的唤醒链分析')
    
    def _get_related_threads_simple(self, frame, trace_conn) -> list:
        """获取帧相关的线程列表（简化版唤醒链分析）
        
        Args:
            frame: 帧数据（DataFrame行）
            trace_conn: trace数据库连接
        
        Returns:
            线程列表
        """
        try:
            from experiments_ignore.render_service.checkers.wakeup_chain_analyzer import find_wakeup_chain
        except ImportError:
            # 如果导入失败，返回空列表（唤醒链分析是可选的）
            logging.warning('无法导入wakeup_chain_analyzer，跳过唤醒链分析')
            return []
        
        frame_itid = frame['itid']
        frame_start = frame['ts']
        frame_end = frame['ts'] + frame['dur']
        app_pid = frame.get('pid') or frame.get('app_pid')
        
        # 调用唤醒链分析
        related_itids = find_wakeup_chain(
            trace_conn=trace_conn,
            start_itid=frame_itid,
            frame_start=frame_start,
            frame_end=frame_end,
            app_pid=app_pid
        )
        
        # 获取线程详细信息
        if not related_itids:
            return []
        
        cursor = trace_conn.cursor()
        itids_list = list(related_itids)
        placeholders = ','.join('?' * len(itids_list))
        
        cursor.execute(f"""
            SELECT t.itid, t.tid, t.name, p.pid, p.name
            FROM thread t
            INNER JOIN process p ON t.ipid = p.ipid
            WHERE t.itid IN ({placeholders})
        """, itids_list)
        
        thread_results = cursor.fetchall()
        
        from .frame_utils import is_system_thread
        
        related_threads = []
        for itid, tid, thread_name, pid, process_name in thread_results:
            related_threads.append({
                'itid': itid,
                'tid': tid,
                'thread_name': thread_name,
                'pid': pid,
                'process_name': process_name,
                'is_system_thread': is_system_thread(process_name, thread_name)
            })
        
        return related_threads
