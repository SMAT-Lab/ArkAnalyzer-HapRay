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

import base64
import enum
import gzip
import json
import logging
import os
import re
import shutil
import zlib
from pathlib import Path
from typing import Any, Optional

import pandas as pd

from hapray import VERSION
from hapray.actions.hilog_action import HilogAction
from hapray.analyze import analyze_data
from hapray.analyze.symbol_statistic_analyzer import SymbolStatisticAnalyzer
from hapray.core.common.excel_utils import ExcelReportSaver
from hapray.core.common.exe_utils import ExeUtils
from hapray.core.config.config import Config
from hapray.mode.mode import Mode


class DataType(enum.Enum):
    JSON = 0
    BASE64_GZIP_JSON = 1


class ReportData:
    """封装报告生成所需的所有数据"""

    def __init__(self, scene_dir: str, result: dict):
        self.scene_dir = scene_dir
        self.perf_data = []
        self.result = {
            **{
                'version': VERSION,
                'type': DataType.BASE64_GZIP_JSON.value,
                'versionCode': 1,
                'basicInfo': {},
                'steps': [],  # 步骤基本信息（step_id, step_name）
                'perf': {'steps': []},  # 性能数据步骤（不包含step_id和step_name）
            },
            **result,
        }

    @classmethod
    def from_paths(cls, scene_dir: str, result: dict):
        """从文件路径加载数据

        Args:
            scene_dir: 场景目录路径
            result: 分析结果字典
        """
        perf_data_path = os.path.join(scene_dir, 'hiperf', 'hiperf_info.json')
        data = cls(scene_dir, result)
        steps_path = os.path.join(scene_dir, 'steps.json')
        data._load_steps_data(steps_path)
        # 当perf.data不存在时，hiperf_info.json可能不存在，设为非必需
        data.load_perf_data(perf_data_path, required=False)
        data.load_trace_data(scene_dir)
        return data

    def __str__(self):
        # 路径1: Base64编码的gzip压缩JSON
        # 清理数据中的NaN值以确保JSON序列化安全
        cleaned_result = self._clean_data_for_json(self.result)

        # 特殊处理火焰图数据：按步骤单独压缩
        cleaned_result = self._compress_flame_graph_by_steps(cleaned_result)

        # 特殊处理UI动画数据：按步骤单独压缩
        cleaned_result = self._compress_ui_animate_by_steps(cleaned_result)

        # 特殊处理UI原始数据：按步骤单独压缩
        cleaned_result = self._compress_ui_raw_by_steps(cleaned_result)

        # 特殊处理 trace 数据：压缩大数据字段
        cleaned_result = self._compress_trace_data(cleaned_result)

        json_str = json.dumps(cleaned_result)
        with open(os.path.join(self.scene_dir, 'report', 'hapray_report.json'), 'w', encoding='utf-8') as f:
            f.write(json_str)
        compressed_bytes = zlib.compress(json_str.encode('utf-8'), level=9)
        base64_bytes = base64.b64encode(compressed_bytes)
        return base64_bytes.decode('ascii')

    def _clean_data_for_json(self, data):  # pylint: disable=too-many-return-statements
        """清理数据，将numpy类型和NaN值转换为标准Python类型以确保JSON序列化"""
        # pylint: disable=duplicate-code
        if isinstance(data, dict):
            return {key: self._clean_data_for_json(value) for key, value in data.items()}
        if isinstance(data, list):
            return [self._clean_data_for_json(item) for item in data]
        if hasattr(data, 'dtype') and hasattr(data, 'item'):
            # numpy类型
            if pd.isna(data):
                # 处理NaN值
                if 'int' in str(data.dtype):
                    return 0
                if 'float' in str(data.dtype):
                    return 0.0
                return None
            if 'int' in str(data.dtype):
                return int(data)
            if 'float' in str(data.dtype):
                return float(data)
            return data.item()
        if hasattr(data, '__class__') and 'int64' in str(data.__class__):
            # 其他可能的int64类型
            if pd.isna(data):
                return 0
            return int(data)
        if pd.isna(data):
            # 处理pandas NaN值
            if isinstance(data, (int, float)):
                return 0
            return None
        return data
        # pylint: enable=duplicate-code

    def _compress_flame_graph_by_steps(self, data):
        """按步骤压缩火焰图数据，避免字符串过长"""
        if not isinstance(data, dict):
            return data

        # 检查是否有火焰图数据
        if 'more' not in data or 'flame_graph' not in data['more']:
            return data

        flame_graph_data = data['more']['flame_graph']
        if not isinstance(flame_graph_data, dict):
            return data

        # 按步骤压缩火焰图数据
        compressed_flame_graph = {}

        for step_key, step_data in flame_graph_data.items():
            if isinstance(step_data, str) and step_data:
                try:
                    # 压缩单个步骤的数据
                    compressed_bytes = zlib.compress(step_data.encode('utf-8'), level=9)
                    base64_bytes = base64.b64encode(compressed_bytes)
                    compressed_flame_graph[step_key] = base64_bytes.decode('ascii')

                    # 记录压缩效果
                    original_size = len(step_data)
                    compressed_size = len(compressed_flame_graph[step_key])
                    compression_ratio = (1 - compressed_size / original_size) * 100
                    logging.info(
                        '火焰图数据压缩 %s: %d -> %d 字节 (压缩率: %.1f%%)',
                        step_key,
                        original_size,
                        compressed_size,
                        compression_ratio,
                    )
                except Exception as e:
                    logging.warning('压缩火焰图数据失败 %s: %s', step_key, str(e))
                    # 压缩失败时保持原数据
                    compressed_flame_graph[step_key] = step_data
            else:
                # 非字符串数据或空数据保持不变
                compressed_flame_graph[step_key] = step_data

        # 更新数据结构
        data['more']['flame_graph'] = compressed_flame_graph
        return data

    def _compress_ui_animate_by_steps(self, data):
        """按步骤压缩UI动画数据，避免字符串过长

        UI动画数据包含大量base64编码的图片，需要压缩以减小文件大小
        """
        if not isinstance(data, dict):
            return data

        # 检查是否有UI动画数据
        if 'ui' not in data or 'animate' not in data['ui']:
            return data

        ui_animate_data = data['ui']['animate']
        if not isinstance(ui_animate_data, dict):
            return data

        # 按步骤压缩UI动画数据
        compressed_ui_animate = {}

        for step_key, step_data in ui_animate_data.items():
            if isinstance(step_data, dict):
                try:
                    # 将整个步骤数据转换为 JSON 字符串
                    step_json = json.dumps(step_data)
                    original_size = len(step_json)

                    # 压缩步骤数据
                    compressed_bytes = zlib.compress(step_json.encode('utf-8'), level=9)
                    base64_bytes = base64.b64encode(compressed_bytes)
                    compressed_step = base64_bytes.decode('ascii')

                    # 使用压缩后的数据
                    compressed_ui_animate[step_key] = {
                        'compressed': True,  # 标记为已压缩
                        'data': compressed_step,  # 压缩后的数据
                    }

                    # 记录压缩效果
                    compressed_size = len(compressed_step)
                    compression_ratio = (1 - compressed_size / original_size) * 100
                    logging.info(
                        'UI动画数据压缩 %s: %d -> %d 字节 (压缩率: %.1f%%)',
                        step_key,
                        original_size,
                        compressed_size,
                        compression_ratio,
                    )
                except Exception as e:
                    logging.warning('压缩UI动画数据失败 %s: %s', step_key, str(e))
                    # 压缩失败时保持原数据
                    compressed_ui_animate[step_key] = step_data
            else:
                # 非预期格式的数据保持不变
                compressed_ui_animate[step_key] = step_data

        # 更新数据结构
        data['ui']['animate'] = compressed_ui_animate
        return data

    def _compress_ui_raw_by_steps(self, data):
        """按步骤压缩UI原始数据，避免文件过大

        UI原始数据包含大量base64编码的截图和组件树文本，需要压缩以减小文件大小
        """
        if not isinstance(data, dict):
            return data

        # 检查是否有UI原始数据
        if 'ui' not in data or 'raw' not in data['ui']:
            return data

        ui_raw_data = data['ui']['raw']
        if not isinstance(ui_raw_data, dict):
            return data

        # 按步骤压缩UI原始数据
        compressed_ui_raw = {}

        for step_key, step_data in ui_raw_data.items():
            if isinstance(step_data, dict):
                try:
                    # 将整个步骤数据转换为 JSON 字符串
                    step_json = json.dumps(step_data)
                    original_size = len(step_json)

                    # 压缩步骤数据
                    compressed_bytes = zlib.compress(step_json.encode('utf-8'), level=9)
                    base64_bytes = base64.b64encode(compressed_bytes)
                    compressed_step = base64_bytes.decode('ascii')

                    # 使用压缩后的数据
                    compressed_ui_raw[step_key] = {
                        'compressed': True,  # 标记为已压缩
                        'data': compressed_step,  # 压缩后的数据
                    }

                    # 记录压缩效果
                    compressed_size = len(compressed_step)
                    compression_ratio = (1 - compressed_size / original_size) * 100
                    logging.info(
                        'UI原始数据压缩 %s: %d -> %d 字节 (压缩率: %.1f%%)',
                        step_key,
                        original_size,
                        compressed_size,
                        compression_ratio,
                    )
                except Exception as e:
                    logging.warning('压缩UI原始数据失败 %s: %s', step_key, str(e))
                    # 压缩失败时保持原数据
                    compressed_ui_raw[step_key] = step_data
            else:
                # 非预期格式的数据保持不变
                compressed_ui_raw[step_key] = step_data

        # 更新数据结构
        data['ui']['raw'] = compressed_ui_raw
        return data

    def _compress_trace_data(self, data):
        """压缩 trace 数据中的大字段（如 frames、emptyFrame 等）

        这些数据通常包含大量的帧数据，需要压缩以减小 HTML 文件大小
        """
        if not isinstance(data, dict):
            return data

        # 检查是否有 trace 数据
        if 'trace' not in data or not isinstance(data['trace'], dict):
            return data

        trace_data = data['trace']

        # 需要压缩的 trace 字段列表（这些字段通常包含大量数据）
        compress_fields = ['frames', 'emptyFrame', 'frameLoads', 'vsyncAnomaly']

        for field in compress_fields:
            if field not in trace_data:
                continue

            field_data = trace_data[field]
            if not isinstance(field_data, dict):
                continue

            try:
                # 将字段数据转换为 JSON 字符串
                field_json = json.dumps(field_data)
                original_size = len(field_json)

                # 只压缩大于 100KB 的数据
                if original_size < 100 * 1024:
                    continue

                # 压缩数据
                compressed_bytes = zlib.compress(field_json.encode('utf-8'), level=9)
                base64_bytes = base64.b64encode(compressed_bytes)
                compressed_data = base64_bytes.decode('ascii')

                # 替换为压缩后的数据
                trace_data[field] = {
                    'compressed': True,
                    'data': compressed_data,
                }

                # 记录压缩效果
                compressed_size = len(compressed_data)
                compression_ratio = (1 - compressed_size / original_size) * 100
                logging.info(
                    'Trace 数据压缩 %s: %d -> %d 字节 (压缩率: %.1f%%)',
                    field,
                    original_size,
                    compressed_size,
                    compression_ratio,
                )
            except Exception as e:
                logging.warning('压缩 trace 数据失败 %s: %s', field, str(e))
                # 压缩失败时保持原数据
                continue

        return data

    def _load_steps_data(self, path: str):
        """加载步骤基本信息

        Args:
            path: steps.json 文件路径
        """
        steps_data = self._load_json_safe(path, default=[])
        if len(steps_data) == 0:
            raise FileNotFoundError(f'steps.json not found: {path}')

        # 提取 step_id 和 step_name 到 self.result['steps']
        self.result['steps'] = [
            {
                'step_id': step.get('stepIdx'),
                'step_name': step.get('name'),
            }
            for step in steps_data
            if 'stepIdx' in step and 'name' in step
        ]

    def load_perf_data(self, path, required: bool = True):
        """加载性能数据

        Args:
            path: hiperf_info.json 文件路径
            required: 是否必须存在（默认True，支持仅内存分析模式设为False）
        """
        self.perf_data = self._load_json_safe(path, default=[])
        if len(self.perf_data) == 0:
            if required:
                raise FileNotFoundError(f'hiperf_info.json not found: {path}')
            logging.warning('hiperf_info.json not found: %s, skipping perf data loading', path)
            return
        first_entry = self.perf_data[0]
        self.result['perf']['steps'] = first_entry.get('steps', [])
        self.result['perf']['har'] = first_entry.get('har', {})
        self.result['basicInfo'] = {
            'rom_version': first_entry.get('rom_version', ''),
            'app_id': first_entry.get('app_id', ''),
            'app_name': first_entry.get('app_name', ''),
            'app_version': first_entry.get('app_version', ''),
            'scene': first_entry.get('scene', ''),
            'timestamp': first_entry.get('timestamp', 0),
        }

    def load_trace_data(self, scene_dir: str, required: bool = False):
        """加载 trace 相关数据

        Args:
            scene_dir: 场景目录路径
            required: 是否必须存在（默认False，支持仅内存分析模式）
        """
        report_dir = os.path.join(scene_dir, 'report')

        # 确保 trace 字段存在
        if 'trace' not in self.result:
            self.result['trace'] = {}

        # 加载各种 trace 数据
        trace_files = {
            'frames': 'trace_frames.json',
            'emptyFrame': 'trace_emptyFrame.json',
            'componentReuse': 'trace_componentReuse.json',
            'coldStart': 'trace_coldStart.json',
            'gc_thread': 'trace_gc_thread.json',
            'frameLoads': 'trace_frameLoads.json',
            'vsyncAnomaly': 'trace_vsyncAnomaly.json',
            'faultTree': 'trace_fault_tree.json',
        }

        for key, filename in trace_files.items():
            file_path = os.path.join(report_dir, filename)
            data = self._load_json_safe(file_path, default={})
            if data:  # 只有当数据不为空时才添加
                self.result['trace'][key] = data

        # 加载火焰图数据数据
        if 'more' not in self.result:
            self.result['more'] = {}

        flame_graph_path = os.path.join(report_dir, 'more_flame_graph.json')
        flame_graph_data = self._load_json_safe(flame_graph_path, default={})
        if flame_graph_data:
            self.result['more']['flame_graph'] = flame_graph_data
        elif required:
            logging.warning('Flame graph data not found at %s', flame_graph_path)

        # 加载 UI 动画数据
        if 'ui' not in self.result:
            self.result['ui'] = {}

        ui_animate_path = os.path.join(report_dir, 'ui_animate.json')
        ui_animate_data = self._load_json_safe(ui_animate_path, default={})
        if ui_animate_data:
            self.result['ui']['animate'] = ui_animate_data
            logging.info(f'Loaded UI Animate data: {len(ui_animate_data)} steps')

        # 加载 UI 原始数据（用于对比）
        ui_raw_path = os.path.join(report_dir, 'ui_raw.json')
        ui_raw_data = self._load_json_safe(ui_raw_path, default={})
        if ui_raw_data:
            self.result['ui']['raw'] = ui_raw_data
            logging.info(f'Loaded UI Raw data: {len(ui_raw_data)} steps')

    def _load_json_safe(self, path, default):
        """安全加载JSON文件，处理异常情况"""
        if not os.path.exists(path):
            logging.info('File not found: %s', path)
            return default

        try:
            with open(path, encoding='utf-8') as f:
                data = json.load(f)

            # 验证数据类型
            if isinstance(default, list) and not isinstance(data, list):
                logging.warning('Invalid format in %s, expected list but got %s', path, type(data).__name__)
                return default
            if isinstance(default, dict) and not isinstance(data, dict):
                logging.warning('Invalid format in %s, expected list but got %s', path, type(data).__name__)
                return default

            return data
        except json.JSONDecodeError as e:
            logging.error('JSON decoding error in %s: %s', path, str(e))
            return default
        except Exception as e:
            logging.error('Error loading %s: %s', path, str(e))
            return default


