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
import zlib
from pathlib import Path
from typing import Any

import pandas as pd

from hapray import VERSION
from hapray.analyze import analyze_data
from hapray.core.common.excel_utils import ExcelReportSaver
from hapray.core.common.exe_utils import ExeUtils
from hapray.core.config.config import Config


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
                'perf': {'steps': []},  # 默认空步骤
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
        data.load_perf_data(perf_data_path)
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

    def __init__(self, use_refined_lib_symbol: bool = False, export_comparison: bool = False):
        """Initialize ReportGenerator

        Args:
            use_refined_lib_symbol: Enable refined mode for memory analysis
            export_comparison: Export comparison Excel for memory analysis
        """
        self.report_template_path = os.path.abspath(ExeUtils.get_tools_dir('web', 'report_template.html'))
        self.use_refined_lib_symbol = use_refined_lib_symbol
        self.export_comparison = export_comparison

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

        # Step 3: Generate HTML report
        self._create_html_report(scene_dir, result)

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
            logging.error('错误: 没有找到任何summary_info.json文件或文件内容为空')
            return False

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
