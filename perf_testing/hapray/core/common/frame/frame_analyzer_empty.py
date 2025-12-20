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
# 导入公共模块
from .frame_empty_common import (
    EmptyFrameCPUCalculator,
    EmptyFrameCallchainAnalyzer,
    EmptyFrameResultBuilder,
    calculate_process_instructions
)
# 导入RS skip追溯模块
from .frame_rs_skip_backtrack_api import (
    preload_caches as preload_rs_api_caches,
    trace_rs_skip_to_app_frame as trace_rs_api
)
from .frame_rs_skip_backtrack_nw import (
    preload_caches as preload_nw_caches,
    trace_rs_skip_to_app_frame as trace_nw_api
)


class EmptyFrameAnalyzer:
    """统一空刷帧分析器（EmptyFrame + RSSkip合并）

    业务目标：检测所有空刷帧，使用两种检测方法：
    1. 正向检测：分析应用进程的flag=2空刷帧
    2. 反向追溯：从RS skip事件追溯到应用帧（补充漏检）

    核心功能：
    1. 空帧检测（正向 + 反向）
    2. 帧合并去重（避免重复计数）
    3. CPU浪费计算（应用进程 + RS进程）
    4. 调用链分析
    5. 重要性标记（traced_count）

    帧标志 (flag) 定义：
    - flag = 0: 实际渲染帧不卡帧（正常帧）
    - flag = 1: 实际渲染帧卡帧（expectEndTime < actualEndTime为异常）
    - flag = 2: 数据不需要绘制（空帧，本分析器专门分析此类帧）
    - flag = 3: rs进程与app进程起止异常（|expRsStartTime - expUiEndTime| < 1ms 正常，否则异常）
    """

    def __init__(self, debug_vsync_enabled: bool = False, cache_manager: FrameCacheManager = None):
        """
        初始化统一空刷帧分析器

        Args:
            debug_vsync_enabled: VSync调试开关
            cache_manager: 缓存管理器实例
        """
        self.cache_manager = cache_manager
        self.load_calculator = FrameLoadCalculator(debug_vsync_enabled, cache_manager)
        
        # 使用公共模块（模块化重构）
        self.cpu_calculator = EmptyFrameCPUCalculator(cache_manager)
        self.callchain_analyzer = EmptyFrameCallchainAnalyzer(cache_manager)
        self.result_builder = EmptyFrameResultBuilder(cache_manager)
        
        # 检测方法开关
        self.direct_detection_enabled = True  # 正向检测（flag=2）
        self.rs_traced_detection_enabled = True  # 反向追溯（RS skip）
        
        # 算法升级开关
        self.false_positive_filter_enabled = True  # 默认启用假阳性过滤
        self.wakeup_chain_enabled = True  # 默认启用唤醒链分析（只对Top N帧）
        
        # RS Skip追溯配置
        self.rs_api_enabled = True  # 是否启用RS系统API追溯
        self.nw_api_enabled = True  # 是否启用NativeWindow API追溯
        self.top_n = 10  # Top N帧数量

    def analyze_empty_frames(self) -> Optional[dict]:
        """分析空刷帧（统一方法：正向检测 + 反向追溯）

        检测方法：
        1. 正向检测：flag=2 帧（direct detection）
        2. 反向追溯：RS skip → app frame（RS traced）

        返回:
        - dict，包含统一的分析结果
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
            # ========== 方法1：正向检测（Direct Detection）==========
            direct_frames_df = pd.DataFrame()
            direct_frames_count = 0
            
            if self.direct_detection_enabled:
                # 阶段1A：加载flag=2帧
                trace_df, total_load, perf_df = self._load_empty_frame_data(app_pids, timing_stats)
                
                if not trace_df.empty:
                    # 假阳性过滤
                    if self.false_positive_filter_enabled:
                        filter_start = time.time()
                        trace_df = self._filter_false_positives(trace_df, trace_conn)
                        timing_stats['false_positive_filter'] = time.time() - filter_start
                        logging.info('假阳性过滤耗时: %.3f秒', timing_stats['false_positive_filter'])
                    
                    if not trace_df.empty:
                        direct_frames_df = trace_df
                        direct_frames_count = len(trace_df)
                        logging.info('正向检测到 %d 个空刷帧', direct_frames_count)
            
            # ========== 方法2：反向追溯（RS Traced）==========
            rs_traced_results = []
            rs_traced_count = 0
            rs_skip_cpu = 0
            
            if self.rs_traced_detection_enabled:
                # 阶段1B：检测RS skip事件并追溯
                rs_skip_frames = self._detect_rs_skip_frames(trace_conn, timing_stats)
                
                if rs_skip_frames:
                    logging.info('检测到 %d 个RS skip帧', len(rs_skip_frames))
                    
                    # 计算RS进程CPU
                    if perf_conn:
                        rs_cpu_start = time.time()
                        rs_skip_cpu = self._calculate_rs_skip_cpu(rs_skip_frames)
                        timing_stats['rs_cpu_calculation'] = time.time() - rs_cpu_start
                    
                    # 预加载缓存并追溯到应用帧
                    caches = self._preload_rs_caches(trace_conn, rs_skip_frames, timing_stats)
                    rs_traced_results = self._trace_rs_to_app_frames(
                        trace_conn, perf_conn, rs_skip_frames, caches, timing_stats
                    )
                    
                    # 统计追溯成功数
                    rs_traced_count = sum(
                        1 for r in rs_traced_results 
                        if r.get('trace_result') and r['trace_result'].get('app_frame')
                    )
                    logging.info('反向追溯成功 %d 个空刷帧', rs_traced_count)
            
            # ========== 合并检测结果 ==========
            # 如果两种方法都没有检测到帧，返回空结果
            if direct_frames_count == 0 and rs_traced_count == 0:
                logging.info('未检测到空刷帧，返回空结果')
                return self._build_empty_result_unified(total_load, timing_stats, rs_skip_cpu)
            
            # 阶段2：合并并去重
            merge_start = time.time()
            all_frames_df, detection_stats = self._merge_and_deduplicate_frames(
                direct_frames_df, rs_traced_results, timing_stats
            )
            timing_stats['merge_deduplicate'] = time.time() - merge_start
            logging.info('帧合并去重完成: 正向%d + 反向%d → 总计%d（去重后）', 
                        direct_frames_count, rs_traced_count, len(all_frames_df))
            
            # 阶段3：数据预处理
            self._prepare_frame_data(all_frames_df, timing_stats)
            
            # 阶段4：CPU计算（统一）
            # 确保perf_df已加载（如果为空或未定义，重新获取）
            if 'perf_df' not in locals() or perf_df is None or perf_df.empty:
                perf_load_start = time.time()
                perf_df = self.cache_manager.get_perf_samples()
                timing_stats['perf_reload'] = time.time() - perf_load_start
                if timing_stats.get('perf_reload', 0) > 0.1:  # 如果耗时超过0.1秒，记录日志
                    logging.info('重新加载perf数据耗时: %.3f秒', timing_stats['perf_reload'])
            frame_loads = self._calculate_frame_loads(all_frames_df, perf_df, timing_stats)

            # 阶段5：Top帧调用链分析
            self._analyze_top_frames_callchains(frame_loads, all_frames_df, perf_df, perf_conn, timing_stats)
            
            # 阶段6：Top帧唤醒链分析
            if self.wakeup_chain_enabled:
                wakeup_start = time.time()
                self._analyze_top_frames_wakeup_chain(frame_loads, all_frames_df, trace_conn)
                timing_stats['wakeup_chain'] = time.time() - wakeup_start

            # 阶段7：结果构建（统一格式）
            result = self._build_result_unified(
                frame_loads, all_frames_df, total_load, timing_stats, 
                detection_stats, rs_skip_cpu, rs_traced_results
            )

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
        # 使用公共模块EmptyFrameCPUCalculator
        frame_loads = self.cpu_calculator.calculate_frame_loads(trace_df, perf_df)
        timing_stats['fast_calc'] = time.time() - fast_calc_start
        return frame_loads

    def _analyze_top_frames_callchains(
        self, frame_loads: list, trace_df: pd.DataFrame, perf_df: pd.DataFrame, perf_conn, timing_stats: dict
    ) -> None:
        """识别Top帧并进行调用链分析（使用公共模块）

        Args:
            frame_loads: 帧负载数据列表
            trace_df: 帧数据DataFrame
            perf_df: 性能数据DataFrame
            perf_conn: perf数据库连接
            timing_stats: 耗时统计字典，函数内部会设置相关时间值
        """
        top_analysis_start = time.time()

        # 使用公共模块EmptyFrameCallchainAnalyzer
        self.callchain_analyzer.analyze_callchains(
            frame_loads=frame_loads,
            trace_df=trace_df,
            perf_df=perf_df,
            perf_conn=perf_conn,
            top_n=TOP_FRAMES_FOR_CALLCHAIN
        )

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
        """构建分析结果（使用公共模块）

        Args:
            frame_loads: 帧负载数据列表
            trace_df: 帧数据DataFrame
            total_load: 总负载
            timing_stats: 耗时统计字典，函数内部会设置相关时间值

        Returns:
            dict: 分析结果
        """
        result_build_start = time.time()
        
        # 使用公共模块EmptyFrameResultBuilder
        result = self.result_builder.build_result(
            frame_loads=frame_loads,
            total_load=total_load,
            detection_stats=None  # EmptyFrameAnalyzer无追溯统计
        )
        
        timing_stats['result_build'] = time.time() - result_build_start
        return result
    
    def _build_result_old(self, frame_loads: list, trace_df: pd.DataFrame, total_load: int, timing_stats: dict) -> dict:
        """构建分析结果（旧实现，保留作为参考）

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
            frame: 帧数据（DataFrame行或字典）
            trace_conn: trace数据库连接
        
        Returns:
            线程列表
        """
        try:
            from .frame_wakeup_chain import find_wakeup_chain
        except ImportError:
            # 如果导入失败，返回空列表（唤醒链分析是可选的）
            logging.warning('无法导入wakeup_chain，跳过唤醒链分析')
            return []
        
        # 处理itid：如果不存在，尝试从tid查询
        frame_itid = frame.get('itid')
        if not frame_itid and trace_conn:
            tid = frame.get('tid')
            if tid:
                try:
                    cursor = trace_conn.cursor()
                    cursor.execute("SELECT itid FROM thread WHERE tid = ? LIMIT 1", (tid,))
                    result = cursor.fetchone()
                    if result:
                        frame_itid = result[0]
                except Exception:
                    pass
        
        if not frame_itid:
            # 如果仍然没有itid，跳过唤醒链分析
            logging.warning('帧缺少itid字段，跳过唤醒链分析: ts=%s', frame.get('ts'))
            return []
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
    
    # ==================== RS Skip 检测方法（合并功能）====================
    
    def _detect_rs_skip_frames(self, trace_conn, timing_stats: dict) -> list:
        """检测RS skip事件并分组到帧
        
        Args:
            trace_conn: trace数据库连接
            timing_stats: 耗时统计字典
        
        Returns:
            list: RS skip帧列表（每个帧可能包含多个skip事件）
        """
        detect_start = time.time()
        
        try:
            cursor = trace_conn.cursor()
            
            # 步骤1: 查找所有DisplayNode skip事件
            skip_events_query = """
            SELECT 
                c.callid,
                c.ts,
                c.dur,
                c.name
            FROM callstack c
            WHERE c.name LIKE '%DisplayNode skip%'
            AND c.callid IN (
                SELECT t.id
                FROM thread t
                WHERE t.ipid IN (
                    SELECT p.ipid
                    FROM process p
                    WHERE p.name = 'render_service'
                )
            )
            ORDER BY c.ts
            """
            cursor.execute(skip_events_query)
            skip_events = cursor.fetchall()
            
            if not skip_events:
                logging.info('未找到DisplayNode skip事件')
                timing_stats['detect_rs_skip'] = time.time() - detect_start
                return []
            
            logging.info('找到 %d 个DisplayNode skip事件', len(skip_events))
            
            # 步骤2: 获取RS进程的所有帧
            rs_frames_query = """
            SELECT 
                fs.rowid,
                fs.ts,
                fs.dur,
                fs.vsync,
                fs.flag,
                fs.type
            FROM frame_slice fs
            WHERE fs.ipid IN (
                SELECT p.ipid
                FROM process p
                WHERE p.name = 'render_service'
            )
            AND fs.type = 0
            AND fs.flag IS NOT NULL
            ORDER BY fs.ts
            """
            cursor.execute(rs_frames_query)
            rs_frames = cursor.fetchall()
            
            if not rs_frames:
                logging.warning('未找到RS进程的帧')
                timing_stats['detect_rs_skip'] = time.time() - detect_start
                return []
            
            logging.info('找到 %d 个RS进程帧', len(rs_frames))
            
            # 步骤3: 将skip事件分配到对应的RS帧
            skip_frame_dict = {}
            
            for frame_data in rs_frames:
                frame_id, frame_ts, frame_dur, frame_vsync, frame_flag, frame_type = frame_data
                frame_dur = frame_dur if frame_dur else 0
                frame_end = frame_ts + frame_dur
                
                # 查找此帧时间窗口内的skip事件
                frame_skip_events = []
                for event in skip_events:
                    event_callid, event_ts, event_dur, event_name = event
                    if frame_ts <= event_ts < frame_end:
                        frame_skip_events.append({
                            'callid': event_callid,
                            'ts': event_ts,
                            'dur': event_dur if event_dur else 0,
                            'name': event_name
                        })
                
                # 如果此帧有skip事件，记录
                if frame_skip_events:
                    skip_frame_dict[frame_id] = {
                        'frame_id': frame_id,
                        'ts': frame_ts,
                        'dur': frame_dur,
                        'vsync': frame_vsync,
                        'flag': frame_flag,
                        'type': frame_type,
                        'skip_events': frame_skip_events,
                        'skip_event_count': len(frame_skip_events)
                    }
            
            result = list(skip_frame_dict.values())
            
            logging.info('检测完成: %d 个RS帧包含skip事件（共%d个skip事件）', 
                        len(result), len(skip_events))
            
            timing_stats['detect_rs_skip'] = time.time() - detect_start
            return result
            
        except Exception as e:
            logging.error('检测RS skip帧失败: %s', str(e))
            logging.error('异常堆栈跟踪:\n%s', traceback.format_exc())
            timing_stats['detect_rs_skip'] = time.time() - detect_start
            return []
    
    def _get_rs_process_pid(self) -> int:
        """获取RS进程PID"""
        try:
            cursor = self.cache_manager.trace_conn.cursor()
            cursor.execute("""
                SELECT pid FROM process 
                WHERE name LIKE '%render_service%' 
                LIMIT 1
            """)
            result = cursor.fetchone()
            return result[0] if result else 0
        except Exception as e:
            logging.error('获取RS进程PID失败: %s', e)
            return 0
    
    def _calculate_rs_skip_cpu(self, skip_frames: list) -> int:
        """计算RS进程skip帧的CPU浪费"""
        if not skip_frames:
            return 0
        
        rs_pid = self._get_rs_process_pid()
        if not rs_pid:
            logging.warning('无法获取RS进程PID，跳过RS进程CPU计算')
            return 0
        
        total_rs_cpu = 0
        calculated_count = 0
        
        for skip_frame in skip_frames:
            frame_start = skip_frame['ts']
            frame_dur = skip_frame.get('dur', 0) or 16_666_666  # 默认16.67ms
            frame_end = frame_start + frame_dur
            
            try:
                app_instructions, system_instructions = calculate_process_instructions(
                    perf_conn=self.cache_manager.perf_conn,
                    trace_conn=self.cache_manager.trace_conn,
                    app_pid=rs_pid,
                    frame_start=frame_start,
                    frame_end=frame_end
                )
                if app_instructions > 0:
                    total_rs_cpu += app_instructions
                    calculated_count += 1
            except Exception as e:
                logging.warning('计算RS skip帧CPU失败: frame_id=%s, error=%s', 
                              skip_frame.get("frame_id"), e)
        
        logging.info('RS进程CPU统计: %d个skip帧, 成功计算%d个, 总CPU=%d 指令',
                    len(skip_frames), calculated_count, total_rs_cpu)
        return total_rs_cpu
    
    def _preload_rs_caches(self, trace_conn, skip_frames: list, timing_stats: dict) -> dict:
        """预加载RS追溯需要的缓存"""
        if not skip_frames:
            return {}
        
        preload_start = time.time()
        min_ts = min(f['ts'] for f in skip_frames) - 500_000_000
        max_ts = max(f['ts'] + f['dur'] for f in skip_frames) + 50_000_000
        
        caches = {}
        
        if self.rs_api_enabled:
            try:
                caches['rs_api'] = preload_rs_api_caches(trace_conn, min_ts, max_ts)
            except Exception as e:
                logging.error('加载RS API缓存失败: %s', e)
                caches['rs_api'] = None
        
        if self.nw_api_enabled:
            try:
                caches['nw'] = preload_nw_caches(trace_conn, min_ts, max_ts)
            except Exception as e:
                logging.error('加载NativeWindow API缓存失败: %s', e)
                caches['nw'] = None
        
        timing_stats['preload_rs_caches'] = time.time() - preload_start
        return caches
    
    def _trace_rs_to_app_frames(self, trace_conn, perf_conn, skip_frames: list,
                                 caches: dict, timing_stats: dict) -> list:
        """追溯RS skip事件到应用帧"""
        trace_start = time.time()
        traced_results = []
        rs_success = 0
        nw_success = 0
        failed = 0
        
        for skip_frame in skip_frames:
            rs_frame_id = skip_frame.get('frame_id')
            trace_result = None
            trace_method = None
            
            # 尝试RS API追溯
            if self.rs_api_enabled and caches.get('rs_api'):
                try:
                    trace_result = trace_rs_api(
                        trace_conn, rs_frame_id,
                        caches=caches['rs_api'],
                        perf_conn=perf_conn
                    )
                    if trace_result and trace_result.get('app_frame'):
                        trace_method = 'rs_api'
                        rs_success += 1
                except Exception as e:
                    logging.warning('RS API追溯失败: frame_id=%s, error=%s', rs_frame_id, e)
            
            # 如果RS API失败，尝试NativeWindow API
            if not trace_method and self.nw_api_enabled and caches.get('nw'):
                try:
                    trace_result = trace_nw_api(
                        trace_conn, rs_frame_id,
                        nativewindow_events_cache=caches['nw'].get('nativewindow_events'),
                        app_frames_cache=caches['nw'].get('app_frames'),
                        tid_to_info_cache=caches['nw'].get('tid_to_info'),
                        perf_conn=perf_conn
                    )
                    if trace_result and trace_result.get('app_frame'):
                        trace_method = 'nw_api'
                        nw_success += 1
                except Exception as e:
                    logging.warning('NativeWindow API追溯失败: frame_id=%s, error=%s', rs_frame_id, e)
            
            if not trace_method:
                failed += 1
            
            traced_results.append({
                'rs_frame': skip_frame,
                'trace_result': trace_result,
                'trace_method': trace_method
            })
        
        timing_stats['trace_rs_to_app'] = time.time() - trace_start
        logging.info('RS追溯完成: RS API成功%d, NW API成功%d, 失败%d',
                    rs_success, nw_success, failed)
        
        return traced_results
    
    def _merge_and_deduplicate_frames(self, direct_frames_df: pd.DataFrame, 
                                       rs_traced_results: list,
                                       timing_stats: dict) -> tuple:
        """合并并去重空刷帧（核心方法）
        
        Args:
            direct_frames_df: 正向检测的flag=2帧
            rs_traced_results: RS skip追溯结果
            timing_stats: 耗时统计字典
        
        Returns:
            tuple: (合并后的DataFrame, 检测统计信息)
        """
        trace_conn = self.cache_manager.trace_conn
        """合并并去重空刷帧（核心方法）
        
        Args:
            direct_frames_df: 正向检测的flag=2帧
            rs_traced_results: RS skip追溯结果
            timing_stats: 耗时统计字典
        
        Returns:
            tuple: (合并后的DataFrame, 检测统计信息)
        """
        frame_map = {}  # key: (pid, ts, vsync)
        detection_stats = {
            'direct_only': 0,
            'rs_traced_only': 0,
            'both': 0,
            'total_rs_skip_events': len(rs_traced_results)
        }
        
        # 1. 处理正向检测的帧
        for _, row in direct_frames_df.iterrows():
            key = (row['pid'], row['ts'], row['vsync'])
            frame_map[key] = {
                'ts': row['ts'],
                'dur': row['dur'],
                'vsync': row['vsync'],
                'pid': row['pid'],
                'tid': row['tid'],
                'process_name': row['process_name'],
                'thread_name': row['thread_name'],
                'flag': row['flag'],
                'type': row.get('type', 0),
                'is_main_thread': row.get('is_main_thread', 0),
                'callstack_id': row.get('callstack_id'),
                'detection_method': 'direct',
                'traced_count': 0,
                'rs_skip_events': [],
                'trace_method': None
            }
        
        detection_stats['direct_only'] = len(frame_map)
        
        # 2. 处理RS traced帧
        for trace_result_wrapper in rs_traced_results:
            trace_result = trace_result_wrapper.get('trace_result')
            if not trace_result or not trace_result.get('app_frame'):
                continue
            
            app_frame = trace_result['app_frame']
            rs_frame = trace_result_wrapper['rs_frame']
            trace_method = trace_result_wrapper.get('trace_method')
            
            # 构建key（注意：backtrack返回的字段名是frame_ts, frame_dur, frame_vsync）
            key = (
                app_frame.get('app_pid') or app_frame.get('process_pid') or app_frame.get('pid'),
                app_frame.get('frame_ts') or app_frame.get('ts'),
                app_frame.get('frame_vsync') or app_frame.get('vsync')
            )
            
            if key in frame_map:
                # 已存在：更新为both
                if frame_map[key]['detection_method'] == 'direct':
                    frame_map[key]['detection_method'] = 'both'
                    detection_stats['direct_only'] -= 1
                    detection_stats['both'] += 1
                
                frame_map[key]['traced_count'] += 1
                frame_map[key]['rs_skip_events'].append(rs_frame)
                if not frame_map[key]['trace_method']:
                    frame_map[key]['trace_method'] = trace_method
            else:
                # 新帧：添加为rs_traced（注意字段名映射）
                # 需要查询itid（唤醒链分析需要）
                tid = app_frame.get('thread_id') or app_frame.get('tid')
                itid = None
                if tid and trace_conn:
                    try:
                        cursor = trace_conn.cursor()
                        cursor.execute("""
                            SELECT itid FROM thread WHERE tid = ? LIMIT 1
                        """, (tid,))
                        result = cursor.fetchone()
                        if result:
                            itid = result[0]
                    except Exception as e:
                        logging.warning('查询itid失败: tid=%s, error=%s', tid, e)
                
                frame_map[key] = {
                    'ts': app_frame.get('frame_ts') or app_frame.get('ts'),
                    'dur': app_frame.get('frame_dur') or app_frame.get('dur'),
                    'vsync': app_frame.get('frame_vsync') or app_frame.get('vsync'),
                    'pid': app_frame.get('app_pid') or app_frame.get('process_pid') or app_frame.get('pid'),
                    'tid': tid,
                    'itid': itid,  # 添加itid字段（唤醒链分析需要）
                    'process_name': app_frame.get('process_name', ''),
                    'thread_name': app_frame.get('thread_name', ''),
                    'flag': app_frame.get('frame_flag') or app_frame.get('flag', 2),  # 空刷帧标记
                    'type': 0,
                    'is_main_thread': app_frame.get('is_main_thread', 0),
                    'callstack_id': app_frame.get('callstack_id'),
                    'detection_method': 'rs_traced',
                    'traced_count': 1,
                    'rs_skip_events': [rs_frame],
                    'trace_method': trace_method
                }
                detection_stats['rs_traced_only'] += 1
        
        # 3. 转换为DataFrame
        if frame_map:
            merged_df = pd.DataFrame(list(frame_map.values()))
        else:
            merged_df = pd.DataFrame()
        
        # 统计信息
        logging.info('帧合并统计: 仅正向=%d, 仅反向=%d, 重叠=%d, 总计=%d',
                    detection_stats['direct_only'],
                    detection_stats['rs_traced_only'],
                    detection_stats['both'],
                    len(merged_df))
        
        return merged_df, detection_stats
    
    def _build_result_unified(self, frame_loads: list, trace_df: pd.DataFrame,
                             total_load: int, timing_stats: dict,
                             detection_stats: dict, rs_skip_cpu: int,
                             rs_traced_results: list) -> dict:
        """构建统一的分析结果（包含检测方法统计）
        
        Args:
            frame_loads: 帧负载数据
            trace_df: 帧数据DataFrame
            total_load: 总负载
            timing_stats: 耗时统计
            detection_stats: 检测方法统计
            rs_skip_cpu: RS进程CPU浪费
            rs_traced_results: RS追溯结果（用于统计）
        
        Returns:
            dict: 统一的分析结果
        """
        # 使用公共模块构建基础结果
        base_result = self.result_builder.build_result(
            frame_loads=frame_loads,
            total_load=total_load,
            detection_stats=detection_stats  # 传递检测统计信息
        )
        
        # 添加timing_stats（如果结果中没有）
        if 'timing_stats' not in base_result:
            base_result['timing_stats'] = timing_stats
        
        # 增强summary：添加检测方法统计
        if base_result and 'summary' in base_result:
            summary = base_result['summary']
            
            # 添加检测方法分解
            summary['detection_breakdown'] = {
                'direct_only': detection_stats['direct_only'],
                'rs_traced_only': detection_stats['rs_traced_only'],
                'both': detection_stats['both']
            }
            
            # 添加RS追溯统计
            total_skip_events = detection_stats.get('total_rs_skip_events', 0)
            total_skip_frames = len([r for r in rs_traced_results if r.get('rs_frame')])
            traced_success = sum(
                1 for r in rs_traced_results 
                if r.get('trace_result') and r['trace_result'].get('app_frame')
            )
            rs_api_success = sum(
                1 for r in rs_traced_results 
                if r.get('trace_method') == 'rs_api'
            )
            nw_api_success = sum(
                1 for r in rs_traced_results 
                if r.get('trace_method') == 'nw_api'
            )
            
            summary['rs_trace_stats'] = {
                'total_skip_events': total_skip_events,
                'total_skip_frames': total_skip_frames,
                'traced_success_count': traced_success,
                'trace_accuracy': (traced_success / total_skip_frames * 100) if total_skip_frames > 0 else 0.0,
                'rs_api_success': rs_api_success,
                'nativewindow_success': nw_api_success,
                'failed': total_skip_frames - traced_success,
                'rs_skip_cpu': rs_skip_cpu
            }
            
            # 添加traced_count统计
            if frame_loads:
                multi_traced_frames = [f for f in frame_loads if f.get('traced_count', 0) > 1]
                max_traced = max((f.get('traced_count', 0) for f in frame_loads), default=0)
                
                summary['traced_count_stats'] = {
                    'frames_traced_multiple_times': len(multi_traced_frames),
                    'max_traced_count': max_traced
                }
        
        return base_result
    
    def _build_empty_result_unified(self, total_load: int, timing_stats: dict, 
                                    rs_skip_cpu: int) -> dict:
        """构建空结果（统一格式）"""
        return {
            'status': 'success',
            'summary': {
                'total_empty_frames': 0,
                'empty_frame_load': 0,
                'empty_frame_percentage': 0.0,
                'total_load': total_load,
                'severity_level': 'normal',
                'severity_description': '正常：未检测到空刷帧',
                'detection_breakdown': {
                    'direct_only': 0,
                    'rs_traced_only': 0,
                    'both': 0
                },
                'rs_trace_stats': {
                    'total_skip_events': 0,
                    'total_skip_frames': 0,
                    'traced_success_count': 0,
                    'trace_accuracy': 0.0,
                    'rs_api_success': 0,
                    'nativewindow_success': 0,
                    'failed': 0,
                    'rs_skip_cpu': rs_skip_cpu
                }
            },
            'top_frames': {
                'main_thread_empty_frames': [],
                'background_thread': []
            },
            'timing_stats': timing_stats
        }