class ReportGenerator:
    """Generates and updates performance analysis reports"""

    def __init__(
        self,
        use_refined_lib_symbol: bool = False,
        export_comparison: bool = False,
        symbol_statistic: str = None,
        time_range_strings: list[str] = None,
    ):
        """Initialize ReportGenerator

        Args:
            use_refined_lib_symbol: Enable refined mode for memory analysis
            export_comparison: Export comparison Excel for memory analysis
            symbol_statistic: Path to SymbolsStatistic.txt for symbol analysis (optional)
            time_range_strings: List of time range strings in format "startTime-endTime" (optional)
        """
        self.report_template_path = os.path.abspath(ExeUtils.get_tools_dir('web', 'report_template.html'))
        self.use_refined_lib_symbol = use_refined_lib_symbol
        self.export_comparison = export_comparison
        self.symbol_statistic = symbol_statistic
        self.time_range_strings = time_range_strings or []

    def update_report(self, scene_dir: str, time_ranges: list[dict] = None) -> bool:
        """Update an existing performance report

        Args:
            scene_dir: Directory containing the scene data
            time_ranges: Optional list of time range filters
        """
        return self._generate_report(
            scene_dirs=[scene_dir],
            scene_dir=scene_dir,
            skip_round_selection=True,
            time_ranges=time_ranges,
            use_refined_lib_symbol=self.use_refined_lib_symbol,
            export_comparison=self.export_comparison,
        )

    def generate_report(self, scene_dirs: list[str], scene_dir: str, time_ranges: list[dict] = None) -> bool:
        """Generate a new performance analysis report"""
        return self._generate_report(
            scene_dirs,
            scene_dir,
            skip_round_selection=False,
            time_ranges=time_ranges,
            use_refined_lib_symbol=self.use_refined_lib_symbol,
            export_comparison=self.export_comparison,
        )

    def _generate_report(
        self,
        scene_dirs: list[str],
        scene_dir: str,
        skip_round_selection: bool,
        time_ranges: list[dict] = None,
        use_refined_lib_symbol: bool = False,
        export_comparison: bool = False,
    ) -> bool:
        """Core method for report generation and updating

        Args:
            scene_dirs: List of scene directories
            scene_dir: Current scene directory
            skip_round_selection: Whether to skip round selection
            time_ranges: Optional time range filters
            use_refined_lib_symbol: Enable refined mode for memory analysis
            export_comparison: Export comparison Excel for memory analysis
        """

        steps_path = os.path.join(scene_dir, 'steps.json')
        # 兼容性设计：如果 scene_dir 下没有 steps.json，从 scene_dir/hiperf/ 目录下拷贝
        if not os.path.exists(steps_path):
            hiperf_steps_path = os.path.join(scene_dir, 'hiperf', 'steps.json')
            if os.path.exists(hiperf_steps_path):
                try:
                    shutil.copy2(hiperf_steps_path, steps_path)
                    logging.info(f'Copied steps.json from {hiperf_steps_path} to {steps_path}')
                except Exception as e:
                    logging.warning(f'Failed to copy steps.json from hipef directory: {e}')

        # Step 1: Select round (only for new reports)
        if not skip_round_selection and not self._select_round(scene_dirs, scene_dir):
            logging.error('Round selection failed, aborting report generation')
            return False

        # Step 2: Analyze data (includes empty frames and frame drops analysis)
        result = analyze_data(
            scene_dir,
            time_ranges,
            use_refined_lib_symbol=use_refined_lib_symbol,
            export_comparison=export_comparison,
        )

        # Step 3: Generate step summary (summary.json & embed into main json)
        summary_list = self._generate_summary_json(scene_dir) or []
        if isinstance(summary_list, list):
            # 将 summary 直接注入到主 JSON 结构中，前端通过 window.jsonData 访问
            result['summary'] = summary_list

        # Step 4: Generate HTML report
        self._create_html_report(scene_dir, result)

        # Step 5: Process symbol statistics (if enabled)
        if self.symbol_statistic:
            self._process_symbol_statistics(scene_dir)

        logging.info('Report successfully %s for %s', 'updated' if skip_round_selection else 'generated', scene_dir)
        return True

    def _select_round(self, scene_dirs: list[str], scene_dir: str) -> bool:
        """Select the best round for report generation"""
        if not scene_dirs:
            logging.error('No scene directories provided for round selection')
            return False

        args = ['perf', '--choose', '-i', scene_dir]

        logging.debug('Selecting round with command: %s', ' '.join(args))
        return ExeUtils.execute_hapray_cmd(args)

    def _create_html_report(self, scene_dir: str, result: dict) -> None:
        """Create the final HTML report"""
        try:
            json_data_str = self._build_json_data(scene_dir, result)
            db_data_str = self._build_db_data(scene_dir)

            output_path = os.path.join(scene_dir, 'report', 'hapray_report.html')

            # Create directory structure if needed
            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            # Inject data (support multiple placeholders)
            self._inject_json_to_html(
                placeholders={
                    'JSON_DATA_PLACEHOLDER': json_data_str,
                    'DB_DATA_PLACEHOLDER': db_data_str,
                },
                html_path=self.report_template_path,
                output_path=output_path,
            )

            logging.info('HTML report created at %s', output_path)
        except Exception as e:
            logging.error('Failed to create HTML report: %s', str(e))

    def _process_symbol_statistics(self, report_dir: str):
        """Process symbol statistics for the report directory.

        Args:
            report_dir: Report directory path
        """
        if not self.symbol_statistic:
            return

        try:
            # Only process if in SIMPLE mode
            if Config.get('mode') != Mode.SIMPLE:
                logging.info('Symbol statistics only supported in SIMPLE mode, skipping')
                return

            logging.info('Processing symbol statistics...')
            time_ranges = self._parse_time_ranges(self.time_range_strings)
            analyzer = SymbolStatisticAnalyzer(report_dir, self.symbol_statistic, time_ranges)
            testcase_dirs = self._find_testcase_dirs(report_dir)

            logging.info('Processing symbol statistics for %d test cases', len(testcase_dirs))
            analyzer.process_all_testcases(testcase_dirs)
            analyzer.generate_excel(os.path.join(report_dir, 'symbol_statistics.xlsx'))
            logging.info('Symbol statistics processing completed')
        except Exception as e:
            logging.error('Failed to process symbol statistics: %s', str(e))

    @staticmethod
    def _parse_time_ranges(time_range_strings: list[str]) -> list[dict]:
        """Parse time range strings into structured format.

        Args:
            time_range_strings: List of time range strings in format "startTime-endTime"

        Returns:
            List of time range dictionaries with 'startTime' and 'endTime' keys
        """
        if not time_range_strings:
            return []

        time_ranges = []
        for tr_str in time_range_strings:
            try:
                parts = tr_str.split('-')
                if len(parts) == 2:
                    start_time = int(parts[0])
                    end_time = int(parts[1])
                    time_ranges.append({'startTime': start_time, 'endTime': end_time})
                else:
                    logging.warning('Invalid time range format: %s (expected "startTime-endTime")', tr_str)
            except ValueError:
                logging.warning('Invalid time range values: %s (expected integers)', tr_str)

        return time_ranges

    @staticmethod
    def _find_testcase_dirs(report_dir: str) -> list[str]:
        """Identifies valid test case directories in the report directory.

        A valid test case directory must have at least a 'hiperf' subdirectory.
        The 'htrace' subdirectory is optional (for perf-only mode).

        Args:
            report_dir: Root report directory path

        Returns:
            List of test case directory paths
        """
        testcase_dirs = []
        round_dir_pattern = re.compile(r'.*_round\d$')

        for entry in os.listdir(report_dir):
            if round_dir_pattern.match(entry):
                continue

            full_path = os.path.join(report_dir, entry)
            # Check if directory has hiperf (htrace is optional)
            if os.path.isdir(full_path) and os.path.exists(os.path.join(full_path, 'hiperf')):
                testcase_dirs.append(full_path)

        # If no subdirectories found, check if report_dir itself is a test case directory
        if not testcase_dirs and os.path.exists(os.path.join(report_dir, 'hiperf')):
            testcase_dirs.append(report_dir)

        return testcase_dirs

    @staticmethod
    def _build_json_data(scene_dir: str, result: dict) -> str:
        """构建JSON数据，支持三种分析模式

        Args:
            scene_dir: 场景目录路径
            result: 分析结果字典

        Returns:
            Base64编码的压缩JSON字符串
        """
        # 从配置中获取分析模式，默认为 'all'
        analysis_mode = Config.get('analysis_mode', 'all')

        # 根据分析模式决定是否加载性能数据
        load_perf = analysis_mode in ['all', 'perf']

        # 创建 ReportData 实例
        report_data = ReportData.from_paths(scene_dir, result)

        # 如果是仅内存分析模式，不加载性能数据
        if not load_perf:
            report_data.perf_data = []
            report_data.result['perf']['steps'] = []

        return str(report_data)

    @staticmethod
    def _build_db_data(scene_dir: str) -> str:
        """构建数据库文件数据（gzip+base64编码）

        Args:
            scene_dir: 场景目录路径

        Returns:
            Base64编码的gzip压缩数据库文件字符串，如果文件不存在则返回空字符串
        """
        # 数据库文件路径
        db_path = os.path.join(scene_dir, 'report', 'hapray_report.db')

        # 检查数据库文件是否存在
        if not os.path.exists(db_path):
            logging.warning('Database file not found: %s, returning empty string', db_path)
            return ''

        try:
            # 读取数据库文件
            with open(db_path, 'rb') as f:
                db_data = f.read()

            # 使用 gzip 压缩
            compressed_data = gzip.compress(db_data, compresslevel=9)

            # Base64 编码
            base64_data = base64.b64encode(compressed_data).decode('ascii')

            # 记录压缩效果
            original_size = len(db_data)
            compressed_size = len(compressed_data)
            base64_size = len(base64_data)
            compression_ratio = (1 - compressed_size / original_size) * 100 if original_size > 0 else 0

            logging.info(
                'Database file processed: %s -> %d bytes (compressed: %d, base64: %d, compression ratio: %.1f%%)',
                db_path,
                original_size,
                compressed_size,
                base64_size,
                compression_ratio,
            )

            return base64_data
        except Exception as e:
            logging.error('Failed to build database data: %s', str(e))
            return ''

    @staticmethod
    def _inject_json_to_html(placeholders: dict[str, str], html_path: str, output_path: str) -> None:
        """Inject data into an HTML template (support multiple placeholders)

        Args:
            placeholders: 占位符字典，key 为占位符字符串，value 为要替换的值
            html_path: HTML 模板文件路径
            output_path: 输出 HTML 文件路径
        """
        # Validate path
        if not os.path.exists(html_path):
            raise FileNotFoundError(f'HTML template not found: {html_path}')

        # Load HTML template
        with open(html_path, encoding='utf-8') as f:
            html_content = f.read()

        # Replace all placeholders
        for placeholder, value in placeholders.items():
            html_content = html_content.replace(placeholder, value)

        # Save the updated HTML
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)

        logging.debug('Injected %d placeholders into %s', len(placeholders), output_path)

    @staticmethod
    def _load_json_safe(path: str, default):
        """安全加载JSON文件，处理异常情况"""
        if not os.path.exists(path):
            logging.info('File not found: %s', path)
            return default

        try:
            with open(path, encoding='utf-8') as f:
                data = json.load(f)

            # 验证数据类型
            if isinstance(default, list) and not isinstance(data, list):
                logging.warning('Invalid format in %s, expected list but got %s', path, type(data).__name__)
                return default
            if isinstance(default, dict) and not isinstance(data, dict):
                logging.warning('Invalid format in %s, expected dict but got %s', path, type(data).__name__)
                return default

            return data
        except json.JSONDecodeError as e:
            logging.error('JSON decoding error in %s: %s', path, str(e))
            return default
        except Exception as e:
            logging.error('Error loading %s: %s', path, str(e))
            return default

    def _generate_summary_json(self, scene_dir: str) -> list[dict[str, Any]] | None:
        """Generate summary.json for each test step and return summary list

        Args:
            scene_dir: Scene directory path
        """
        try:
            report_dir = os.path.join(scene_dir, 'report')
            # Ensure report directory exists
            os.makedirs(report_dir, exist_ok=True)
            report_html_path = os.path.join(report_dir, 'hapray_report.html')

            # Load steps data from scene_dir root directory only
            steps_path = os.path.join(scene_dir, 'steps.json')
            steps_data = ReportGenerator._load_json_safe(steps_path, default=[])
            if not steps_data:
                logging.warning('No steps data found in scene_dir: %s, skipping summary.json generation', steps_path)
                return None

            # Load empty frame data
            empty_frame_path = os.path.join(report_dir, 'trace_emptyFrame.json')
            empty_frame_data = ReportGenerator._load_json_safe(empty_frame_path, default={})

            # Load perf data for tech_stack statistics
            perf_data_path = os.path.join(scene_dir, 'hiperf', 'hiperf_info.json')
            perf_data = ReportGenerator._load_json_safe(perf_data_path, default=[])

            # Load component reuse data
            component_reuse_path = os.path.join(report_dir, 'trace_componentReuse.json')
            component_reuse_data = ReportGenerator._load_json_safe(component_reuse_path, default={})

            # Load fault tree data
            fault_tree_path = os.path.join(report_dir, 'trace_fault_tree.json')
            fault_tree_data = ReportGenerator._load_json_safe(fault_tree_path, default={})

            # Load UI animate data (for image oversize & component tree stats)
            ui_animate_path = os.path.join(report_dir, 'ui_animate.json')
            ui_animate_data = ReportGenerator._load_json_safe(ui_animate_path, default={})

            # Run hilog analysis if log or hilog directory exists
            # Prioritize 'log' directory as it's the current standard
            hilog_dir = None
            if os.path.exists(os.path.join(scene_dir, 'log')):
                hilog_dir = os.path.join(scene_dir, 'log')
            elif os.path.exists(os.path.join(scene_dir, 'hilog')):
                hilog_dir = os.path.join(scene_dir, 'hilog')

            hilog_data = {}
            if hilog_dir:
                try:
                    hilog_data = self._run_hilog_analysis(hilog_dir, report_dir)
                except Exception as e:
                    logging.warning('Failed to run hilog analysis: %s', str(e))

            # Get scene name from scene_dir
            scene_name = os.path.basename(scene_dir)

            # Generate summary for each step
            summary_list = []
            for step in steps_data:
                step_idx = step.get('stepIdx')
                step.get('name', f'step{step_idx}')
                step_id = f'{scene_name}_step{step_idx}'

                # Get empty_frame data for this step
                step_empty_frame = self._get_empty_frame_for_step(empty_frame_data, step_idx)

                # Get tech_stack data for this step
                step_tech_stack = self._get_tech_stack_for_step(perf_data, step_idx)

                # Get component reuse data for this step
                step_component_reuse = self._get_component_reuse_for_step(component_reuse_data, step_idx)

                # Get fault tree data for this step (raw fault tree node, front-end再做可视化与标签)
                step_fault_tree = self._get_fault_tree_for_step(fault_tree_data, step_idx)

                # Get UI related summaries (image oversize & component tree on/off tree stats)
                step_image_oversize, step_component_tree = self._get_ui_summary_for_step(ui_animate_data, step_idx)

                # Get hilog data for this step
                step_hilog = self._get_hilog_for_step(hilog_data, step_idx)

                summary_item = {
                    'step_id': step_id,
                    'report_html_path': report_html_path,
                    'empty_frame': step_empty_frame,
                    'tech_stack': step_tech_stack,
                    'log': step_hilog,
                    # 新增：组件复用、故障树、Image 超尺寸、组件树上/未上树统计
                    'component_reuse': step_component_reuse,
                    'fault_tree': step_fault_tree,
                    'image_oversize': step_image_oversize,
                    'component_tree': step_component_tree,
                }
                summary_list.append(summary_item)

            # Save summary.json
            summary_path = os.path.join(report_dir, 'summary.json')
            # Ensure report directory exists before writing
            os.makedirs(os.path.dirname(summary_path), exist_ok=True)
            with open(summary_path, 'w', encoding='utf-8') as f:
                json.dump(summary_list, f, ensure_ascii=False, indent=4)

            logging.info('Summary JSON generated at %s', summary_path)

            return summary_list

        except Exception as e:
            logging.error('Failed to generate summary.json: %s', str(e))
            return None

    @staticmethod
    def _get_empty_frame_for_step(empty_frame_data: dict, step_idx: int) -> dict:
        """Get empty_frame statistics for a specific step

        Args:
            empty_frame_data: Empty frame data dictionary
            step_idx: Step index

        Returns:
            Dictionary with count and percentage
        """
        step_key = f'step{step_idx}'
        step_data = empty_frame_data.get(step_key, {})

        if step_data.get('status') == 'success':
            summary = step_data.get('summary', {})
            count = summary.get('total_empty_frames', 0)
            percentage = summary.get('empty_frame_percentage', 0.0)
            return {
                'count': int(count),
                'percentage': f'{percentage:.2f}%',
            }
        return {'count': 0, 'percentage': '0.00%'}

    @staticmethod
    def _get_tech_stack_for_step(perf_data: list, step_idx: int) -> dict:
        """Get tech_stack statistics for a specific step

        Args:
            perf_data: Performance data list
            step_idx: Step index

        Returns:
            Dictionary with tech stack statistics
        """
        tech_stack = {
            'ArkUI': 0,
            'Web': 0,
            'RN': 0,
            'Flutter': 0,
            'KMP': 0,
            'APP_Processes': 0,
        }

        if not perf_data:
            return tech_stack

        # Get first entry's steps data
        first_entry = perf_data[0]
        steps = first_entry.get('steps', [])

        # Find the step data
        step_data = None
        for step in steps:
            if step.get('step_id') == step_idx:
                step_data = step
                break

        if not step_data:
            return tech_stack

        # Get data items for this step
        data_items = step_data.get('data', [])

        # Excluded component names (system components we don't want to classify)
        excluded_components = ['[shmm]']  # Shared memory components

        # Statistics
        for item in data_items:
            # Only count instruction events
            if item.get('eventType') != 1:  # 1 = INSTRUCTION_EVENT
                continue

            # Only count main app data
            # Check if this is main app data by processName or isMainApp flag
            process_name = item.get('processName', '')
            is_main_app = item.get('isMainApp', None)  # Use None as default to distinguish from False
            app_id = first_entry.get('app_id', '')

            # Count if: isMainApp is explicitly True, or isMainApp is None/missing and processName matches app_id
            if not (is_main_app is True or (is_main_app is None and process_name == app_id)):
                continue

            component_name = item.get('componentName', '')
            sub_category_name = item.get('subCategoryName', '')
            symbol_events = item.get('symbolEvents', 0)

            # Count total APP_Processes
            tech_stack['APP_Processes'] += symbol_events

            # Check if should classify as ArkUI
            is_arkui = ReportGenerator._should_classify_as_arkui(
                item.get('componentCategory', 0), component_name, sub_category_name
            )

            if is_arkui:
                tech_stack['ArkUI'] += symbol_events
            elif component_name not in excluded_components:
                # For non-ArkUI components, try to map to tech stack if possible
                tech_stack_name = ReportGenerator._map_category_to_tech_stack(component_name)
                if tech_stack_name:
                    tech_stack[tech_stack_name] += symbol_events
                # Note: Most components will fall into APP_Processes total, specific tech stack mapping may need updates

        return tech_stack

    @staticmethod
    def _get_component_reuse_for_step(component_reuse_data: dict, step_idx: int) -> dict | None:
        """Get component reuse statistics for a specific step.

        The structure is aligned with front-end ComponentResuStepData:
        {
            "total_builds": int,
            "recycled_builds": int,
            "reusability_ratio": float,
            "max_component": str
        }
        """
        if not isinstance(component_reuse_data, dict):
            return None

        step_key = f'step{step_idx}'
        step_data = component_reuse_data.get(step_key)
        if not isinstance(step_data, dict):
            return None

        # 字段可能缺失，这里统一做容错处理
        return {
            'total_builds': int(step_data.get('total_builds', 0)),
            'recycled_builds': int(step_data.get('recycled_builds', 0)),
            'reusability_ratio': float(step_data.get('reusability_ratio', 0.0)),
            'max_component': step_data.get('max_component') or '',
        }

    @staticmethod
    def _get_fault_tree_for_step(fault_tree_data: dict, step_idx: int) -> dict | None:
        """Get fault tree data for a specific step.

        We keep the raw fault tree node for this step so that the web
        can interpret and render detailed fault information.
        """
        if not isinstance(fault_tree_data, dict):
            return None

        step_key = f'step{step_idx}'
        step_data = fault_tree_data.get(step_key)
        if not isinstance(step_data, dict):
            return None

        return step_data

    @staticmethod
    def _get_ui_summary_for_step(ui_animate_data: dict, step_idx: int) -> tuple[dict | None, dict | None]:
        """Get UI-related summary (image oversize & component tree stats) for a specific step.

        The ui_animate.json structure is compatible with UIAnimateData on the web side.
        We aggregate per-page statistics into step-level summaries:

        image_oversize:
          {
            "total_images": int,
            "exceed_count": int,
            "total_excess_memory_mb": float
          }

        component_tree:
          {
            "total_nodes": int,
            "on_tree_nodes": int,
            "off_tree_nodes": int,
            "off_tree_ratio": float
          }
        """
        if not isinstance(ui_animate_data, dict):
            return None, None

        step_key = f'step{step_idx}'
        step_data = ui_animate_data.get(step_key)
        if not step_data:
            return None, None

        # 兼容两种格式：直接数组或包含 pages 字段的对象
        pages = None
        if isinstance(step_data, dict):
            pages = step_data.get('pages')
        if pages is None:
            # 可能是直接的页面数组
            pages = step_data

        if not isinstance(pages, list) or len(pages) == 0:
            return None, None

        total_images = 0
        exceed_count = 0
        total_excess_memory_mb = 0.0

        total_nodes = 0
        on_tree_nodes = 0
        off_tree_nodes = 0

        for page in pages:
            if not isinstance(page, dict):
                continue

            # Image 超尺寸统计
            image_analysis = page.get('image_size_analysis') or {}
            if isinstance(image_analysis, dict):
                total_images += int(image_analysis.get('total_images', 0))

                images_exceeding = image_analysis.get('images_exceeding_framerect') or []
                if isinstance(images_exceeding, list):
                    exceed_count += len(images_exceeding)

                total_excess_memory_mb += float(image_analysis.get('total_excess_memory_mb', 0.0))

            # 组件树上/未上树统计（使用 canvas 节点计数）
            canvas_node_cnt = page.get('canvasNodeCnt')
            if isinstance(canvas_node_cnt, (int, float)):
                total_nodes += int(canvas_node_cnt)

            on_tree = page.get('canvas_node_on_tree')
            if isinstance(on_tree, (int, float)):
                on_tree_nodes += int(on_tree)

            off_tree = page.get('canvas_node_off_tree')
            if isinstance(off_tree, (int, float)):
                off_tree_nodes += int(off_tree)

        image_oversize_summary = None
        if total_images > 0 or exceed_count > 0 or total_excess_memory_mb > 0:
            image_oversize_summary = {
                'total_images': total_images,
                'exceed_count': exceed_count,
                'total_excess_memory_mb': total_excess_memory_mb,
            }

        component_tree_summary = None
        if total_nodes > 0 or on_tree_nodes > 0 or off_tree_nodes > 0:
            off_tree_ratio = float(off_tree_nodes) / float(total_nodes) if total_nodes > 0 else 0.0
            component_tree_summary = {
                'total_nodes': total_nodes,
                'on_tree_nodes': on_tree_nodes,
                'off_tree_nodes': off_tree_nodes,
                'off_tree_ratio': off_tree_ratio,
            }

        return image_oversize_summary, component_tree_summary

    @staticmethod
    def _should_classify_as_arkui(component_category: int, component_name: str, sub_category_name: str) -> bool:
        """Check if should classify as ArkUI

        Args:
            component_category: Component category number
            component_name: Component name (previously category_name)
            sub_category_name: Sub category name

        Returns:
            True if should classify as ArkUI
        """
        # kind=3: ArkTS related components (Ability, ArkTS Runtime, ArkTS System LIB)
        if component_category == 3 and component_name in ['Ability', 'ArkTS Runtime', 'ArkTS System LIB']:
            return True

        # Check component name for ArkUI classification
        return bool('ArkTS' in component_name or 'ArkUI' in component_name)

    @staticmethod
    def _map_category_to_tech_stack(category_name: str) -> Optional[str]:
        """Map category name to tech stack name

        Args:
            category_name: Category name

        Returns:
            Tech stack name or None
        """
        category_to_tech_stack = {
            'Web': 'Web',
            'RN': 'RN',
            'ReactNative': 'RN',
            'Flutter': 'Flutter',
            'KMP': 'KMP',
            'KotlinMultiplatform': 'KMP',
        }

        # Try direct match
        if category_name in category_to_tech_stack:
            return category_to_tech_stack[category_name]

        # Try case-insensitive match
        for key, value in category_to_tech_stack.items():
            if category_name.lower() == key.lower():
                return value

        return None

    @staticmethod
    def _run_hilog_analysis(hilog_dir: str, report_dir: str) -> dict:
        """Run hilog analysis and return results

        Args:
            hilog_dir: Directory containing hilog files
            report_dir: Report directory to save analysis results

        Returns:
            Dictionary with hilog analysis results by step
        """
        try:
            # Run hilog analysis (detail=True 以生成 hilog_detail.json，供前端展示详细匹配信息)
            hilog_action = HilogAction()
            output_file = os.path.join(report_dir, 'hilog_analysis.xlsx')
            hilog_action.run(hilog_dir, output_file, detail=True)

            # Load hilog analysis results from JSON file
            hilog_json_path = os.path.join(report_dir, 'hilog_analysis.json')
            hilog_data = ReportGenerator._load_json_safe(hilog_json_path, default={})

            # Load hilog_detail.json（规则匹配详情：各规则 matched、其他 未匹配任何规则）
            hilog_detail_path = os.path.join(report_dir, 'hilog_detail.json')
            if os.path.exists(hilog_detail_path):
                hilog_detail = ReportGenerator._load_json_safe(hilog_detail_path, default={})
                hilog_data['_detail'] = hilog_detail

            return hilog_data

        except Exception as e:
            logging.warning('Hilog analysis failed: %s', str(e))
            return {}

    @staticmethod
    def _get_hilog_for_step(hilog_data: dict, step_idx: int) -> dict:
        """Get hilog analysis results for a specific step

        Args:
            hilog_data: Hilog analysis data dictionary
            step_idx: Step index

        Returns:
            Dictionary with hilog pattern statistics
        """
        # Try step-specific key first
        step_key = f'step{step_idx}'
        step_hilog = hilog_data.get(step_key, {})

        # If no step-specific data, try to get from root level
        # (hilog analysis might not be step-specific)
        if not step_hilog and hilog_data:
            # Return all hilog data if no step-specific data
            # Format: pattern_name -> count
            return hilog_data

        # Return the hilog statistics (pattern name -> count)
        return step_hilog


