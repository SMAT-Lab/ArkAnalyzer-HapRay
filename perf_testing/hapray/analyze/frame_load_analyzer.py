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
import os
from typing import Dict, Any, Optional

from hapray.analyze.base_analyzer import BaseAnalyzer
from hapray.core.common.frame import FrameAnalyzerCore
from hapray.core.common.frame.frame_core_cache_manager import FrameCacheManager


class FrameLoadAnalyzer(BaseAnalyzer):
    """Analyzer for frame load analysis
    
    帧负载分析器 - 遵循正确的架构设计：
    1. 继承BaseAnalyzer，负责业务逻辑协调
    2. 使用FrameAnalyzerCore进行核心分析
    3. 不直接连接数据库，通过core层访问数据
    4. 专注于帧负载分析的业务逻辑
    """

    def __init__(self, scene_dir: str, top_frames_count: int = 10):
        """
        初始化帧负载分析器
        
        Args:
            scene_dir: 场景目录路径
            top_frames_count: Top帧数量，默认10
        """
        super().__init__(scene_dir, 'trace/frameLoads')
        self.top_frames_count = top_frames_count
        # 初始化核心分析器
        self.core_analyzer = FrameAnalyzerCore()

    def _analyze_impl(self,
                      step_dir: str,
                      trace_db_path: str,
                      perf_db_path: str,
                      app_pids: list) -> Optional[Dict[str, Any]]:
        """实现帧负载分析逻辑

        Args:
            step_dir: 步骤目录
            trace_db_path: trace数据库路径
            perf_db_path: perf数据库路径
            app_pids: 应用进程ID列表

        Returns:
            Optional[Dict[str, Any]]: 分析结果
        """
        logging.info("Analyzing frame loads for %s...", step_dir)
            
        if not os.path.exists(trace_db_path):
            logging.warning("Trace database not found: %s", trace_db_path)
            return None

        if not os.path.exists(perf_db_path):
            logging.warning("Perf database not found: %s", perf_db_path)
            return None

        try:
            # 使用核心分析器进行帧负载分析
            # 核心分析器负责所有数据库连接和数据处理
            frame_loads_data = self.core_analyzer.analyze_comprehensive_frames(
                trace_db_path=trace_db_path,
                perf_db_path=perf_db_path,
                app_pids=app_pids,
                scene_dir=self.scene_dir,
                step_id=step_dir
            )
            
            if not frame_loads_data:
                logging.info("No frame load data found for step %s", step_dir)
                return None
            
            # 生成帧负载分析结果
            logging.debug("Generating frame load analysis result...")
            
            # 获取帧负载统计信息
            statistics = FrameCacheManager.get_frame_load_statistics(step_dir)
            
            # 获取Top帧数据
            top_frames = FrameCacheManager.get_top_frame_loads(step_dir, self.top_frames_count)
            
            # 获取所有帧负载数据用于时间线
            all_frame_loads = FrameCacheManager.get_frame_loads(step_dir)
            
            # 调试信息：检查缓存中的数据
            logging.debug("Cache frame loads count: %d", len(all_frame_loads))
            if all_frame_loads:
                sample_frame = all_frame_loads[0]
                logging.debug("Sample frame from cache: ts=%s, load=%s, process_name=%s, frame_type=%s, vsync=%s", 
                             sample_frame.get('ts'), sample_frame.get('frame_load'), 
                             sample_frame.get('process_name'), sample_frame.get('frame_type'), 
                             sample_frame.get('vsync'))
            
            # 生成时间线数据
            load_timeline = self._generate_load_timeline(all_frame_loads)
            
            # 构建最终结果
            result = {
                'statistics': statistics,
                'top_frames': top_frames,
                'load_timeline': load_timeline,
                'total_frames': len(all_frame_loads)
            }
            
            return result

        except Exception as e:
            logging.error("Frame load analysis failed for step %s: %s", step_dir, str(e))
            return None

    def _generate_load_timeline(self, frame_loads: list) -> list:
        """生成帧负载时间线数据
        
        Args:
            frame_loads: 帧负载数据列表
            
        Returns:
            list: 时间线数据
        """
        if not frame_loads:
            return []
        
        timeline = []
        for frame in frame_loads:
            timeline.append({
                'timestamp': frame.get('ts', 0),
                'frame_load': frame.get('frame_load', 0),
                'process_name': frame.get('process_name', ''),
                'frame_type': frame.get('frame_type', ''),
                'vsync': frame.get('vsync', 0)
            })
        
        return timeline

    def _clean_data_for_json(self, data):
        """清理数据，确保JSON序列化安全"""
        if isinstance(data, dict):
            return {key: self._clean_data_for_json(value) for key, value in data.items()}
        elif isinstance(data, list):
            return [self._clean_data_for_json(item) for item in data]
        elif hasattr(data, 'dtype') and hasattr(data, 'item'):
            # numpy类型
            if hasattr(data, 'isna') and data.isna():
                return 0
            elif 'int' in str(data.dtype):
                return int(data)
            elif 'float' in str(data.dtype):
                return float(data)
            else:
                return data.item()
        else:
            return data 