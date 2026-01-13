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
from bisect import bisect_left
from collections import defaultdict
from typing import Optional

import pandas as pd

from .frame_constants import TOP_FRAMES_FOR_CALLCHAIN
from .frame_core_cache_manager import FrameCacheManager
from .frame_core_load_calculator import FrameLoadCalculator
from .frame_empty_common import (
    EmptyFrameCallchainAnalyzer,
    EmptyFrameCPUCalculator,
    EmptyFrameResultBuilder,
    calculate_process_instructions,
)
from .frame_empty_framework_specific import detect_framework_specific_empty_frames
from .frame_rs_skip_backtrack_api import (
    preload_caches as preload_rs_api_caches,
)
from .frame_rs_skip_backtrack_api import (
    trace_rs_skip_to_app_frame as trace_rs_api,
)
from .frame_rs_skip_backtrack_nw import (
    preload_caches as preload_nw_caches,
)
from .frame_rs_skip_backtrack_nw import (
    trace_rs_skip_to_app_frame as trace_nw_api,
)
from .frame_time_utils import FrameTimeUtils
from .frame_utils import is_system_thread


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
        self.framework_detection_enabled = True  # 框架特定检测（Flutter/RN等）

        # 算法升级开关
        self.false_positive_filter_enabled = True  # 默认启用假阳性过滤
        self.wakeup_chain_enabled = True  # 默认启用唤醒链分析（只对Top N帧）

        # RS Skip追溯配置
        self.rs_api_enabled = True  # 是否启用RS系统API追溯
        self.nw_api_enabled = True  # 是否启用NativeWindow API追溯
        self.top_n = 10  # Top N帧数量

        # 框架特定检测配置
        self.framework_types = ['flutter']  # 支持的框架类型

        # 三个检测器的原始检测数量（在合并去重之前，不处理 overlap）
        self.direct_detected_count = 0  # flag=2 检测器的原始检测数量
        self.rs_detected_count = 0  # RS skip 检测器的原始检测数量
        self.framework_detected_counts = {}  # 框架特定检测器的原始检测数量

    def analyze_empty_frames(self) -> Optional[dict]:
        """分析空刷帧（统一方法：正向检测 + 反向追溯）

        三个核心阶段：
        1. 找到空刷的帧：通过正向检测（flag=2）和反向追溯（RS skip → app frame）
        2. 算出帧的浪费的进程级别的cpu指令数：
           - 2.1 计算每个空刷帧在[ts, ts+dur]时间范围内的CPU浪费（进程级别）
           - 2.2 分析Top N帧的调用链，定位CPU浪费的具体代码路径
        3. 统计整个trace浪费指令数占比：empty_frame_load / total_load * 100

        检测方法：
        1. 正向检测：flag=2 帧（direct detection）
        2. 反向追溯：RS skip → app frame（RS traced）
        3. 框架特定检测：Flutter/RN 等框架的空刷检测（framework specific）

        返回:
        - dict，包含统一的分析结果
        """
        # 从cache_manager获取数据库连接和参数
        trace_conn = self.cache_manager.trace_conn
        perf_conn = self.cache_manager.perf_conn
        app_pids = self.cache_manager.app_pids

        if not trace_conn or not perf_conn:
            # logging.error('数据库连接未建立')
            return None

        total_start_time = time.time()
        timing_stats = {}

        try:
            # ========== 方法1：正向检测（Direct Detection）==========
            direct_frames_df = pd.DataFrame()
            direct_frames_count = 0

            if self.direct_detection_enabled:
                # 阶段1A：加载flag=2帧
                trace_df, total_load, perf_df, merged_time_ranges = self._load_empty_frame_data(app_pids, timing_stats)

                # 保存原始 total_load（用于日志对比）
                timing_stats['original_total_load'] = total_load

                if not trace_df.empty:
                    # 假阳性过滤
                    if self.false_positive_filter_enabled:
                        filter_start = time.time()
                        trace_df = self._filter_false_positives(trace_df, trace_conn)
                        timing_stats['false_positive_filter'] = time.time() - filter_start
                        # logging.info('假阳性过滤耗时: %.3f秒', timing_stats['false_positive_filter'])

                    if not trace_df.empty:
                        direct_frames_df = trace_df
                        direct_frames_count = len(trace_df)
                        # 保存 flag=2 检测器的原始检测数量（第一次计算的位置）
                        self.direct_detected_count = direct_frames_count
                        # logging.info('正向检测到 %d 个空刷帧', direct_frames_count)

            # 方法2：反向追溯（RS Traced）
            rs_traced_results = []
            rs_traced_count = 0
            rs_skip_cpu = 0

            if self.rs_traced_detection_enabled:
                # 阶段1B：检测RS skip事件并追溯到应用帧（反向追溯）
                rs_skip_frames = self._detect_rs_skip_frames(trace_conn, timing_stats)

                if rs_skip_frames:
                    # logging.info('检测到 %d 个RS skip帧', len(rs_skip_frames))

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

                    # 保存 RS skip 检测器的原始检测数量（第一次计算的位置）
                    self.rs_detected_count = len(rs_traced_results) if rs_traced_results else 0

                    # 统计追溯成功数
                    rs_traced_count = sum(
                        1 for r in rs_traced_results if r.get('trace_result') and r['trace_result'].get('app_frame')
                    )
                    # logging.info('反向追溯成功 %d 个空刷帧', rs_traced_count)

            # 方法3：框架特定检测（Flutter/RN等）
            framework_frames_df = pd.DataFrame()
            framework_frames_count = 0

            if self.framework_detection_enabled:
                framework_start = time.time()
                framework_frames_df = detect_framework_specific_empty_frames(
                    trace_conn=trace_conn,
                    app_pids=app_pids,
                    framework_types=self.framework_types,
                    timing_stats=timing_stats,
                )
                framework_frames_count = len(framework_frames_df)
                # 保存框架特定检测器的原始检测数量（第一次计算的位置）
                self.framework_detected_counts = {}
                for framework_type in self.framework_types:
                    detected_count = timing_stats.get(f'{framework_type}_detected_count', 0)
                    self.framework_detected_counts[framework_type] = detected_count
                    if detected_count > 0:
                        logging.info(
                            f'{framework_type} 检测器原始检测结果：{detected_count} 个空刷帧（在合并去重之前）'
                        )
                if framework_frames_count > 0:
                    # logging.info('框架特定检测到 %d 个空刷帧', framework_frames_count)
                    pass

            # ========== 合并检测结果 ==========
            # 如果三种方法都没有检测到帧，返回空结果
            if direct_frames_count == 0 and rs_traced_count == 0 and framework_frames_count == 0:
                # logging.info('未检测到空刷帧，返回空结果')
                # 构建空的 detection_stats，包含三个检测器的原始检测结果
                empty_detection_stats = {
                    'direct_detected_count': self.direct_detected_count,
                    'rs_detected_count': self.rs_detected_count,
                    'framework_detected_counts': self.framework_detected_counts.copy()
                    if self.framework_detected_counts
                    else {},
                }
                return self._build_empty_result_unified(total_load, timing_stats, rs_skip_cpu, empty_detection_stats)

            # 阶段2：合并并去重
            merge_start = time.time()
            all_frames_df, detection_stats = self._merge_and_deduplicate_frames(
                direct_frames_df, rs_traced_results, framework_frames_df, timing_stats
            )
            timing_stats['merge_deduplicate'] = time.time() - merge_start

            # 将三个检测器的原始检测结果记录到 detection_stats 中（在合并去重之前，不处理 overlap）
            # 使用类属性中保存的值（在第一次计算的位置保存的）
            detection_stats['direct_detected_count'] = self.direct_detected_count
            detection_stats['rs_detected_count'] = self.rs_detected_count
            detection_stats['framework_detected_counts'] = (
                self.framework_detected_counts.copy() if self.framework_detected_counts else {}
            )

            logging.info(f'flag=2 检测器原始检测结果：{self.direct_detected_count} 个空刷帧（在合并去重之前）')
            logging.info(f'RS skip 检测器原始检测结果：{self.rs_detected_count} 个空刷帧（在合并去重之前）')
            for framework_type, detected_count in self.framework_detected_counts.items():
                logging.info(
                    f'{framework_type} 检测器原始检测结果：{detected_count} 个空刷帧（在合并去重之前，可能与 flag=2 或 RS skip 重叠）'
                )
            # logging.info('帧合并去重完成: 正向%d + 反向%d → 总计%d（去重后）',
            # direct_frames_count, rs_traced_count, len(all_frames_df))

            # 数据预处理
            self._prepare_frame_data(all_frames_df, timing_stats)

            # ========== 阶段2：算出帧的浪费的进程级别的CPU指令数 ==========
            # 2.1 计算每个空刷帧的CPU浪费（进程级别）
            # 确保perf_df已加载（如果为空或未定义，重新获取）
            if 'perf_df' not in locals() or perf_df is None or perf_df.empty:
                perf_load_start = time.time()
                perf_df = self.cache_manager.get_perf_samples()
                timing_stats['perf_reload'] = time.time() - perf_load_start
                if timing_stats.get('perf_reload', 0) > 0.1:  # 如果耗时超过0.1秒，记录日志
                    # logging.info('重新加载perf数据耗时: %.3f秒', timing_stats['perf_reload'])
                    pass
            frame_loads = self._calculate_frame_loads(all_frames_df, perf_df, timing_stats)

            # 2.2 分析Top N帧的调用链（核心功能，用于定位CPU浪费的具体代码路径）
            self._analyze_top_frames_callchains(frame_loads, all_frames_df, perf_df, perf_conn, timing_stats)

            # 唤醒链分析（辅助分析，用于理解线程唤醒关系）
            if self.wakeup_chain_enabled:
                wakeup_start = time.time()
                self._analyze_top_frames_wakeup_chain(frame_loads, all_frames_df, trace_conn)
                timing_stats['wakeup_chain'] = time.time() - wakeup_start

            # ========== 阶段3：统计整个trace浪费指令数占比 ==========
            # 在_build_result_unified中计算 empty_frame_percentage = empty_frame_load / total_load * 100
            result = self._build_result_unified(
                frame_loads,
                all_frames_df,
                total_load,
                timing_stats,
                detection_stats,
                rs_skip_cpu,
                rs_traced_results,
                merged_time_ranges,
            )

            # 总耗时统计
            total_time = time.time() - total_start_time
            self._log_analysis_complete(total_time, timing_stats)

            return result

        except Exception:
            # logging.error('分析空帧时发生异常: %s', str(e))
            # logging.error('异常堆栈跟踪:\n%s', traceback.format_exc())
            return None

    def _load_empty_frame_data(self, app_pids: list, timing_stats: dict) -> tuple:
        """加载空帧相关数据

        Args:
            app_pids: 应用进程ID列表
            timing_stats: 耗时统计字典，函数内部会设置相关时间值

        Returns:
            tuple: (trace_df, total_load, perf_df, merged_time_ranges)
                - trace_df: 空帧数据
                - total_load: 总负载
                - perf_df: 性能样本
                - merged_time_ranges: 去重后的时间范围列表
        """
        # 获取空帧数据和去重后的时间范围
        query_start = time.time()
        trace_df, merged_time_ranges = self.cache_manager.get_empty_frames_with_details(app_pids)
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

        return trace_df, total_load, perf_df, merged_time_ranges

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
        """阶段2.1：计算帧的浪费的进程级别的CPU指令数

        对于每个空刷帧，计算其在[ts, ts+dur]时间范围内（扩展±1ms）的进程级别CPU浪费。
        进程级别意味着统计该进程所有线程的CPU指令数，不区分具体线程。

        注意：调用链分析（阶段2.2）会在此基础上对Top N帧进行详细分析。

        Args:
            trace_df: 帧数据DataFrame（阶段1找到的空刷帧）
            perf_df: 性能数据DataFrame（perf_sample表数据）
            timing_stats: 耗时统计字典，函数内部会设置相关时间值

        Returns:
            list: 帧负载数据列表，每个元素包含frame_load字段（CPU指令数）
        """
        fast_calc_start = time.time()
        # 使用公共模块EmptyFrameCPUCalculator
        frame_loads = self.cpu_calculator.calculate_frame_loads(trace_df, perf_df)
        timing_stats['fast_calc'] = time.time() - fast_calc_start
        return frame_loads

    def _analyze_top_frames_callchains(
        self, frame_loads: list, trace_df: pd.DataFrame, perf_df: pd.DataFrame, perf_conn, timing_stats: dict
    ) -> None:
        """阶段2.2：分析Top N帧的调用链（核心功能）

        对Top N（默认10个）CPU浪费最高的空刷帧进行调用链分析，
        定位CPU浪费的具体代码路径，帮助开发者找到优化点。

        Args:
            frame_loads: 帧负载数据列表（已计算CPU浪费）
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
            top_n=TOP_FRAMES_FOR_CALLCHAIN,
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
            'top_frames': [],  # 统一列表，不再区分主线程和后台线程
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
            detection_stats=None,  # EmptyFrameAnalyzer无追溯统计
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
            severity_level = 'normal'
            severity_description = '正常：空刷帧CPU占比小于3%，属于正常范围。'
        elif empty_frame_percentage < 10.0:
            severity_level = 'moderate'
            severity_description = '较为严重：空刷帧CPU占比在3%-10%之间，建议关注并优化。'
        elif empty_frame_percentage <= 100.0:
            severity_level = 'severe'
            severity_description = '严重：空刷帧CPU占比超过10%，需要优先优化。'
        else:  # > 100%
            severity_level = 'extreme'
            severity_description = (
                f'极端异常：空刷帧CPU占比超过100% ({empty_frame_percentage:.2f}%)。'
                f'这是因为时间窗口扩展（±1ms）导致多个帧的CPU计算存在重叠。'
                f'这是正常的设计，不影响单个帧的CPU计算准确性。'
                f'建议查看原始占比值（empty_frame_percentage）和警告信息（percentage_warning）了解详情。'
            )
            percentage_warning = (
                f'注意：空刷帧占比超过100% ({empty_frame_percentage:.2f}%)，这是因为时间窗口扩展（±1ms）'
                f'导致多个帧的CPU计算存在重叠。这是正常的设计，不影响单个帧的CPU计算准确性。'
            )
            # logging.warning(percentage_warning)

            # 如果启用限制，将显示占比限制为100%
            if LIMIT_DISPLAY_PERCENTAGE:
                display_percentage = 100.0
                # logging.info(f"显示占比已限制为100%（原始占比：{empty_frame_percentage:.2f}%）")

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
                'empty_frames_with_load': int(
                    len([f for f in frame_loads if f.get('frame_load', 0) > 0])
                ),  # 有CPU负载的空刷帧数量
                # 严重程度评估
                'severity_level': severity_level,  # 严重程度级别：normal, moderate, severe, extreme
                'severity_description': severity_description,  # 严重程度说明
            },
            'top_frames': processed_main_thread_frames
            + processed_bg_thread_frames,  # 统一列表，不再区分主线程和后台线程
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
        # logging.info('空帧分析总耗时: %.3f秒', total_time)
        # logging.info(
        # '各阶段耗时占比: '
        # '缓存检查%.1f%%, '
        # '查询%.1f%%, '
        # '总负载%.1f%%, '
        # '性能样本%.1f%%, '
        # '假阳性过滤%.1f%%, '
        # '预处理%.1f%%, '
        # '快速计算%.1f%%, '
        # 'Top帧分析%.1f%%, '
        # '唤醒链分析%.1f%%, '
        # '结果构建%.1f%%',
        # timing_stats.get('cache_check', 0) / total_time * 100 if total_time > 0 else 0,
        # timing_stats.get('query', 0) / total_time * 100 if total_time > 0 else 0,
        # timing_stats.get('total_load', 0) / total_time * 100 if total_time > 0 else 0,
        # timing_stats.get('perf', 0) / total_time * 100 if total_time > 0 else 0,
        # timing_stats.get('false_positive_filter', 0) / total_time * 100 if total_time > 0 else 0,
        # timing_stats.get('data_prep', 0) / total_time * 100 if total_time > 0 else 0,
        # timing_stats.get('fast_calc', 0) / total_time * 100 if total_time > 0 else 0,
        # timing_stats.get('top_analysis', 0) / total_time * 100 if total_time > 0 else 0,
        # timing_stats.get('wakeup_chain', 0) / total_time * 100 if total_time > 0 else 0,
        # timing_stats.get('result_build', 0) / total_time * 100 if total_time > 0 else 0,
        # )

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
            # logging.warning('所有帧的dur都为NaN，无法计算时间范围')
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
        nw_events_cache = defaultdict(list)
        for itid, ts in nw_records:
            nw_events_cache[itid].append(ts)

        # 排序以便二分查找
        for itid in nw_events_cache:
            nw_events_cache[itid].sort()

        # logging.info(f'预加载NativeWindow API事件: {len(nw_records)}条记录, {len(nw_events_cache)}个线程')

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
            except Exception:
                # 如果检查过程中出现异常，记录日志但不标记为假阳性（保守策略）
                # logging.warning(f'假阳性检查异常: {e}, row={row.to_dict() if hasattr(row, "to_dict") else row}')
                return False

        # 标记假阳性
        false_positive_mask = trace_df.apply(is_false_positive, axis=1)
        false_positive_mask.sum()

        # 过滤假阳性
        return trace_df[~false_positive_mask].copy()

        # logging.info(
        # f'假阳性过滤: 过滤前={len(trace_df)}, 过滤后={len(filtered_df)}, '
        # f'假阳性={false_positive_count} ({false_positive_count/len(trace_df)*100:.1f}%)'
        # )

    def _analyze_top_frames_wakeup_chain(self, frame_loads: list, trace_df: pd.DataFrame, trace_conn) -> None:
        """对Top N帧进行唤醒链分析，填充wakeup_threads字段

        注意：
        - 只对Top N帧进行唤醒链分析（性能考虑）
        - CPU计算是进程级的，不需要唤醒链分析
        - 唤醒链分析仅用于填充wakeup_threads字段和根因分析

        Args:
            frame_loads: 帧负载数据列表
            trace_df: 帧数据DataFrame
            trace_conn: trace数据库连接
        """
        # 对所有空刷帧按frame_load排序，取Top N（不区分主线程和后台线程）
        # 但排除系统线程（系统线程不计入占比，也不应该分析唤醒链）
        non_system_frames = [
            f
            for f in frame_loads
            # 规则：由于frame_loads已经通过app_pids过滤，所有帧都属于应用进程
            # 因此，只排除进程名本身是系统进程的情况
            # 对于应用进程内的线程，即使名称像系统线程（如OS_VSyncThread），也不排除
            if not is_system_thread(f.get('process_name'), None)  # 只检查进程名
        ]
        sorted_frames = sorted(non_system_frames, key=lambda x: x['frame_load'], reverse=True)
        top_n_frames = sorted_frames[:TOP_FRAMES_FOR_CALLCHAIN]

        # logging.info(f'开始对Top {len(top_n_frames)}帧进行唤醒链分析...')

        # 只对Top N帧进行唤醒链分析
        for frame_data in top_n_frames:
            # 找到对应的原始帧数据
            # 优先使用vsync匹配（如果有vsync，一定能匹配到frame_slice中的帧）
            vsync = frame_data.get('vsync')
            matching_frames = pd.DataFrame()  # 初始化为空DataFrame

            # 确保vsync不是'unknown'字符串，并且trace_df中有vsync列
            if vsync is not None and vsync != 'unknown' and 'vsync' in trace_df.columns:
                try:
                    # 确保vsync是数值类型
                    vsync_value = int(vsync) if not isinstance(vsync, (int, float)) else vsync
                    # 使用vsync匹配（最可靠的方式）
                    trace_vsync = pd.to_numeric(trace_df['vsync'], errors='coerce')
                    frame_mask = trace_vsync == vsync_value
                    matching_frames = trace_df[frame_mask]
                    if not matching_frames.empty:
                        # logging.debug(f'唤醒链分析：使用vsync匹配成功: vsync={vsync_value}, ts={frame_data["ts"]}, 找到{len(matching_frames)}个匹配帧')
                        pass
                    else:
                        # logging.warning(f'唤醒链分析：vsync匹配失败: vsync={vsync_value}, ts={frame_data["ts"]}')
                        pass
                except (ValueError, TypeError):
                    # logging.warning(f'唤醒链分析：vsync类型转换失败: vsync={vsync}, error={e}, 使用备用匹配方式')
                    pass
                    matching_frames = pd.DataFrame()  # 重置为空

            # 如果vsync匹配失败，使用ts、dur、tid匹配
            if matching_frames.empty:
                frame_mask = (
                    (trace_df['ts'] == frame_data['ts'])
                    & (trace_df['dur'] == frame_data['dur'])
                    & (trace_df['tid'] == frame_data['thread_id'])
                )
                matching_frames = trace_df[frame_mask]

            if not matching_frames.empty:
                original_frame = matching_frames.iloc[0]
                # 确保original_frame转换为字典格式，包含所有必要字段
                frame_dict = original_frame.to_dict() if isinstance(original_frame, pd.Series) else original_frame

                # 确保有itid字段（唤醒链分析需要）
                # 检查itid是否存在且不是NaN（pandas的NaN值需要特殊处理）
                frame_itid_value = frame_dict.get('itid')
                # 检查itid是否为NaN或None
                if 'itid' not in frame_dict or frame_itid_value is None or pd.isna(frame_itid_value):
                    # 如果itid是NaN或不存在，尝试从tid查询
                    tid = frame_dict.get('tid')
                    if tid and pd.notna(tid) and trace_conn:
                        try:
                            cursor = trace_conn.cursor()
                            cursor.execute('SELECT id FROM thread WHERE tid = ? LIMIT 1', (int(tid),))
                            result = cursor.fetchone()
                            if result:
                                frame_dict['itid'] = result[0]
                                # logging.debug(f'通过tid查询到itid: tid={tid}, itid={result[0]}')
                        except Exception:
                            # logging.warning(f'查询itid失败: tid={tid}, error={e}')
                            pass
                else:
                    # 确保itid是整数类型（不是NaN）
                    frame_dict['itid'] = int(frame_itid_value)

                try:
                    # 调用简化的唤醒链分析（只获取线程列表，不计算CPU）
                    # logging.debug(f'开始唤醒链分析: ts={frame_data["ts"]}, tid={frame_data.get("thread_id")}, itid={frame_dict.get("itid")}, frame_dict keys={list(frame_dict.keys())[:10]}')
                    wakeup_threads = self._get_related_threads_simple(frame_dict, trace_conn)
                    frame_data['wakeup_threads'] = wakeup_threads if wakeup_threads else []
                    if not wakeup_threads:
                        # logging.warning(f'唤醒链分析结果为空: ts={frame_data["ts"]}, tid={frame_data.get("thread_id")}, itid={frame_dict.get("itid")}, frame_dict={frame_dict}')
                        pass
                    else:
                        # logging.info(f'唤醒链分析成功: ts={frame_data["ts"]}, 找到 {len(related_threads)} 个相关线程')
                        pass
                except Exception:
                    # logging.warning(f'唤醒链分析失败: ts={frame_data["ts"]}, error={e}, traceback={traceback.format_exc()}')
                    pass
                    frame_data['wakeup_threads'] = []
            else:
                # logging.warning(f'未找到匹配的原始帧（唤醒链）: ts={frame_data["ts"]}, dur={frame_data["dur"]}, '
                # f'thread_id={frame_data.get("thread_id")}, trace_df中有{len(trace_df)}帧')
                frame_data['wakeup_threads'] = []

        # 对于非Top N帧，设置空的wakeup_threads
        for frame_data in frame_loads:
            if 'wakeup_threads' not in frame_data:
                frame_data['wakeup_threads'] = []

        # logging.info(f'完成Top {len(top_n_frames)}帧的唤醒链分析')

    def _get_related_threads_simple(self, frame, trace_conn) -> list:
        """获取帧相关的线程列表（简化版唤醒链分析）

        Args:
            frame: 帧数据（DataFrame行或字典）
            trace_conn: trace数据库连接

        Returns:
            线程列表
        """
        try:
            from .frame_wakeup_chain import find_wakeup_chain  # noqa: PLC0415
        except ImportError:
            # 如果导入失败，返回空列表（唤醒链分析是可选的）
            # logging.warning('无法导入wakeup_chain，跳过唤醒链分析')
            return []

        # 处理itid：如果不存在，尝试从tid查询
        # 确保frame是字典格式
        if isinstance(frame, pd.Series):
            frame = frame.to_dict()

        frame_itid = frame.get('itid')
        frame.get('ts')
        frame.get('tid')

        # logging.debug(f'_get_related_threads_simple: 开始分析, ts={frame_ts}, tid={frame_tid}, itid={frame_itid}')

        # 检查itid是否为NaN或None（pandas的NaN值需要特殊处理）
        if 'itid' not in frame or frame_itid is None or pd.isna(frame_itid):
            # 如果itid是NaN或不存在，尝试从tid查询
            tid = frame.get('tid')
            if tid and pd.notna(tid) and trace_conn:
                try:
                    cursor = trace_conn.cursor()
                    cursor.execute('SELECT id FROM thread WHERE tid = ? LIMIT 1', (int(tid),))
                    result = cursor.fetchone()
                    if result:
                        frame_itid = result[0]
                        # logging.debug(f'_get_related_threads_simple: 通过tid查询到itid, tid={tid}, itid={frame_itid}')
                        pass
                except Exception:
                    # logging.warning(f'_get_related_threads_simple: 查询itid失败: tid={tid}, error={e}')
                    pass
        else:
            # 确保itid是整数类型（不是NaN）
            frame_itid = int(frame_itid)

        if not frame_itid or pd.isna(frame_itid):
            # 如果仍然没有itid，跳过唤醒链分析
            # logging.warning('帧缺少itid字段，跳过唤醒链分析: ts=%s, tid=%s', frame.get('ts'), frame.get('tid'))
            return []

        frame_start = frame.get('ts') or frame.get('start_time', 0)
        frame_dur = frame.get('dur', 0)
        frame_end = frame_start + frame_dur
        app_pid = frame.get('pid') or frame.get('app_pid')

        # logging.debug(f'_get_related_threads_simple: 调用find_wakeup_chain, itid={frame_itid}, frame_start={frame_start}, frame_end={frame_end}, app_pid={app_pid}')

        # 调用唤醒链分析
        try:
            related_itids_ordered = find_wakeup_chain(
                trace_conn=trace_conn,
                start_itid=frame_itid,
                frame_start=frame_start,
                frame_end=frame_end,
                app_pid=app_pid,
            )
            # related_itids_ordered 是 [(itid, depth), ...] 列表，按唤醒链顺序
            # logging.debug(f'_get_related_threads_simple: find_wakeup_chain返回 {len(related_itids_ordered)} 个线程')
        except Exception:
            # logging.warning(f'_get_related_threads_simple: find_wakeup_chain调用失败: error={e}')
            related_itids_ordered = []

        # 确保至少包含当前帧的线程（用户要求）
        related_itids_set = {itid for itid, _ in related_itids_ordered}
        if frame_itid and frame_itid not in related_itids_set:
            related_itids_ordered.insert(0, (frame_itid, 0))  # 插入到最前面，深度为0
            related_itids_set.add(frame_itid)
            # logging.debug(f'_get_related_threads_simple: 添加当前帧线程到related_itids, itid={frame_itid}')

        # 获取线程详细信息
        if not related_itids_ordered:
            # 即使唤醒链为空，也要返回当前帧的线程
            # logging.debug(f'_get_related_threads_simple: related_itids_ordered为空，尝试返回当前帧线程, itid={frame_itid}')
            if frame_itid:
                try:
                    cursor = trace_conn.cursor()
                    cursor.execute(
                        """
                        SELECT t.itid, t.tid, t.name, p.pid, p.name
                        FROM thread t
                        INNER JOIN process p ON t.ipid = p.ipid
                        WHERE t.itid = ?
                    """,
                        (frame_itid,),
                    )
                    result = cursor.fetchone()
                    if result:
                        itid, tid, thread_name, pid, process_name = result
                        # logging.debug(f'_get_related_threads_simple: 成功获取当前线程信息, itid={itid}, thread_name={thread_name}')
                        return [
                            {
                                'itid': itid,
                                'tid': tid,
                                'thread_name': thread_name,
                                'pid': pid,
                                'process_name': process_name,
                                'is_system_thread': is_system_thread(process_name, thread_name),
                            }
                        ]
                    # logging.warning(f'_get_related_threads_simple: 查询当前线程信息无结果, itid={frame_itid}')

                    pass
                except Exception:
                    # logging.warning(f'_get_related_threads_simple: 获取当前线程信息失败: itid={frame_itid}, error={e}')
                    pass
            # logging.warning(f'_get_related_threads_simple: 最终返回空列表, itid={frame_itid}')
            return []

        cursor = trace_conn.cursor()
        # 按唤醒链顺序提取 itid 列表
        itids_list = [itid for itid, _ in related_itids_ordered]
        placeholders = ','.join('?' * len(itids_list))

        # logging.debug(f'_get_related_threads_simple: 查询 {len(itids_list)} 个线程的详细信息')

        cursor.execute(
            f"""
            SELECT t.itid, t.tid, t.name, p.pid, p.name
            FROM thread t
            INNER JOIN process p ON t.ipid = p.ipid
            WHERE t.itid IN ({placeholders})
        """,
            itids_list,
        )

        thread_results = cursor.fetchall()

        # logging.debug(f'_get_related_threads_simple: 查询到 {len(thread_results)} 个线程结果')

        # 构建 itid 到线程信息的映射
        thread_info_map = {}
        for itid, tid, thread_name, pid, process_name in thread_results:
            thread_info_map[itid] = {
                'tid': tid,
                'thread_name': thread_name,
                'pid': pid,
                'process_name': process_name,
                'is_system_thread': is_system_thread(process_name, thread_name),
            }

        # 按唤醒链顺序构建结果列表
        # 注意：使用 thread_id 而不是 tid，以保持与 sample_callchains 中字段命名的一致性
        # thread_id 和 tid 在语义上相同，都是线程号（来自 thread.tid 或 perf_sample.thread_id）
        wakeup_threads = []
        for itid, depth in related_itids_ordered:
            if itid in thread_info_map:
                thread_info = thread_info_map[itid]
                wakeup_threads.append(
                    {
                        'itid': itid,
                        'thread_id': thread_info['tid'],  # 使用 thread_id 保持与 sample_callchains 一致
                        'thread_name': thread_info['thread_name'],
                        'pid': thread_info['pid'],
                        'process_name': thread_info['process_name'],
                        'is_system_thread': thread_info['is_system_thread'],
                        'wakeup_depth': depth,  # 添加唤醒链深度信息
                    }
                )

        # logging.debug(f'_get_related_threads_simple: 返回 {len(wakeup_threads)} 个唤醒链线程（按顺序）')
        return wakeup_threads

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
                # logging.info('未找到DisplayNode skip事件')
                timing_stats['detect_rs_skip'] = time.time() - detect_start
                return []

            # logging.info('找到 %d 个DisplayNode skip事件', len(skip_events))

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
                # logging.warning('未找到RS进程的帧')
                timing_stats['detect_rs_skip'] = time.time() - detect_start
                return []

            # logging.info('找到 %d 个RS进程帧', len(rs_frames))

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
                        frame_skip_events.append(
                            {
                                'callid': event_callid,
                                'ts': event_ts,
                                'dur': event_dur if event_dur else 0,
                                'name': event_name,
                            }
                        )

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
                        'skip_event_count': len(frame_skip_events),
                    }

            result = list(skip_frame_dict.values())

            # logging.info('检测完成: %d 个RS帧包含skip事件（共%d个skip事件）',
            # len(result), len(skip_events))

            timing_stats['detect_rs_skip'] = time.time() - detect_start
            return result

        except Exception:
            # logging.error('检测RS skip帧失败: %s', str(e))
            # logging.error('异常堆栈跟踪:\n%s', traceback.format_exc())
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
        except Exception:
            # logging.error('获取RS进程PID失败: %s', e)
            return 0

    def _calculate_rs_skip_cpu(self, skip_frames: list) -> int:
        """计算RS进程skip帧的CPU浪费"""
        if not skip_frames:
            return 0

        rs_pid = self._get_rs_process_pid()
        if not rs_pid:
            # logging.warning('无法获取RS进程PID，跳过RS进程CPU计算')
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
                    frame_end=frame_end,
                )
                if app_instructions > 0:
                    total_rs_cpu += app_instructions
                    calculated_count += 1
            except Exception:
                # logging.warning('计算RS skip帧CPU失败: frame_id=%s, error=%s',
                # skip_frame.get("frame_id"), e)
                pass

        # logging.info('RS进程CPU统计: %d个skip帧, 成功计算%d个, 总CPU=%d 指令',
        # len(skip_frames), calculated_count, total_rs_cpu)
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
            except Exception:
                # logging.error('加载RS API缓存失败: %s', e)
                caches['rs_api'] = None

        if self.nw_api_enabled:
            try:
                caches['nw'] = preload_nw_caches(trace_conn, min_ts, max_ts)
            except Exception:
                # logging.error('加载NativeWindow API缓存失败: %s', e)
                caches['nw'] = None

        timing_stats['preload_rs_caches'] = time.time() - preload_start
        return caches

    def _trace_rs_to_app_frames(
        self, trace_conn, perf_conn, skip_frames: list, caches: dict, timing_stats: dict
    ) -> list:
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
                    trace_result = trace_rs_api(trace_conn, rs_frame_id, caches=caches['rs_api'], perf_conn=perf_conn)
                    if trace_result and trace_result.get('app_frame'):
                        trace_method = 'rs_api'
                        rs_success += 1
                except Exception:
                    # logging.warning('RS API追溯失败: frame_id=%s, error=%s', rs_frame_id, e)
                    pass

            # 如果RS API失败，尝试NativeWindow API
            if not trace_method and self.nw_api_enabled and caches.get('nw'):
                try:
                    trace_result = trace_nw_api(
                        trace_conn,
                        rs_frame_id,
                        nativewindow_events_cache=caches['nw'].get('nativewindow_events'),
                        app_frames_cache=caches['nw'].get('app_frames'),
                        tid_to_info_cache=caches['nw'].get('tid_to_info'),
                        perf_conn=perf_conn,
                    )
                    if trace_result and trace_result.get('app_frame'):
                        trace_method = 'nw_api'
                        nw_success += 1
                except Exception:
                    # logging.warning('NativeWindow API追溯失败: frame_id=%s, error=%s', rs_frame_id, e)
                    pass

            if not trace_method:
                failed += 1

            traced_results.append({'rs_frame': skip_frame, 'trace_result': trace_result, 'trace_method': trace_method})

        timing_stats['trace_rs_to_app'] = time.time() - trace_start
        # logging.info('RS追溯完成: RS API成功%d, NW API成功%d, 失败%d',
        # rs_success, nw_success, failed)

        return traced_results

    def _merge_and_deduplicate_frames(
        self,
        direct_frames_df: pd.DataFrame,
        rs_traced_results: list,
        framework_frames_df: pd.DataFrame,
        timing_stats: dict,
    ) -> tuple:
        """合并并去重空刷帧（核心方法）

        Args:
            direct_frames_df: 正向检测的flag=2帧
            rs_traced_results: RS skip追溯结果
            framework_frames_df: 框架特定检测的帧（Flutter/RN等）
            timing_stats: 耗时统计字典

        Returns:
            tuple: (合并后的DataFrame, 检测统计信息)
        """
        trace_conn = self.cache_manager.trace_conn
        frame_map = {}  # key: (pid, ts, vsync)
        detection_stats = {
            'direct_only': 0,
            'rs_traced_only': 0,
            'framework_specific_only': 0,
            'both': 0,
            'framework_and_direct': 0,
            'framework_and_rs': 0,
            'all_three': 0,
            'total_rs_skip_events': len(rs_traced_results),
            'total_framework_events': len(framework_frames_df) if not framework_frames_df.empty else 0,
        }

        # 1. 处理正向检测的帧
        for _, row in direct_frames_df.iterrows():
            key = (row['pid'], row['ts'], row['vsync'])
            # 使用"线程名=进程名"规则判断主线程（规则完全成立，无需查询is_main_thread字段）
            # 处理pandas NaN值：如果thread_name是NaN，转换为空字符串
            thread_name = row.get('thread_name', '')
            if pd.isna(thread_name):
                thread_name = ''
            process_name = row.get('process_name', '')
            if pd.isna(process_name):
                process_name = ''
            tid = row.get('tid')
            itid = row.get('itid')  # direct_frames_df应该包含itid字段
            callstack_id = row.get('callstack_id')
            # 处理pandas NaN值：如果callstack_id是NaN，转换为None
            if pd.isna(callstack_id):
                callstack_id = None
            
            # 如果thread_name为空，从数据库查询
            if not thread_name and tid and trace_conn:
                try:
                    cursor = trace_conn.cursor()
                    cursor.execute('SELECT name FROM thread WHERE tid = ? LIMIT 1', (int(tid),))
                    result = cursor.fetchone()
                    if result:
                        thread_name = result[0] or ''
                except Exception as e:
                    logging.debug(f'查询thread_name失败: tid={tid}, error={e}')
                    pass
            
            # 如果callstack_id为空，从frame_slice表查询
            # 根据文档：frame_slice.itid 关联 thread.id（不是thread.itid）
            # 优先使用vsync匹配（vsync是唯一标识一组渲染帧的）
            if callstack_id is None and trace_conn:
                try:
                    cursor = trace_conn.cursor()
                    vsync = row.get('vsync')
                    
                    # 优先使用vsync匹配（最准确）
                    if vsync is not None and pd.notna(vsync):
                        if itid is not None and pd.notna(itid):
                            # 如果有itid，直接使用itid和vsync匹配
                            cursor.execute(
                                """
                                SELECT callstack_id FROM frame_slice 
                                WHERE vsync = ? AND itid = ? LIMIT 1
                                """,
                                (int(vsync), int(itid))
                            )
                            result = cursor.fetchone()
                            if result:
                                callstack_id = result[0]
                        elif tid and pd.notna(tid):
                            # 如果没有itid，通过tid查询thread.id，然后用id和vsync匹配
                            # 注意：frame_slice.itid 关联 thread.id（不是thread.itid）
                            cursor.execute(
                                """
                                SELECT callstack_id FROM frame_slice 
                                WHERE vsync = ? AND itid IN (
                                    SELECT id FROM thread WHERE tid = ?
                                ) LIMIT 1
                                """,
                                (int(vsync), int(tid))
                            )
                            result = cursor.fetchone()
                            if result:
                                callstack_id = result[0]
                    else:
                        # 如果没有vsync，使用ts, dur, itid匹配
                        if itid is not None and pd.notna(itid):
                            cursor.execute(
                                """
                                SELECT callstack_id FROM frame_slice 
                                WHERE ts = ? AND dur = ? AND itid = ? LIMIT 1
                                """,
                                (row['ts'], row['dur'], int(itid))
                            )
                            result = cursor.fetchone()
                            if result:
                                callstack_id = result[0]
                        elif tid and pd.notna(tid):
                            cursor.execute(
                                """
                                SELECT callstack_id FROM frame_slice 
                                WHERE ts = ? AND dur = ? AND itid IN (
                                    SELECT id FROM thread WHERE tid = ?
                                ) LIMIT 1
                                """,
                                (row['ts'], row['dur'], int(tid))
                            )
                            result = cursor.fetchone()
                            if result:
                                callstack_id = result[0]
                except Exception as e:
                    logging.debug(f'查询callstack_id失败: vsync={vsync}, itid={itid}, tid={tid}, error={e}')
                    pass
            
            is_main_thread = (
                1 if thread_name == process_name else (row.get('is_main_thread', 0) if 'is_main_thread' in row else 0)
            )

            frame_map[key] = {
                'ts': row['ts'],
                'dur': row['dur'],
                'vsync': row['vsync'],
                'pid': row['pid'],
                'tid': tid,
                'process_name': process_name,
                'thread_name': thread_name,
                'flag': row['flag'],
                'type': row.get('type', 0),
                'is_main_thread': is_main_thread,  # 使用规则判断，如果规则不适用则使用原有值
                'callstack_id': callstack_id,
                'detection_method': 'direct',
                'traced_count': 0,
                'rs_skip_events': [],
                'trace_method': None,
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
                app_frame.get('frame_vsync') or app_frame.get('vsync'),
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
                # 需要查询itid和tid（唤醒链分析需要）
                # 注意：根据文档，RS追溯返回的thread_id是itid（TS内部线程ID，对应thread表的id字段）
                # instant.wakeup_from字段明确说明是"唤醒当前线程的内部线程号（itid）"
                # 而tid是线程号（thread表的tid字段），perf_sample.thread_id也是线程号
                itid = app_frame.get('thread_id') or app_frame.get('tid')
                tid = None

                if itid and trace_conn:
                    try:
                        cursor = trace_conn.cursor()
                        # RS追溯返回的thread_id是itid（thread表的id字段），直接查询对应的tid
                        cursor.execute(
                            """
                            SELECT id, tid FROM thread WHERE id = ? LIMIT 1
                        """,
                            (itid,),
                        )
                        result = cursor.fetchone()
                        if result:
                            itid = result[0]  # thread.id（确认是itid）
                            tid = result[1]  # thread.tid（线程号）
                        else:
                            # logging.warning('未找到itid=%s对应的线程信息', itid)
                            pass
                    except Exception:
                        # logging.warning('查询线程信息失败: itid=%s, error=%s', itid, e)
                        pass

                # 使用"线程名=进程名"规则判断主线程（规则完全成立，无需查询is_main_thread字段）
                thread_name = app_frame.get('thread_name', '')
                if pd.isna(thread_name):
                    thread_name = ''
                process_name = app_frame.get('process_name', '')
                if pd.isna(process_name):
                    process_name = ''
                callstack_id = app_frame.get('callstack_id')
                if pd.isna(callstack_id):
                    callstack_id = None
                frame_ts = app_frame.get('frame_ts') or app_frame.get('ts')
                frame_dur = app_frame.get('frame_dur') or app_frame.get('dur')
                frame_vsync = app_frame.get('frame_vsync') or app_frame.get('vsync')
                
                # 如果thread_name为空，从数据库查询
                if not thread_name and tid and trace_conn:
                    try:
                        cursor = trace_conn.cursor()
                        cursor.execute('SELECT name FROM thread WHERE tid = ? LIMIT 1', (int(tid),))
                        result = cursor.fetchone()
                        if result:
                            thread_name = result[0] or ''
                    except Exception:
                        pass
                
                # 如果callstack_id为空，从frame_slice表查询
                # 根据文档：frame_slice.itid 关联 thread.id（不是thread.itid）
                # 优先使用vsync匹配（vsync是唯一标识一组渲染帧的）
                if callstack_id is None and trace_conn:
                    try:
                        cursor = trace_conn.cursor()
                        # 优先使用vsync匹配（最准确）
                        if frame_vsync is not None and pd.notna(frame_vsync):
                            if itid is not None and pd.notna(itid):
                                cursor.execute(
                                    """
                                    SELECT callstack_id FROM frame_slice 
                                    WHERE vsync = ? AND itid = ? LIMIT 1
                                    """,
                                    (int(frame_vsync), int(itid))
                                )
                            elif tid and pd.notna(tid):
                                cursor.execute(
                                    """
                                    SELECT callstack_id FROM frame_slice 
                                    WHERE vsync = ? AND itid IN (
                                        SELECT id FROM thread WHERE tid = ?
                                    ) LIMIT 1
                                    """,
                                    (int(frame_vsync), int(tid))
                                )
                        elif frame_ts and frame_dur:
                            # 如果没有vsync，使用ts, dur, itid匹配
                            if itid is not None and pd.notna(itid):
                                cursor.execute(
                                    """
                                    SELECT callstack_id FROM frame_slice 
                                    WHERE ts = ? AND dur = ? AND itid = ? LIMIT 1
                                    """,
                                    (frame_ts, frame_dur, int(itid))
                                )
                            elif tid and pd.notna(tid):
                                cursor.execute(
                                    """
                                    SELECT callstack_id FROM frame_slice 
                                    WHERE ts = ? AND dur = ? AND itid IN (
                                        SELECT id FROM thread WHERE tid = ?
                                    ) LIMIT 1
                                    """,
                                    (frame_ts, frame_dur, int(tid))
                                )
                        
                        result = cursor.fetchone()
                        if result:
                            callstack_id = result[0]
                    except Exception:
                        pass
                
                is_main_thread = 1 if thread_name == process_name else 0

                frame_map[key] = {
                    'ts': frame_ts,
                    'dur': frame_dur,
                    'vsync': app_frame.get('frame_vsync') or app_frame.get('vsync'),
                    'pid': app_frame.get('app_pid') or app_frame.get('process_pid') or app_frame.get('pid'),
                    'tid': tid,
                    'itid': itid,  # 添加itid字段（唤醒链分析需要）
                    'process_name': process_name,
                    'thread_name': thread_name,
                    'flag': app_frame.get('frame_flag') or app_frame.get('flag', 2),  # 空刷帧标记
                    'type': 0,
                    'is_main_thread': is_main_thread,  # 从thread表查询得到，或使用app_frame中的值
                    'callstack_id': callstack_id,
                    'detection_method': 'rs_traced',
                    'traced_count': 1,
                    'rs_skip_events': [rs_frame],
                    'trace_method': trace_method,
                }
                detection_stats['rs_traced_only'] += 1

        # 3. 处理框架特定检测的帧（Flutter/RN等）
        if framework_frames_df is not None and not framework_frames_df.empty:
            for _, row in framework_frames_df.iterrows():
                # 使用 (pid, ts, vsync) 作为 key，如果没有 vsync 则使用 (pid, ts, None)
                vsync = row.get('vsync') if pd.notna(row.get('vsync')) else None
                key = (row['pid'], row['ts'], vsync)

                if key in frame_map:
                    # 已存在：更新检测方法
                    existing_method = frame_map[key]['detection_method']
                    if existing_method == 'direct':
                        frame_map[key]['detection_method'] = 'framework_and_direct'
                        detection_stats['direct_only'] -= 1
                        detection_stats['framework_and_direct'] += 1
                    elif existing_method == 'rs_traced':
                        frame_map[key]['detection_method'] = 'framework_and_rs'
                        detection_stats['rs_traced_only'] -= 1
                        detection_stats['framework_and_rs'] += 1
                    elif existing_method == 'both':
                        frame_map[key]['detection_method'] = 'all_three'
                        detection_stats['both'] -= 1
                        detection_stats['all_three'] += 1
                    # 如果是 framework_specific，则保持不变（理论上不会发生）
                else:
                    # 新帧：添加为 framework_specific
                    tid = row.get('tid')
                    itid = row.get('itid')
                    thread_name = row.get('thread_name', '')
                    if pd.isna(thread_name):
                        thread_name = ''
                    callstack_id = row.get('callstack_id')
                    if pd.isna(callstack_id):
                        callstack_id = None
                    vsync = row.get('vsync')
                    
                    # 如果thread_name为空，从数据库查询
                    if not thread_name and tid and trace_conn:
                        try:
                            cursor = trace_conn.cursor()
                            cursor.execute('SELECT name FROM thread WHERE tid = ? LIMIT 1', (int(tid),))
                            result = cursor.fetchone()
                            if result:
                                thread_name = result[0] or ''
                        except Exception:
                            pass
                    
                    # 如果callstack_id为空，从frame_slice表查询
                    # 根据文档：frame_slice.itid 关联 thread.id（不是thread.itid）
                    # 优先使用vsync匹配（vsync是唯一标识一组渲染帧的）
                    if callstack_id is None and trace_conn:
                        try:
                            cursor = trace_conn.cursor()
                            # 优先使用vsync匹配（最准确）
                            if vsync is not None and pd.notna(vsync):
                                if itid is not None and pd.notna(itid):
                                    cursor.execute(
                                        """
                                        SELECT callstack_id FROM frame_slice 
                                        WHERE vsync = ? AND itid = ? LIMIT 1
                                        """,
                                        (int(vsync), int(itid))
                                    )
                                elif tid and pd.notna(tid):
                                    cursor.execute(
                                        """
                                        SELECT callstack_id FROM frame_slice 
                                        WHERE vsync = ? AND itid IN (
                                            SELECT id FROM thread WHERE tid = ?
                                        ) LIMIT 1
                                        """,
                                        (int(vsync), int(tid))
                                    )
                            else:
                                # 如果没有vsync，使用ts, dur, itid匹配
                                if itid is not None and pd.notna(itid):
                                    cursor.execute(
                                        """
                                        SELECT callstack_id FROM frame_slice 
                                        WHERE ts = ? AND dur = ? AND itid = ? LIMIT 1
                                        """,
                                        (row['ts'], row['dur'], int(itid))
                                    )
                                elif tid and pd.notna(tid):
                                    cursor.execute(
                                        """
                                        SELECT callstack_id FROM frame_slice 
                                        WHERE ts = ? AND dur = ? AND itid IN (
                                            SELECT id FROM thread WHERE tid = ?
                                        ) LIMIT 1
                                        """,
                                        (row['ts'], row['dur'], int(tid))
                                    )
                            
                            result = cursor.fetchone()
                            if result:
                                callstack_id = result[0]
                        except Exception:
                            pass
                    
                    frame_map[key] = {
                        'ts': row['ts'],
                        'dur': row['dur'],
                        'vsync': vsync,
                        'pid': row['pid'],
                        'tid': tid,
                        'itid': row.get('itid'),
                        'process_name': row.get('process_name', 'unknown'),
                        'thread_name': thread_name if thread_name else 'unknown',
                        'flag': row.get('flag', 2),
                        'type': row.get('type', 0),
                        'is_main_thread': row.get('is_main_thread', 0),
                        'callstack_id': callstack_id,
                        'detection_method': 'framework_specific',
                        'framework_type': row.get('framework_type', 'unknown'),
                        'frame_damage': row.get('frame_damage'),  # Flutter 特有
                        'beginframe_id': row.get('beginframe_id'),  # Flutter 特有
                        'traced_count': 0,
                        'rs_skip_events': [],
                        'trace_method': None,
                    }
                    detection_stats['framework_specific_only'] += 1

        # 4. 转换为DataFrame
        merged_df = pd.DataFrame(list(frame_map.values())) if frame_map else pd.DataFrame()

        # 确保thread_id字段存在（如果只有tid，则使用tid作为thread_id）
        if not merged_df.empty and 'thread_id' not in merged_df.columns:
            if 'tid' in merged_df.columns:
                merged_df['thread_id'] = merged_df['tid']
        elif not merged_df.empty and 'tid' in merged_df.columns:
            # 如果thread_id存在但为None，使用tid填充
            merged_df['thread_id'] = merged_df['thread_id'].fillna(merged_df['tid'])

        # 统计信息
        # logging.info('帧合并统计: 仅正向=%d, 仅反向=%d, 重叠=%d, 总计=%d',
        # detection_stats['direct_only'],
        # detection_stats['rs_traced_only'],
        # detection_stats['both'],
        # len(merged_df))

        return merged_df, detection_stats

    def _merge_time_ranges(self, time_ranges: list[tuple[int, int]]) -> list[tuple[int, int]]:
        """合并重叠的时间范围

        Args:
            time_ranges: 时间范围列表，格式为 [(start_ts, end_ts), ...]

        Returns:
            合并后的时间范围列表（无重叠）
        """
        if not time_ranges:
            return []

        # 按开始时间排序
        sorted_ranges = sorted(time_ranges, key=lambda x: x[0])
        merged = [sorted_ranges[0]]

        for current_start, current_end in sorted_ranges[1:]:
            last_start, last_end = merged[-1]

            # 如果当前范围与最后一个合并范围重叠
            if current_start <= last_end:
                # 合并：扩展结束时间
                merged[-1] = (last_start, max(last_end, current_end))
            else:
                # 无重叠，添加新范围
                merged.append((current_start, current_end))

        return merged

    def _calculate_merged_time_ranges(self, frame_loads: list) -> list[tuple[int, int]]:
        """计算所有帧的合并时间范围（使用原始时间戳，不含扩展）

        Args:
            frame_loads: 帧负载数据列表

        Returns:
            合并后的时间范围列表
        """
        if not frame_loads:
            return []

        # 收集所有帧的原始时间范围（使用 frame_slice 表中的 ts 和 dur，不含扩展）
        time_ranges = []
        for frame in frame_loads:
            ts = frame.get('ts', 0)
            dur = frame.get('dur', 0)

            if ts > 0 and dur >= 0:
                # 使用原始时间戳（frame_slice 表中的 ts 和 dur）
                # 不扩展±1ms，避免重叠问题
                frame_start = ts
                frame_end = ts + dur
                time_ranges.append((frame_start, frame_end))

        # 合并重叠的时间范围
        return self._merge_time_ranges(time_ranges)

    def _build_result_unified(
        self,
        frame_loads: list,
        trace_df: pd.DataFrame,
        total_load: int,
        timing_stats: dict,
        detection_stats: dict,
        rs_skip_cpu: int,
        rs_traced_results: list,
        merged_time_ranges: list[tuple[int, int]],
    ) -> dict:
        """构建统一的分析结果（使用去重后的时间范围）

        Args:
            frame_loads: 帧负载数据
            trace_df: 帧数据DataFrame
            total_load: 总负载
            timing_stats: 耗时统计
            detection_stats: 检测方法统计
            rs_skip_cpu: RS进程CPU浪费
            rs_traced_results: RS追溯结果（用于统计）
            merged_time_ranges: 去重后的时间范围列表（从 get_empty_frames_with_details 获取）

        Returns:
            dict: 统一的分析结果
        """
        # === 使用去重后的时间范围计算所有汇总值（去除重叠区域） ===
        original_empty_frame_load = int(sum(f['frame_load'] for f in frame_loads)) if frame_loads else 0
        deduplicated_empty_frame_load = None
        deduplicated_main_thread_load = None
        deduplicated_background_thread_load = None
        deduplicated_thread_loads = None  # {thread_id: load, ...}

        if merged_time_ranges:
            recalc_start = time.time()

            # 扩展合并后的时间范围（±1ms），与 frame_load 计算保持一致
            extended_merged_ranges = []
            for start_ts, end_ts in merged_time_ranges:
                extended_start = start_ts - 1_000_000
                extended_end = end_ts + 1_000_000
                extended_merged_ranges.append((extended_start, extended_end))

            # 优化：合并4次查询为1次，在应用层分组计算
            deduplicated_result = self.cache_manager.get_all_thread_loads_with_info_for_pids(
                self.cache_manager.app_pids, time_ranges=extended_merged_ranges
            )

            deduplicated_empty_frame_load = deduplicated_result['total_load']
            deduplicated_main_thread_load = deduplicated_result['main_thread_load']
            deduplicated_background_thread_load = deduplicated_result['background_thread_load']
            deduplicated_thread_loads = deduplicated_result['thread_loads_dict']

            recalc_time = time.time() - recalc_start
            timing_stats['recalc_deduplicated_loads'] = recalc_time
            logging.info(
                f'去重负载重新计算耗时: {recalc_time:.3f}秒 (优化方法-1次查询, 时间范围: {len(extended_merged_ranges)}个)'
            )

        # 保存原始 empty_frame_load 到 timing_stats（用于日志对比）
        timing_stats['original_empty_frame_load'] = original_empty_frame_load

        # 构建 tid_to_info 映射（用于 thread_statistics）
        tid_to_info = {}
        if self.cache_manager and self.cache_manager.trace_conn:
            try:
                trace_cursor = self.cache_manager.trace_conn.cursor()
                app_pids = self.cache_manager.app_pids or []
                if app_pids:
                    placeholders = ','.join('?' * len(app_pids))
                    trace_cursor.execute(
                        f"""
                        SELECT DISTINCT t.tid, t.name as thread_name, p.name as process_name
                        FROM thread t
                        INNER JOIN process p ON t.ipid = p.ipid
                        WHERE p.pid IN ({placeholders})
                    """,
                        app_pids,
                    )

                    for tid, thread_name, process_name in trace_cursor.fetchall():
                        tid_to_info[tid] = {
                            'thread_name': thread_name,
                            'process_name': process_name,
                            'is_main_thread': 1 if thread_name == process_name else 0,
                        }
            except Exception:
                pass

        # === 使用公共模块构建基础结果 ===
        base_result = self.result_builder.build_result(
            frame_loads=frame_loads,
            total_load=total_load,  # total_load 保持不变（整个trace的CPU）
            detection_stats=detection_stats,  # 传递检测统计信息
            deduplicated_empty_frame_load=deduplicated_empty_frame_load,  # 传递去重后的 empty_frame_load
            deduplicated_main_thread_load=deduplicated_main_thread_load,  # 传递去重后的主线程负载
            deduplicated_background_thread_load=deduplicated_background_thread_load,  # 传递去重后的后台线程负载
            deduplicated_thread_loads=deduplicated_thread_loads,  # 传递去重后的所有线程负载
            tid_to_info=tid_to_info,  # 传递线程信息映射
        )

        # 注意：timing_stats 仅用于调试日志，不添加到最终结果中

        # 增强summary：添加检测方法统计
        if base_result and 'summary' in base_result:
            summary = base_result['summary']

            # 添加检测方法分解
            summary['detection_breakdown'] = {
                'direct_only': detection_stats['direct_only'],
                'rs_traced_only': detection_stats['rs_traced_only'],
                'both': detection_stats['both'],
            }

            # 添加RS追溯统计
            total_skip_events = detection_stats.get('total_rs_skip_events', 0)
            total_skip_frames = len([r for r in rs_traced_results if r.get('rs_frame')])
            traced_success = sum(
                1 for r in rs_traced_results if r.get('trace_result') and r['trace_result'].get('app_frame')
            )
            rs_api_success = sum(1 for r in rs_traced_results if r.get('trace_method') == 'rs_api')
            nw_api_success = sum(1 for r in rs_traced_results if r.get('trace_method') == 'nw_api')

            summary['rs_trace_stats'] = {
                'total_skip_events': total_skip_events,
                'total_skip_frames': total_skip_frames,
                'traced_success_count': traced_success,
                'trace_accuracy': (traced_success / total_skip_frames * 100) if total_skip_frames > 0 else 0.0,
                'rs_api_success': rs_api_success,
                'nativewindow_success': nw_api_success,
                'failed': total_skip_frames - traced_success,
                'rs_skip_cpu': rs_skip_cpu,
            }

            # 添加traced_count统计
            if frame_loads:
                multi_traced_frames = [f for f in frame_loads if f.get('traced_count', 0) > 1]
                max_traced = max((f.get('traced_count', 0) for f in frame_loads), default=0)

                summary['traced_count_stats'] = {
                    'frames_traced_multiple_times': len(multi_traced_frames),
                    'max_traced_count': max_traced,
                }

            # 确保三个检测器的原始检测结果被保存
            summary['direct_detected_count'] = detection_stats.get('direct_detected_count', 0) if detection_stats else 0
            summary['rs_detected_count'] = detection_stats.get('rs_detected_count', 0) if detection_stats else 0
            framework_counts = detection_stats.get('framework_detected_counts', {}) if detection_stats else {}
            summary['framework_detection_counts'] = framework_counts if framework_counts is not None else {}

        return base_result

    def _build_empty_result_unified(
        self, total_load: int, timing_stats: dict, rs_skip_cpu: int, detection_stats: Optional[dict] = None
    ) -> dict:
        """构建空结果（统一格式）"""
        result = {
            'status': 'success',
            'summary': {
                'total_empty_frames': 0,
                'empty_frame_load': 0,
                'empty_frame_percentage': 0.0,
                'total_load': total_load,
                'severity_level': 'normal',
                'severity_description': '正常：未检测到空刷帧',
                'detection_breakdown': {'direct_only': 0, 'rs_traced_only': 0, 'both': 0},
                'rs_trace_stats': {
                    'total_skip_events': 0,
                    'total_skip_frames': 0,
                    'traced_success_count': 0,
                    'trace_accuracy': 0.0,
                    'rs_api_success': 0,
                    'nativewindow_success': 0,
                    'failed': 0,
                    'rs_skip_cpu': rs_skip_cpu,
                },
            },
            'top_frames': [],  # 统一列表，不再区分主线程和后台线程
            # 注意：timing_stats 仅用于调试日志，不添加到最终结果中
        }

        # === 三个检测器的原始检测结果（在合并去重之前，不处理 overlap）===
        # 无论 detection_stats 是否存在，都设置这三个字段（确保总是存在）
        if detection_stats:
            direct_count = detection_stats.get('direct_detected_count', 0)
            rs_count = detection_stats.get('rs_detected_count', 0)
            framework_counts = detection_stats.get('framework_detected_counts')
            framework_counts = framework_counts if framework_counts is not None else {}

            result['summary']['direct_detected_count'] = direct_count
            result['summary']['rs_detected_count'] = rs_count
            result['summary']['framework_detection_counts'] = framework_counts
        else:
            # 如果没有 detection_stats，设置默认值
            result['summary']['direct_detected_count'] = 0
            result['summary']['rs_detected_count'] = 0
            result['summary']['framework_detection_counts'] = {}

        return result