def merge_summary_info(directory: str) -> list[dict[str, Any]]:
    """合并指定目录下所有summary_info.json文件中的数据"""
    merged_data = []

    for root, _, files in os.walk(directory):
        for file in files:
            if file == 'summary_info.json':
                file_path = os.path.join(root, file)

                try:
                    with open(file_path, encoding='utf-8') as f:
                        data = json.load(f)

                        if isinstance(data, dict):
                            merged_data.append(data)
                        elif isinstance(data, list):
                            for item in data:
                                if isinstance(item, dict):
                                    merged_data.append(item)
                                else:
                                    logging.warning('警告: 文件 %s 包含非字典项，已跳过', file_path)
                        else:
                            logging.warning('警告: 文件 %s 格式不符合预期，已跳过', file_path)
                except Exception as e:
                    logging.error('错误: 无法读取文件 %s: %s', file_path, str(e))

    return merged_data


def process_to_dataframe(data: list[dict[str, Any]]) -> pd.DataFrame:
    """将合并后的数据转换为DataFrame并处理为透视表"""
    if not data:
        logging.warning('警告: 没有数据可处理')
        return pd.DataFrame()

    # 转换为DataFrame
    df = pd.DataFrame(data)

    # 组合rom_version和app_version作为列名
    df['version'] = df['rom_version'] + '+' + df['app_version']

    # 使用apply逐行处理step_id
    df['scene_name'] = df['scene'] + '步骤' + df['step_id'].astype(str) + ': ' + df['step_name']

    # 创建透视表，行=scene_name，列=version，值=count
    return df.pivot_table(
        index='scene_name',
        columns='version',
        values='count',
        aggfunc='sum',  # 如果有重复值，使用求和聚合
        fill_value=0,
    )


