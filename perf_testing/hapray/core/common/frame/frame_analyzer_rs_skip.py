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
from typing import Optional, List, Dict, Any

import pandas as pd

from .frame_core_cache_manager import FrameCacheManager
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


class RSSkipFrameAnalyzer:
    """RS Skip帧分析器
    
    专门用于分析RS进程中的DisplayNode skip事件，包括：
    1. RS skip事件检测
    2. 追溯到应用帧（RS API + NativeWindow API）
    3. CPU浪费统计
    4. 追溯成功率分析
    
    与EmptyFrameAnalyzer的关系：
    - EmptyFrameAnalyzer：分析应用进程的flag=2空刷帧
    - RSSkipFrameAnalyzer：分析RS进程的skip事件，追溯到应用帧
    - 两者互补，共同覆盖空刷帧检测
    
    完全遵循EmptyFrameAnalyzer的架构：
    - 初始化参数相同：(debug_vsync_enabled, cache_manager)
    - 主入口方法：analyze_rs_skip_frames()
    - 分阶段处理：检测→预加载→追溯→计算→构建
    - 统一输出格式：{status, summary, top_frames}
    - 错误处理一致：try-except返回None
    """
    
    def __init__(self, debug_vsync_enabled: bool = False, cache_manager: FrameCacheManager = None):
        """初始化RS Skip分析器
        
        参数完全遵循EmptyFrameAnalyzer的设计
        
        Args:
            debug_vsync_enabled: VSync调试开关（保留以兼容接口，RS Skip分析不使用）
            cache_manager: 缓存管理器实例
        """
        self.cache_manager = cache_manager
        
        # 使用公共模块（模块化重构）
        self.cpu_calculator = EmptyFrameCPUCalculator(cache_manager)
        self.callchain_analyzer = EmptyFrameCallchainAnalyzer(cache_manager)
        self.result_builder = EmptyFrameResultBuilder(cache_manager)
        
        # 配置选项（参考EmptyFrameAnalyzer的设计）
        self.rs_api_enabled = True  # 是否启用RS系统API追溯
        self.nw_api_enabled = True  # 是否启用NativeWindow API追溯
        self.max_frames = None  # 最大处理帧数（None=全部）
        self.top_n = 10  # Top N帧数量
    
    def analyze_rs_skip_frames(self) -> Optional[dict]:
        """分析RS Skip帧（主入口方法）
        
        完全遵循EmptyFrameAnalyzer.analyze_empty_frames()的架构
        
        Returns:
            dict: 包含分析结果
            {
                'status': 'success',
                'summary': {
                    'total_skip_frames': int,
                    'traced_success_count': int,
                    'trace_accuracy': float,
                    'total_wasted_instructions': int,
                    'severity_level': str,
                    'severity_description': str,
                },
                'top_frames': {
                    'top_skip_frames': list,
                }
            }
            或None（如果分析失败）
        """
        # 从cache_manager获取数据库连接和参数（完全遵循EmptyFrameAnalyzer）
        trace_conn = self.cache_manager.trace_conn if self.cache_manager else None
        perf_conn = self.cache_manager.perf_conn if self.cache_manager else None
        app_pids = self.cache_manager.app_pids if self.cache_manager else []
        
        if not trace_conn:
            logging.error('trace数据库连接未建立')
            return None
        
        total_start_time = time.time()
        timing_stats = {}
        
        try:
            # 阶段1：检测RS skip帧
            skip_frames = self._detect_skip_frames(trace_conn, timing_stats)
            if not skip_frames:
                logging.info('未检测到RS skip帧，返回空结果')
                return self._build_empty_result(timing_stats)
            
            # 阶段2：计算RS进程的skip帧CPU浪费【新增】
            rs_skip_cpu = 0
            if perf_conn:
                rs_cpu_start = time.time()
                rs_skip_cpu = self._calculate_rs_skip_cpu(skip_frames)
                timing_stats['rs_cpu_calculation'] = time.time() - rs_cpu_start
                logging.info(f'RS进程CPU计算完成: {rs_skip_cpu:,} 指令, 耗时: {timing_stats["rs_cpu_calculation"]:.3f}秒')
            
            # 阶段3：预加载缓存
            caches = self._preload_caches(trace_conn, skip_frames, timing_stats)
            
            # 阶段4：追溯到应用帧
            traced_results = self._trace_to_app_frames(
                trace_conn, perf_conn, skip_frames, caches, timing_stats
            )
            
            # 阶段5：应用进程CPU计算（使用公共模块）
            cpu_calc_start = time.time()
            frame_loads_raw = self.cpu_calculator.extract_cpu_from_traced_results(traced_results)
            
            # 去重：同一个应用帧可能被多个RS skip事件追溯到
            frame_loads = self._deduplicate_app_frames(frame_loads_raw)
            logging.info(f'应用进程CPU计算完成: {len(frame_loads_raw)}个帧（去重前）, {len(frame_loads)}个帧（去重后）')
            
            timing_stats['app_cpu_calculation'] = time.time() - cpu_calc_start
            logging.info(f'应用进程CPU计算耗时: {timing_stats["app_cpu_calculation"]:.3f}秒')
            
            # 阶段6：调用链分析（使用公共模块）【新增】
            if perf_conn and frame_loads:
                callchain_start = time.time()
                self._analyze_callchains(frame_loads, traced_results, timing_stats)
                timing_stats['callchain_analysis'] = time.time() - callchain_start
                logging.info(f'调用链分析完成, 耗时: {timing_stats["callchain_analysis"]:.3f}秒')
            
            # 阶段7：结果构建（使用公共模块）
            result = self._build_result_unified(
                skip_frames, traced_results, frame_loads, rs_skip_cpu, timing_stats
            )
            
            # 总耗时统计
            total_time = time.time() - total_start_time
            self._log_analysis_complete(total_time, timing_stats)
            
            return result
        
        except Exception as e:
            logging.error('分析RS Skip帧时发生异常: %s', str(e))
            logging.error('异常堆栈跟踪:\n%s', traceback.format_exc())
            return None
    
    # ==================== 私有方法：分阶段处理 ====================
    
    def _get_rs_process_pid(self) -> int:
        """获取RS进程PID
        
        Returns:
            int: RS进程PID，如果未找到返回0
        """
        try:
            cursor = self.cache_manager.trace_conn.cursor()
            cursor.execute("""
                SELECT pid FROM process 
                WHERE name LIKE '%render_service%' 
                LIMIT 1
            """)
            result = cursor.fetchone()
            if result:
                return result[0]
            else:
                logging.warning('未找到render_service进程')
                return 0
        except Exception as e:
            logging.error(f'获取RS进程PID失败: {e}')
            return 0
    
    def _calculate_rs_skip_cpu(self, skip_frames: list) -> int:
        """计算RS进程skip帧的CPU浪费【新增方法】
        
        注意：skip_frames是从callstack表检测的skip事件，不是frame_slice表的帧。
        每个skip事件有ts和dur，我们计算这个时间窗口内RS进程的CPU。
        
        Args:
            skip_frames: RS skip帧列表（实际是skip事件列表）
        
        Returns:
            int: RS进程CPU浪费（指令数）
        """
        if not skip_frames:
            return 0
        
        # 获取RS进程PID
        rs_pid = self._get_rs_process_pid()
        if not rs_pid:
            logging.warning('无法获取RS进程PID，跳过RS进程CPU计算')
            return 0
        
        total_rs_cpu = 0
        calculated_count = 0
        
        for skip_frame in skip_frames:
            frame_start = skip_frame['ts']
            frame_dur = skip_frame.get('dur', 0)
            
            # 如果dur=0或None，使用默认的16.67ms（一帧时间）
            if not frame_dur or frame_dur <= 0:
                frame_dur = 16_666_666  # 16.67ms
            
            frame_end = frame_start + frame_dur
            
            # 使用frame_empty_common的calculate_process_instructions计算RS进程CPU
            try:
                app_instructions, system_instructions = calculate_process_instructions(
                    perf_conn=self.cache_manager.perf_conn,
                    trace_conn=self.cache_manager.trace_conn,
                    app_pid=rs_pid,  # RS进程PID
                    frame_start=frame_start,
                    frame_end=frame_end
                )
                if app_instructions > 0:
                    total_rs_cpu += app_instructions
                    calculated_count += 1
            except Exception as e:
                logging.warning(f'计算RS skip帧CPU失败: frame_id={skip_frame.get("frame_id")}, error={e}')
                continue
        
        logging.info(f'RS进程CPU统计: {len(skip_frames)}个skip帧, 成功计算{calculated_count}个, 总CPU={total_rs_cpu:,} 指令')
        return total_rs_cpu
    
    def _deduplicate_app_frames(self, frame_loads: list) -> list:
        """去重并统计追溯次数：同一个应用帧可能被多个RS skip事件追溯到
        
        同一个帧被多次追溯到说明它导致了多次RS skip，这是重要的严重性指标。
        去重时保留CPU数据（只计算一次），但记录追溯次数。
        
        Args:
            frame_loads: 帧负载数据列表（可能包含重复）
        
        Returns:
            list: 去重后的帧负载数据列表（包含traced_count字段）
        """
        if not frame_loads:
            return []
        
        seen_frames = {}
        trace_counts = {}
        
        for frame in frame_loads:
            frame_id = frame.get('frame_id')
            if frame_id:
                # 使用frame_id作为唯一标识
                key = f"fid_{frame_id}"
            else:
                # 如果没有frame_id，使用(ts, dur, thread_id)作为唯一标识
                key = (frame.get('ts'), frame.get('dur'), frame.get('thread_id'))
            
            if key not in seen_frames:
                seen_frames[key] = frame
                trace_counts[key] = 1
            else:
                # 重复帧，增加追溯次数
                trace_counts[key] += 1
        
        # 添加traced_count字段
        unique_frames = []
        for key, frame in seen_frames.items():
            frame['traced_count'] = trace_counts[key]  # 添加追溯次数
            unique_frames.append(frame)
        
        # 统计信息
        total_traces = len(frame_loads)
        unique_count = len(unique_frames)
        duplicate_count = total_traces - unique_count
        
        # 统计被多次追溯的帧
        multi_traced = [f for f in unique_frames if f['traced_count'] > 1]
        max_traced = max((f['traced_count'] for f in unique_frames), default=1)
        
        logging.info(
            f'去重统计: {total_traces}个帧 → {unique_count}个唯一帧 '
            f'(去除{duplicate_count}个重复，{len(multi_traced)}个帧被多次追溯，最多{max_traced}次)'
        )
        
        return unique_frames
    
    def _analyze_callchains(
        self, 
        frame_loads: list, 
        traced_results: list, 
        timing_stats: dict
    ) -> None:
        """分析调用链（新增功能）
        
        Args:
            frame_loads: 帧负载数据列表
            traced_results: 追溯结果列表
            timing_stats: 耗时统计字典
        """
        if not frame_loads:
            return
        
        # 将追溯结果转换为DataFrame格式（用于调用链分析）
        app_frames_data = []
        for result in traced_results:
            if result.get('trace_result') and result['trace_result'].get('app_frame'):
                app_frame = result['trace_result']['app_frame']
                app_frames_data.append({
                    'ts': app_frame.get('frame_ts'),
                    'dur': app_frame.get('frame_dur'),
                    'tid': app_frame.get('thread_id'),
                    'thread_id': app_frame.get('thread_id'),
                })
        
        if not app_frames_data:
            logging.warning('没有成功追溯的应用帧，跳过调用链分析')
            return
        
        trace_df = pd.DataFrame(app_frames_data)
        perf_df = self.cache_manager.get_perf_samples()
        perf_conn = self.cache_manager.perf_conn
        
        # 使用公共模块EmptyFrameCallchainAnalyzer
        self.callchain_analyzer.analyze_callchains(
            frame_loads=frame_loads,
            trace_df=trace_df,
            perf_df=perf_df,
            perf_conn=perf_conn,
            top_n=self.top_n
        )
        
        logging.info(f'调用链分析完成: Top {self.top_n}帧')
    
    def _detect_skip_frames(self, trace_conn, timing_stats: dict) -> List[Dict]:
        """阶段1：检测RS skip帧
        
        调用原有的detect_displaynode_skip逻辑（修改为接收连接对象）
        
        Args:
            trace_conn: trace数据库连接
            timing_stats: 耗时统计字典
        
        Returns:
            list: skip帧列表
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
                timing_stats['detect_skip'] = time.time() - detect_start
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
                timing_stats['detect_skip'] = time.time() - detect_start
                return []
            
            logging.info('找到 %d 个RS进程帧', len(rs_frames))
            
            # 步骤3: 将skip事件匹配到对应的帧（使用SQL JOIN优化）
            frame_skip_map_query = """
            SELECT 
                fs.rowid as frame_rowid,
                c.callid,
                c.ts as skip_ts,
                COALESCE(c.dur, 0) as skip_dur,
                c.name as skip_name
            FROM callstack c
            INNER JOIN thread t ON c.callid = t.id
            INNER JOIN process p ON t.ipid = p.ipid
            INNER JOIN frame_slice fs ON fs.ipid = p.ipid
            WHERE c.name LIKE '%DisplayNode skip%'
            AND p.name = 'render_service'
            AND fs.type = 0
            AND fs.flag IS NOT NULL
            AND fs.ts <= c.ts
            AND (fs.ts + COALESCE(fs.dur, 0)) >= c.ts
            ORDER BY fs.rowid, c.ts
            """
            
            cursor.execute(frame_skip_map_query)
            matched_results = cursor.fetchall()
            
            # 构建frame_skip_map
            frame_skip_map = {}
            for row in matched_results:
                frame_rowid = row[0]
                if frame_rowid not in frame_skip_map:
                    frame_skip_map[frame_rowid] = []
                frame_skip_map[frame_rowid].append({
                    'ts': row[2],
                    'dur': row[3],
                    'name': row[4],
                    'callid': row[1]
                })
            
            # 步骤4: 构建结果
            frame_info_map = {frame[0]: frame for frame in rs_frames}
            
            result = []
            for frame_rowid, skip_events_list in frame_skip_map.items():
                frame_info = frame_info_map.get(frame_rowid)
                if frame_info:
                    result.append({
                        'frame_id': frame_rowid,
                        'ts': frame_info[1],
                        'dur': frame_info[2] if frame_info[2] is not None else 0,
                        'vsync': frame_info[3],
                        'flag': frame_info[4],
                        'skip_count': len(skip_events_list),
                        'skip_events': skip_events_list
                    })
            
            result.sort(key=lambda x: x['skip_count'], reverse=True)
            
            # 限制处理数量
            if self.max_frames and result:
                original_count = len(result)
                result = result[:self.max_frames]
                logging.info('限制处理数量: %d -> %d', original_count, len(result))
            
            timing_stats['detect_skip'] = time.time() - detect_start
            logging.info('检测到%d个RS skip帧，耗时: %.3f秒', len(result), timing_stats['detect_skip'])
            
            return result
            
        except Exception as e:
            logging.error('检测RS skip帧失败: %s', str(e))
            logging.error('异常堆栈跟踪:\n%s', traceback.format_exc())
            timing_stats['detect_skip'] = time.time() - detect_start
            return []
    
    def _preload_caches(self, trace_conn, skip_frames: list, timing_stats: dict) -> dict:
        """阶段2：预加载缓存
        
        Args:
            trace_conn: trace数据库连接
            skip_frames: skip帧列表
            timing_stats: 耗时统计字典
        
        Returns:
            dict: 缓存字典
        """
        preload_start = time.time()
        
        # 计算时间范围
        if not skip_frames:
            timing_stats['preload_cache'] = 0
            return {}
        
        min_ts = min(f['ts'] for f in skip_frames) - 500_000_000  # 前500ms
        max_ts = max(f['ts'] + f['dur'] for f in skip_frames) + 50_000_000  # 后50ms
        
        caches = {}
        
        # 预加载RS API缓存
        if self.rs_api_enabled:
            rs_api_start = time.time()
            try:
                caches['rs_api'] = preload_rs_api_caches(trace_conn, min_ts, max_ts)
                timing_stats['preload_rs_api'] = time.time() - rs_api_start
                logging.info('预加载RS API缓存完成，耗时: %.3f秒', timing_stats['preload_rs_api'])
            except Exception as e:
                logging.error('加载RS API缓存失败: %s', str(e))
                caches['rs_api'] = None
        
        # 预加载NativeWindow API缓存
        if self.nw_api_enabled:
            nw_start = time.time()
            try:
                caches['nw'] = preload_nw_caches(trace_conn, min_ts, max_ts)
                timing_stats['preload_nw'] = time.time() - nw_start
                logging.info('预加载NativeWindow API缓存完成，耗时: %.3f秒', timing_stats['preload_nw'])
            except Exception as e:
                logging.error('加载NativeWindow API缓存失败: %s', str(e))
                caches['nw'] = None
        
        timing_stats['preload_cache'] = time.time() - preload_start
        
        return caches
    
    def _trace_to_app_frames(self, trace_conn, perf_conn, skip_frames: list, 
                            caches: dict, timing_stats: dict) -> list:
        """阶段3：追溯到应用帧
        
        Args:
            trace_conn: trace数据库连接
            perf_conn: perf数据库连接
            skip_frames: skip帧列表
            caches: 预加载的缓存
            timing_stats: 耗时统计字典
        
        Returns:
            list: 追溯结果列表
        """
        trace_start = time.time()
        
        # 导入追溯函数
        # 追溯模块已在文件开头导入（trace_rs_api, trace_nw_api）
        
        traced_results = []
        rs_success = 0
        nw_success = 0
        failed = 0
        
        for skip_frame in skip_frames:
            trace_result = None
            trace_method = None
            
            # 提取rs_frame_id（函数期望的是整数ID，而不是整个skip_frame字典）
            rs_frame_id = skip_frame.get('frame_id')
            
            # 尝试RS API追溯
            trace_result = None
            if self.rs_api_enabled and caches.get('rs_api'):
                try:
                    trace_result = trace_rs_api(
                        trace_conn,
                        rs_frame_id,  # 传递整数ID，而不是整个字典
                        caches=caches['rs_api'],
                        perf_conn=perf_conn
                    )
                    # 只有当trace_result存在且包含app_frame时，才算RS API成功
                    # 这与原始算法保持一致（RS_skip_checker.py第429行）
                    if trace_result and trace_result.get('app_frame'):
                        trace_method = 'rs_api'
                        rs_success += 1
                        # RS API成功，不需要尝试NativeWindow API
                        traced_results.append({
                            'skip_frame': skip_frame,
                            'trace_result': trace_result,
                            'trace_method': trace_method
                        })
                        continue
                except Exception as e:
                    logging.debug('RS API追溯失败: %s', str(e))
                    trace_result = None
            
            # 如果RS API追溯失败（返回None或没有app_frame），尝试NativeWindow API追溯
            if (not trace_result or not trace_result.get('app_frame')) and self.nw_api_enabled and caches.get('nw'):
                try:
                    # NativeWindow API的函数签名：
                    # trace_rs_skip_to_app_frame(trace_conn, rs_frame_id, 
                    #                           nativewindow_events_cache, app_frames_cache, perf_conn)
                    nw_cache = caches['nw']
                    trace_result = trace_nw_api(
                        trace_conn,
                        rs_frame_id,  # 传递整数ID
                        nativewindow_events_cache=nw_cache.get('nativewindow_events_cache'),
                        app_frames_cache=nw_cache.get('app_frames_cache'),
                        perf_conn=perf_conn
                    )
                    # 只有当trace_result存在且包含app_frame时，才算NativeWindow API成功
                    # 这与原始算法保持一致（RS_skip_checker.py第468行）
                    if trace_result and trace_result.get('app_frame'):
                        trace_method = 'nativewindow'
                        nw_success += 1
                        # NativeWindow API成功
                        traced_results.append({
                            'skip_frame': skip_frame,
                            'trace_result': trace_result,
                            'trace_method': trace_method
                        })
                        continue
                except Exception as e:
                    logging.debug('NativeWindow API追溯失败: %s', str(e))
            
            # 两种方法都失败
            failed += 1
            traced_results.append({
                'skip_frame': skip_frame,
                'trace_result': trace_result,  # 可能是None或没有app_frame的结果
                'trace_method': trace_method
            })
        
        timing_stats['trace_to_app'] = time.time() - trace_start
        timing_stats['rs_api_success'] = rs_success
        timing_stats['nw_api_success'] = nw_success
        timing_stats['trace_failed'] = failed
        
        trace_accuracy = (rs_success + nw_success) / len(skip_frames) * 100 if skip_frames else 0.0
        logging.info('追溯完成，耗时: %.3f秒，成功率: %.1f%%', 
                    timing_stats['trace_to_app'], trace_accuracy)
        
        return traced_results
    
    def _calculate_cpu_waste(self, trace_conn, perf_conn, traced_results: list,
                            caches: dict, timing_stats: dict) -> None:
        """阶段4：计算CPU浪费
        
        注意：backtrack模块已经在追溯时计算了CPU浪费，这里只需要统计
        
        Args:
            trace_conn: trace数据库连接
            perf_conn: perf数据库连接
            traced_results: 追溯结果列表
            caches: 预加载的缓存
            timing_stats: 耗时统计字典
        """
        cpu_start = time.time()
        
        # backtrack模块已经在追溯时计算了CPU浪费
        # 这里只需要统计有CPU数据的帧数
        frames_with_cpu = 0
        
        for result in traced_results:
            if result['trace_result'] and result['trace_result'].get('app_frame'):
                app_frame = result['trace_result']['app_frame']
                cpu_waste = app_frame.get('cpu_waste', {})
                
                # backtrack模块已经计算了CPU浪费，直接使用
                if cpu_waste and cpu_waste.get('has_perf_data'):
                    wasted = cpu_waste.get('wasted_instructions', 0)
                    if wasted > 0:
                        frames_with_cpu += 1
        
        timing_stats['cpu_calculation'] = time.time() - cpu_start
        timing_stats['frames_with_cpu'] = frames_with_cpu
        
        logging.info('CPU浪费统计完成，耗时: %.3f秒，有CPU数据的帧: %d', 
                    timing_stats['cpu_calculation'], frames_with_cpu)
    
    def _build_result_unified(
        self, 
        skip_frames: list, 
        traced_results: list,
        frame_loads: list,
        rs_skip_cpu: int,
        timing_stats: dict
    ) -> dict:
        """阶段7：结果构建（使用公共模块，统一输出格式）
        
        Args:
            skip_frames: skip帧列表
            traced_results: 追溯结果列表
            frame_loads: 帧负载数据列表（已包含frame_load字段）
            rs_skip_cpu: RS进程CPU浪费
            timing_stats: 耗时统计字典
        
        Returns:
            dict: 统一格式的分析结果
        """
        result_build_start = time.time()
        
        # 统计
        total_skip_frames = len(skip_frames)
        total_skip_events = sum(f.get('skip_count', 0) for f in skip_frames)
        
        traced_success = sum(1 for r in traced_results 
                           if r['trace_result'] and r['trace_result'].get('app_frame'))
        trace_accuracy = (traced_success / total_skip_frames * 100) if total_skip_frames > 0 else 0.0
        
        rs_api_success = timing_stats.get('rs_api_success', 0)
        nw_api_success = timing_stats.get('nw_api_success', 0)
        failed = timing_stats.get('trace_failed', 0)
        
        # 应用进程CPU统计
        app_empty_cpu = sum(f['frame_load'] for f in frame_loads) if frame_loads else 0
        
        # 总CPU浪费
        total_wasted_cpu = rs_skip_cpu + app_empty_cpu
        
        # 使用公共模块EmptyFrameResultBuilder构建结果
        result = self.result_builder.build_result(
            frame_loads=frame_loads,
            total_load=0,  # RS无total_load
            detection_stats={
                # 追溯统计
                'total_skip_frames': total_skip_frames,
                'total_skip_events': total_skip_events,
                'trace_accuracy': trace_accuracy,
                'traced_success_count': traced_success,
                'rs_api_success': rs_api_success,
                'nativewindow_success': nw_api_success,
                'failed': failed,
                
                # RS进程CPU统计【新增】
                'rs_skip_cpu': rs_skip_cpu,
                'rs_skip_percentage': 0.0,  # 可选，需要rs_total_cpu
                
                # 应用进程CPU统计
                'app_empty_cpu': app_empty_cpu,
                
                # 总计
                'total_wasted_cpu': total_wasted_cpu,
            }
        )
        
        timing_stats['result_build'] = time.time() - result_build_start
        return result
    
    def _build_result(self, skip_frames: list, traced_results: list, 
                     timing_stats: dict) -> dict:
        """阶段5：结果构建（旧实现，已弃用，保留作为参考）
        
        注意：此方法已被_build_result_unified替代，使用公共模块EmptyFrameResultBuilder
        完全遵循EmptyFrameAnalyzer的输出格式
        
        Args:
            skip_frames: skip帧列表
            traced_results: 追溯结果列表
            timing_stats: 耗时统计字典
        
        Returns:
            dict: 分析结果（统一格式）
        """
        result_build_start = time.time()
        
        # 统计
        total_skip_frames = len(skip_frames)
        total_skip_events = sum(f.get('skip_count', 0) for f in skip_frames)
        
        traced_success = sum(1 for r in traced_results 
                           if r['trace_result'] and r['trace_result'].get('app_frame'))
        trace_accuracy = (traced_success / total_skip_frames * 100) if total_skip_frames > 0 else 0.0
        
        rs_api_success = timing_stats.get('rs_api_success', 0)
        nw_api_success = timing_stats.get('nw_api_success', 0)
        failed = timing_stats.get('trace_failed', 0)
        
        # CPU统计
        total_wasted = 0
        frames_with_cpu = 0
        for r in traced_results:
            if r['trace_result'] and r['trace_result'].get('app_frame'):
                app_frame = r['trace_result']['app_frame']
                cpu_waste = app_frame.get('cpu_waste', {})
                if cpu_waste.get('has_perf_data'):
                    total_wasted += cpu_waste.get('wasted_instructions', 0)
                    frames_with_cpu += 1
        
        avg_wasted = (total_wasted / frames_with_cpu) if frames_with_cpu > 0 else 0.0
        
        # 严重程度评估（参考EmptyFrameAnalyzer的方式）
        severity_level, severity_description = self._assess_severity(
            total_skip_frames, trace_accuracy, traced_success
        )
        
        # 提取Top N帧
        top_skip_frames = self._extract_top_frames(traced_results, self.top_n)
        
        # 构建结果（完全遵循EmptyFrameAnalyzer的格式）
        result = {
            'status': 'success',
            'summary': {
                'total_skip_frames': int(total_skip_frames),
                'total_skip_events': int(total_skip_events),
                'traced_success_count': int(traced_success),
                'trace_accuracy': float(trace_accuracy),
                'rs_api_success': int(rs_api_success),
                'nativewindow_success': int(nw_api_success),
                'failed': int(failed),
                'total_wasted_instructions': int(total_wasted),
                'avg_wasted_instructions': float(avg_wasted),
                'frames_with_cpu_data': int(frames_with_cpu),
                # 严重程度评估（参考EmptyFrameAnalyzer）
                'severity_level': severity_level,
                'severity_description': severity_description,
            },
            'top_frames': {
                'top_skip_frames': top_skip_frames,  # Top N skip帧详情
            },
        }
        
        # 添加警告（如果追溯成功率低）
        if trace_accuracy < 50.0:
            trace_warning = (
                f"警告：RS Skip帧追溯成功率较低({trace_accuracy:.1f}%)，"
                f"可能导致CPU浪费统计不准确。建议检查数据质量。"
            )
            result['summary']['trace_warning'] = trace_warning
            logging.warning(trace_warning)
        
        timing_stats['result_build'] = time.time() - result_build_start
        return result
    
    def _build_empty_result(self, timing_stats: dict) -> dict:
        """构建空结果（完全遵循EmptyFrameAnalyzer的格式）
        
        Args:
            timing_stats: 耗时统计字典
        
        Returns:
            dict: 空结果字典
        """
        result_build_start = time.time()
        
        result = {
            'status': 'success',
            'summary': {
                'total_skip_frames': 0,
                'total_skip_events': 0,
                'traced_success_count': 0,
                'trace_accuracy': 0.0,
                'rs_api_success': 0,
                'nativewindow_success': 0,
                'failed': 0,
                'total_wasted_instructions': 0,
                'avg_wasted_instructions': 0.0,
                'frames_with_cpu_data': 0,
                'severity_level': 'normal',
                'severity_description': '正常：未检测到RS Skip帧。'
            },
            'top_frames': {
                'top_skip_frames': [],
            },
        }
        
        timing_stats['result_build'] = time.time() - result_build_start
        return result
    
    def _assess_severity(self, total_skip: int, trace_accuracy: float, 
                        traced_success: int) -> tuple:
        """评估严重程度（参考EmptyFrameAnalyzer的分级标准）
        
        评估标准：
        1. 追溯成功率：< 50% = critical
        2. Skip帧数量：< 10 = normal, < 100 = moderate, >= 100 = severe
        
        Args:
            total_skip: 总skip帧数
            trace_accuracy: 追溯成功率
            traced_success: 追溯成功数
        
        Returns:
            (severity_level, severity_description)
        """
        # 追溯成功率评估
        if trace_accuracy < 50.0:
            return ("critical", 
                   f"严重：RS Skip帧追溯成功率仅{trace_accuracy:.1f}%，"
                   f"数据质量差，无法准确评估CPU浪费。")
        
        # Skip帧数量评估
        if total_skip < 10:
            return ("normal", 
                   f"正常：仅检测到{total_skip}个RS Skip帧，属于正常范围。"
                   f"追溯成功率{trace_accuracy:.1f}%。")
        elif total_skip < 100:
            return ("moderate", 
                   f"较为严重：检测到{total_skip}个RS Skip帧，建议关注。"
                   f"追溯成功率{trace_accuracy:.1f}%。")
        else:
            return ("severe", 
                   f"严重：检测到{total_skip}个RS Skip帧，需要优先优化。"
                   f"追溯成功率{trace_accuracy:.1f}%。")
    
    def _extract_top_frames(self, traced_results: list, top_n: int) -> list:
        """提取Top N skip帧（按CPU浪费排序）
        
        Args:
            traced_results: 追溯结果列表
            top_n: Top N数量
        
        Returns:
            list: Top N skip帧列表
        """
        # 提取有CPU数据的帧
        frames_with_cpu = []
        for result in traced_results:
            if result['trace_result'] and result['trace_result'].get('app_frame'):
                skip_frame = result['skip_frame']
                app_frame = result['trace_result']['app_frame']
                cpu_waste = app_frame.get('cpu_waste', {})
                
                if cpu_waste.get('has_perf_data'):
                    frames_with_cpu.append({
                        'rs_frame_id': skip_frame['frame_id'],
                        'rs_frame_ts': skip_frame['ts'],
                        'skip_count': skip_frame['skip_count'],
                        'app_frame_id': app_frame.get('frame_id'),
                        'app_frame_ts': app_frame.get('frame_ts'),
                        'trace_method': result['trace_method'],
                        'wasted_instructions': cpu_waste.get('wasted_instructions', 0),
                        'thread_name': app_frame.get('thread_name', 'N/A'),
                        'process_name': app_frame.get('process_name', 'N/A'),
                        'pid': app_frame.get('pid')
                    })
        
        # 排序并返回Top N
        frames_with_cpu.sort(key=lambda x: x['wasted_instructions'], reverse=True)
        return frames_with_cpu[:top_n]
    
    def _log_analysis_complete(self, total_time: float, timing_stats: dict) -> None:
        """记录分析完成日志（完全遵循EmptyFrameAnalyzer的风格）
        
        Args:
            total_time: 总耗时
            timing_stats: 各阶段耗时统计
        """
        logging.info('RS Skip分析总耗时: %.3f秒', total_time)
        logging.info(
            '各阶段耗时占比: '
            '检测%.1f%%, '
            '预加载缓存%.1f%%, '
            '追溯%.1f%%, '
            'CPU计算%.1f%%, '
            '结果构建%.1f%%',
            timing_stats.get('detect_skip', 0) / total_time * 100 if total_time > 0 else 0,
            timing_stats.get('preload_cache', 0) / total_time * 100 if total_time > 0 else 0,
            timing_stats.get('trace_to_app', 0) / total_time * 100 if total_time > 0 else 0,
            timing_stats.get('cpu_calculation', 0) / total_time * 100 if total_time > 0 else 0,
            timing_stats.get('result_build', 0) / total_time * 100 if total_time > 0 else 0,
        )

