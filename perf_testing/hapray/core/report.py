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
import json
import logging
import os
import zlib
from pathlib import Path
from typing import Any

import pandas as pd

from hapray import VERSION
from hapray.analyze import analyze_data
from hapray.core.common.common_utils import CommonUtils
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
    def from_paths(cls, scene_dir: str, result: dict, load_memory: bool = True):
        """从文件路径加载数据

        Args:
            scene_dir: 场景目录路径
            result: 分析结果字典
            load_memory: 是否加载内存数据（默认True，支持仅负载分析模式）
        """
        perf_data_path = os.path.join(scene_dir, 'hiperf', 'hiperf_info.json')
        data = cls(scene_dir, result)
        data.load_perf_data(perf_data_path)
        data.load_trace_data(scene_dir)
        if load_memory:
            data.load_native_memory_data(scene_dir)
        return data

    def __str__(self):
        # 路径1: Base64编码的gzip压缩JSON
        # 清理数据中的NaN值以确保JSON序列化安全
        cleaned_result = self._clean_data_for_json(self.result)

        # 特殊处理火焰图数据：按步骤单独压缩
        cleaned_result = self._compress_flame_graph_by_steps(cleaned_result)

        # 特殊处理内存数据：按步骤单独压缩
        cleaned_result = self._compress_native_memory_by_steps(cleaned_result)

        # 特殊处理UI动画数据：按步骤单独压缩
        cleaned_result = self._compress_ui_animate_by_steps(cleaned_result)

        # 删除重复的 memory_analysis 字段（已经被压缩到 native_memory 中）
        if 'more' in cleaned_result and 'memory_analysis' in cleaned_result['more']:
            del cleaned_result['more']['memory_analysis']
            logging.info('Removed duplicate memory_analysis field (data is in native_memory)')

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

    def _compress_native_memory_by_steps(self, data):
        """按步骤压缩内存数据，避免字符串过长

        参考火焰图的压缩逻辑，对每个步骤的内存记录进行压缩
        """
        if not isinstance(data, dict):
            return data

        # 检查是否有内存数据
        if 'more' not in data or 'native_memory' not in data['more']:
            return data

        native_memory_data = data['more']['native_memory']
        if not isinstance(native_memory_data, dict):
            return data

        # 按步骤压缩内存数据
        compressed_native_memory = {}

        for step_key, step_data in native_memory_data.items():
            if isinstance(step_data, dict) and 'records' in step_data:
                try:
                    records = step_data['records']
                    records_count = len(records)

                    # 将记录数组转换为 JSON 字符串
                    records_json = json.dumps(records)
                    original_size = len(records_json)

                    # 检查数据大小，如果超过 500MB，使用分块压缩
                    # JavaScript 字符串最大长度约 512MB，我们使用 500MB 作为阈值
                    MAX_CHUNK_SIZE = 500 * 1024 * 1024  # 500MB

                    if original_size > MAX_CHUNK_SIZE:
                        # 分块压缩
                        logging.info(
                            '内存数据过大 %s: %d 字节 (%d 条记录)，使用分块压缩',
                            step_key,
                            original_size,
                            records_count,
                        )

                        # 计算每块的记录数（确保每块 JSON 大小不超过 MAX_CHUNK_SIZE）
                        avg_record_size = original_size / records_count if records_count > 0 else 1
                        chunk_record_count = max(1, int(MAX_CHUNK_SIZE / avg_record_size))

                        # 分块压缩
                        compressed_chunks = []
                        total_compressed_size = 0

                        for i in range(0, records_count, chunk_record_count):
                            chunk = records[i : i + chunk_record_count]
                            chunk_json = json.dumps(chunk)
                            chunk_size = len(chunk_json)

                            # 压缩块
                            compressed_bytes = zlib.compress(chunk_json.encode('utf-8'), level=9)
                            base64_bytes = base64.b64encode(compressed_bytes)
                            compressed_chunk = base64_bytes.decode('ascii')

                            compressed_chunks.append(compressed_chunk)
                            total_compressed_size += len(compressed_chunk)

                            logging.info(
                                '  分块 %d/%d: %d 条记录, %d -> %d 字节',
                                len(compressed_chunks),
                                (records_count + chunk_record_count - 1) // chunk_record_count,
                                len(chunk),
                                chunk_size,
                                len(compressed_chunk),
                            )

                        # 保留统计信息和其他字段，使用分块压缩数据
                        compressed_step_data = {
                            'stats': step_data.get('stats', {}),
                            'peak_time': step_data.get('peak_time'),  # 峰值时间点
                            'peak_value': step_data.get('peak_value'),  # 峰值内存值
                            'records': compressed_chunks,  # 压缩后的记录块数组
                            'callchains': step_data.get('callchains'),  # 调用链数据
                            'compressed': True,  # 标记为已压缩
                            'chunked': True,  # 标记为分块压缩
                            'chunk_count': len(compressed_chunks),  # 块数量
                            'total_records': records_count,  # 总记录数
                        }
                        compressed_native_memory[step_key] = compressed_step_data

                        # 记录压缩效果
                        compression_ratio = (1 - total_compressed_size / original_size) * 100
                        logging.info(
                            '内存数据分块压缩完成 %s: %d -> %d 字节 (压缩率: %.1f%%), %d 个块',
                            step_key,
                            original_size,
                            total_compressed_size,
                            compression_ratio,
                            len(compressed_chunks),
                        )
                    else:
                        # 单块压缩（原有逻辑）
                        compressed_bytes = zlib.compress(records_json.encode('utf-8'), level=9)
                        base64_bytes = base64.b64encode(compressed_bytes)
                        compressed_records = base64_bytes.decode('ascii')

                        # 保留统计信息和其他字段，压缩记录数据
                        compressed_step_data = {
                            'stats': step_data.get('stats', {}),
                            'peak_time': step_data.get('peak_time'),  # 峰值时间点
                            'peak_value': step_data.get('peak_value'),  # 峰值内存值
                            'records': compressed_records,  # 压缩后的记录
                            'callchains': step_data.get('callchains'),  # 调用链数据
                            'compressed': True,  # 标记为已压缩
                        }
                        compressed_native_memory[step_key] = compressed_step_data

                        # 记录压缩效果
                        compressed_size = len(compressed_records)
                        compression_ratio = (1 - compressed_size / original_size) * 100
                        logging.info(
                            '内存数据压缩 %s: %d -> %d 字节 (压缩率: %.1f%%)',
                            step_key,
                            original_size,
                            compressed_size,
                            compression_ratio,
                        )
                except Exception as e:
                    logging.warning('压缩内存数据失败 %s: %s', step_key, str(e))
                    # 压缩失败时保持原数据
                    compressed_native_memory[step_key] = step_data
            else:
                # 非预期格式的数据保持不变
                compressed_native_memory[step_key] = step_data

        # 更新数据结构
        data['more']['native_memory'] = compressed_native_memory
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

    def load_native_memory_data(self, scene_dir: str):
        """加载Native Memory数据（类似trace_frames.json的格式）"""
        report_dir = os.path.join(scene_dir, 'report')

        # 确保 more 字段存在
        if 'more' not in self.result:
            self.result['more'] = {}

        # 加载more_memory_analysis.json 文件
        new_memory_path = os.path.join(report_dir, 'more_memory_analysis.json')
        native_memory_data = self._load_json_safe(new_memory_path, default={})

        if native_memory_data:
            self.result['more']['native_memory'] = native_memory_data
            logging.info(f'Loaded Native Memory data: {len(native_memory_data)} steps')

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

        # 加载火焰图数据和Native Memory数据
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

    def __init__(self):
        self.perf_testing_dir = CommonUtils.get_project_root()

    def update_report(self, scene_dir: str, time_ranges: list[dict] = None) -> bool:
        """Update an existing performance report

        Args:
            scene_dir: Directory containing the scene data
            time_ranges: Optional list of time range filters
        """
        return self._generate_report(
            scene_dirs=[scene_dir], scene_dir=scene_dir, skip_round_selection=True, time_ranges=time_ranges
        )

    def generate_report(self, scene_dirs: list[str], scene_dir: str, time_ranges: list[dict] = None) -> bool:
        """Generate a new performance analysis report"""
        return self._generate_report(scene_dirs, scene_dir, skip_round_selection=False, time_ranges=time_ranges)

    def _generate_report(
        self, scene_dirs: list[str], scene_dir: str, skip_round_selection: bool, time_ranges: list[dict] = None
    ) -> bool:
        """Core method for report generation and updating"""
        # Step 1: Select round (only for new reports)
        if not skip_round_selection and not self._select_round(scene_dirs, scene_dir):
            logging.error('Round selection failed, aborting report generation')
            return False

        # Step 2: Analyze data (includes empty frames and frame drops analysis)
        result = analyze_data(scene_dir, time_ranges)

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

            template_path = os.path.join(self.perf_testing_dir, 'sa-cmd', 'res', 'report_template.html')
            output_path = os.path.join(scene_dir, 'report', 'hapray_report.html')

            # Create directory structure if needed
            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            # Inject performance data
            self._inject_json_to_html(
                json_data_str=json_data_str,
                placeholder='JSON_DATA_PLACEHOLDER',
                html_path=template_path,
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

        # 根据分析模式决定是否加载内存数据
        load_memory = analysis_mode in ['all', 'memory']

        # 根据分析模式决定是否加载性能数据
        load_perf = analysis_mode in ['all', 'perf']

        # 创建 ReportData 实例
        report_data = ReportData.from_paths(scene_dir, result, load_memory=load_memory)

        # 如果是仅内存分析模式，不加载性能数据
        if not load_perf:
            report_data.perf_data = []
            report_data.result['perf']['steps'] = []

        return str(report_data)

    @staticmethod
    def _inject_json_to_html(json_data_str: str, placeholder: str, html_path: str, output_path: str) -> None:
        """Inject JSON data into an HTML template"""
        # Validate path
        if not os.path.exists(html_path):
            raise FileNotFoundError(f'HTML template not found: {html_path}')

        # Load HTML template
        with open(html_path, encoding='utf-8') as f:
            html_content = f.read()

        # Inject JSON into HTML
        updated_html = html_content.replace(placeholder, json_data_str)

        # Save the updated HTML
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(updated_html)

        logging.debug('Injected %s into %s', json_data_str, output_path)


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