def add_percentage_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    添加百分比列，将第一列作为基线与后续每列进行比较

    Args:
        df: 原始透视表DataFrame

    Returns:
        添加了百分比列的DataFrame
    """
    if df.empty or len(df.columns) < 2:
        logging.warning('警告: 数据不足，无法计算百分比')
        return df

    # 获取基线列（第一列）
    baseline_col = df.columns[0]

    # 为除基线列外的每一列计算百分比
    for col in df.columns[1:]:
        # 计算百分比 (新值-基线值)/基线值*100%
        percentage_col = f'{col}_百分比'
        df[percentage_col] = (df[col] - df[baseline_col]) / df[baseline_col]

        # 将百分比列放在对应数据列之后
        df = df[[c for c in df.columns if c != percentage_col] + [percentage_col]]

    return df


def create_perf_summary_excel(input_path: str) -> bool:
    try:
        if not os.path.isdir(input_path):
            logging.error('错误: 目录 %s 不存在', input_path)
            return False

        # 合并JSON数据
        merged_data = merge_summary_info(input_path)

        if not merged_data:
            # summary_info.json不存在时不影响报告生成，只记录警告
            logging.warning('警告: 没有找到任何summary_info.json文件或文件内容为空，跳过Excel汇总报告生成')
            return True

        # 转为DataFrame
        df = pd.DataFrame(merged_data)
        if df.empty:
            logging.error('错误: 合并后的数据为空')
            return False

        # 保留所有rom_version的数据
        rom_versions = df['rom_version'].unique()
        if len(rom_versions) > 1:
            logging.info('检测到多个ROM版本: %s', ', '.join(rom_versions))

        # 重新组织列结构，将rom_version、app_version、count作为列名
        result_df = df[['rom_version', 'app_version', 'scene', 'step_id', 'step_name', 'count', 'app_count']].copy()

        # 按场景、步骤ID、步骤名称排序
        result_df = result_df.sort_values(['scene', 'step_id', 'step_name', 'app_version'])

        # 输出路径
        output_path = Path(input_path) / 'summary_pivot.xlsx'
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # 保存到Excel
        report_saver = ExcelReportSaver(str(output_path))
        report_saver.add_sheet(result_df, 'Summary')
        report_saver.save()

        return True
    except Exception as e:
        logging.error('未知错误：没有生成汇总excel %s', str(e))
        return False
