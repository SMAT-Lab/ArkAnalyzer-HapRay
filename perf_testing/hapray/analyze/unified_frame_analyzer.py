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

import json
import logging
import os
from typing import Any, Optional

from hapray.analyze.base_analyzer import BaseAnalyzer
from hapray.core.common.frame.frame_core_analyzer import FrameAnalyzerCore


class UnifiedFrameAnalyzer(BaseAnalyzer):
    """统一帧分析器 - 整合帧负载、空帧、卡顿帧和VSync异常分析

    合并了以下四个分析器的功能：
    1. FrameLoadAnalyzer - 帧负载分析
    2. EmptyFrameAnalyzer - 空帧分析
    3. FrameDropAnalyzer - 卡顿帧分析
    4. VSyncAnomalyAnalyzer - VSync异常分析

    主要职责：
    1. 统一管理所有帧相关的分析
    2. 使用FrameAnalyzerCore进行核心分析
    3. 保持各分析器的输出路径不变
    4. 优化性能，共享缓存和数据库连接
    """

    def __init__(self, scene_dir: str, top_frames_count: int = 10):
        """
        初始化统一帧分析器

        Args:
            scene_dir: 场景目录路径
            top_frames_count: Top帧数量，默认10
        """
        # 使用一个主路径，但会输出到多个路径
        super().__init__(scene_dir, 'trace/unifiedFrame')
        self.top_frames_count = top_frames_count
        # 定义各分析器的输出路径
        self.report_paths = {
            'frameLoads': 'trace/frameLoads',
            'emptyFrame': 'trace/emptyFrame',
            'frames': 'trace/frames',
            'vsyncAnomaly': 'trace/vsyncAnomaly',
        }
        # 存储各分析器的结果
        self.frame_loads_results = {}
        self.empty_frame_results = {}
        self.frame_drop_results = {}
        self.vsync_anomaly_results = {}

    def _analyze_impl(
        self, step_dir: str, trace_db_path: str, perf_db_path: str, app_pids: list
    ) -> Optional[dict[str, Any]]:
        """实现统一帧分析逻辑

        在 _analyze_impl 中新建 FrameAnalyzerCore，传入 trace_db_path, perf_db_path, app_pids

        Args:
            step_dir: 步骤标识符
            trace_db_path: trace数据库路径
            perf_db_path: perf数据库路径
            app_pids: 应用进程ID列表

        Returns:
            Dictionary containing unified frame analysis results, or None if no data
        """
        if not os.path.exists(trace_db_path):
            logging.warning('Trace database not found: %s', trace_db_path)
            return None

        if not os.path.exists(perf_db_path):
            logging.warning('Perf database not found: %s', perf_db_path)
            return None

        try:
            # 新建 FrameAnalyzerCore，传入 trace_db_path, perf_db_path, app_pids, step_dir
            # 数据库连接在构造函数中建立
            core_analyzer = FrameAnalyzerCore(
                trace_db_path=trace_db_path,
                perf_db_path=perf_db_path,
                app_pids=app_pids,
                step_dir=step_dir,
            )

            # 1. 帧负载分析
            frame_loads_result = self._analyze_frame_loads(core_analyzer, step_dir)
            if frame_loads_result:
                self.frame_loads_results[step_dir] = frame_loads_result

            # 2. 空帧分析
            empty_frame_result = self._analyze_empty_frames(core_analyzer, step_dir)
            if empty_frame_result:
                self.empty_frame_results[step_dir] = empty_frame_result

            # 3. 卡顿帧分析
            frame_drop_result = self._analyze_frame_drops(core_analyzer, step_dir)
            if frame_drop_result:
                self.frame_drop_results[step_dir] = frame_drop_result

            # 4. VSync异常分析
            vsync_anomaly_result = core_analyzer.analyze_vsync_anomalies()
            if vsync_anomaly_result:
                self.vsync_anomaly_results[step_dir] = vsync_anomaly_result

            # 返回合并结果（用于主报告）
            return {
                'frameLoads': frame_loads_result,
                'emptyFrame': empty_frame_result,
                'frames': frame_drop_result,
                'vsyncAnomaly': vsync_anomaly_result,
            }

        except Exception as e:
            logging.error('Unified frame analysis failed for step %s: %s', step_dir, str(e))
            return None
        finally:
            # 关闭数据库连接
            if 'core_analyzer' in locals():
                core_analyzer.close_connections()

    def _analyze_frame_loads(self, core_analyzer: FrameAnalyzerCore, step_dir: str) -> Optional[dict[str, Any]]:
        """分析帧负载"""
        try:
            return core_analyzer.analyze_frame_loads_fast(step_id=step_dir)

        except Exception as e:
            logging.error('Frame load analysis failed for step %s: %s', step_dir, str(e))
            return None

    def _analyze_empty_frames(self, core_analyzer: FrameAnalyzerCore, step_dir: str) -> Optional[dict[str, Any]]:
        """分析空帧"""
        try:
            return core_analyzer.analyze_empty_frames()

        except Exception as e:
            logging.error('Empty frame analysis failed for step %s: %s', step_dir, str(e))
            return None

    def _analyze_frame_drops(self, core_analyzer: FrameAnalyzerCore, step_dir: str) -> Optional[dict[str, Any]]:
        """分析卡顿帧"""
        try:
            return core_analyzer.analyze_stuttered_frames()

        except Exception as e:
            logging.error('Frame drop analysis failed for step %s: %s', step_dir, str(e))
            return None

    def write_report(self, result: dict):
        """写入报告 - 支持多个输出路径

        保持各分析器的输出路径不变，分别写入对应的JSON文件

        Args:
            result: 主结果字典
        """
        # 写入帧负载分析结果
        if self.frame_loads_results:
            self._write_single_report(self.frame_loads_results, self.report_paths['frameLoads'])

        # 写入空帧分析结果
        if self.empty_frame_results:
            self._write_single_report(self.empty_frame_results, self.report_paths['emptyFrame'])

        # 写入卡顿帧分析结果
        if self.frame_drop_results:
            self._write_single_report(self.frame_drop_results, self.report_paths['frames'])

        # 写入VSync异常分析结果
        if self.vsync_anomaly_results:
            self._write_single_report(self.vsync_anomaly_results, self.report_paths['vsyncAnomaly'])

        # 同时更新主结果字典
        if self.frame_loads_results:
            self._update_result_dict(result, self.frame_loads_results, self.report_paths['frameLoads'])
        if self.empty_frame_results:
            self._update_result_dict(result, self.empty_frame_results, self.report_paths['emptyFrame'])
        if self.frame_drop_results:
            self._update_result_dict(result, self.frame_drop_results, self.report_paths['frames'])
        if self.vsync_anomaly_results:
            self._update_result_dict(result, self.vsync_anomaly_results, self.report_paths['vsyncAnomaly'])

    def _write_single_report(self, results: dict, report_path: str):
        """写入单个报告文件"""
        if not results:
            self.logger.warning('No results to write. Skipping report generation for %s', report_path)
            return

        try:
            file_path = os.path.join(self.scene_dir, 'report', report_path.replace('/', '_') + '.json')
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, sort_keys=True)
        except Exception as e:
            self.logger.exception('Failed to write report: %s', str(e))

    def _update_result_dict(self, result: dict, results: dict, report_path: str):
        """更新主结果字典"""
        dict_path = report_path.split('/')
        v = result
        for key in dict_path:
            if key == dict_path[-1]:
                break
            if key not in v:
                v[key] = {}
            v = v[key]
        v[dict_path[-1]] = results

    def _clean_data_for_json(self, data):
        """清理数据，确保JSON序列化安全"""
        if isinstance(data, dict):
            return {key: self._clean_data_for_json(value) for key, value in data.items()}
        if isinstance(data, list):
            return [self._clean_data_for_json(item) for item in data]
        if hasattr(data, 'dtype') and hasattr(data, 'item'):
            # numpy类型
            ans = data.item()
            if hasattr(data, 'isna') and data.isna():
                ans = 0
            elif 'int' in str(data.dtype):
                ans = int(data)
            elif 'float' in str(data.dtype):
                ans = float(data)
            return ans
        return data
