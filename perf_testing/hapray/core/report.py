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
import json
import logging
import os
import zlib
from pathlib import Path
from typing import List, Dict, Any

import pandas as pd

from hapray.analyze import analyze_data
from hapray.core.common.common_utils import CommonUtils
from hapray.core.common.excel_utils import ExcelReportSaver
from hapray.core.common.exe_utils import ExeUtils
from hapray.core.common.frame_analyzer import FrameAnalyzer


class ReportData:
    """封装报告生成所需的所有数据"""

    def __init__(self):
        self.perf_data = []
        self.frame_data = {}
        self.empty_frame_data = {}
        self.component_reusability_data = {}
        self.basic_info = {}

    @classmethod
    def from_paths(cls, scene_dir):
        """从文件路径加载数据"""
        perf_data_path = os.path.join(scene_dir, 'hiperf', 'hiperf_info.json')
        frame_data_path = os.path.join(scene_dir, 'htrace', 'frame_analysis_summary.json')
        empty_frames_analysis_path = os.path.join(scene_dir, 'htrace', 'empty_frames_analysis.json')
        component_reusability_report_path = os.path.join(scene_dir, 'htrace', 'component_reusability_report.json')

        data = cls()
        data.load_perf_data(perf_data_path)
        data.load_frame_data(frame_data_path)
        data.load_empty_frame_data(empty_frames_analysis_path)
        data.load_component_reusability_data(component_reusability_report_path)
        data.extract_basic_info()
        return data

    def load_perf_data(self, path):
        self.perf_data = self._load_json_safe(path, default=[])
        if len(self.perf_data) == 0 :
            raise FileNotFoundError(f"hiperf_info.json not found: {path}")

    def load_frame_data(self, path):
        self.frame_data = self._load_json_safe(path, default={})

    def load_empty_frame_data(self, path):
        self.empty_frame_data = self._load_json_safe(path, default={})

    def load_component_reusability_data(self, path):
        self.component_reusability_data = self._load_json_safe(path, default={})

    def extract_basic_info(self):
        if self.perf_data and isinstance(self.perf_data, list):
            first_entry = self.perf_data[0]
            self.basic_info = {
                "rom_version": first_entry.get("rom_version", ""),
                "app_id": first_entry.get("app_id", ""),
                "app_name": first_entry.get("app_name", ""),
                "app_version": first_entry.get("app_version", ""),
                "scene": first_entry.get("scene", ""),
                "timestamp": first_entry.get("timestamp", 0)
            }

    def _load_json_safe(self, path, default):
        """安全加载JSON文件，处理异常情况"""
        if not os.path.exists(path):
            logging.info(f"File not found: {path}")
            return default

        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # 验证数据类型
            if isinstance(default, list) and not isinstance(data, list):
                logging.warning(f"Invalid format in {path}, expected list but got {type(data).__name__}")
                return default
            elif isinstance(default, dict) and not isinstance(data, dict):
                logging.warning(f"Invalid format in {path}, expected dict but got {type(data).__name__}")
                return default

            return data
        except json.JSONDecodeError as e:
            logging.error(f"JSON decoding error in {path}: {str(e)}")
            return default
        except Exception as e:
            logging.error(f"Error loading {path}: {str(e)}")
            return default


class ReportGenerator:
    """Generates and updates performance analysis reports"""

    def __init__(self):
        self.perf_testing_dir = CommonUtils.get_project_root()

    def update_report(self, scene_dir: str) -> bool:
        """Update an existing performance report"""
        return self._generate_report(
            scene_dirs=[scene_dir],
            scene_dir=scene_dir,
            skip_round_selection=True
        )

    def generate_report(
            self,
            scene_dirs: List[str],
            scene_dir: str
    ) -> bool:
        """Generate a new performance analysis report"""
        return self._generate_report(
            scene_dirs,
            scene_dir,
            skip_round_selection=False
        )

    def _generate_report(
            self,
            scene_dirs: List[str],
            scene_dir: str,
            skip_round_selection: bool
    ) -> bool:
        """Core method for report generation and updating"""
        # Step 1: Select round (only for new reports)
        if not skip_round_selection:
            if not self._select_round(scene_dirs, scene_dir):
                logging.error("Round selection failed, aborting report generation")
                return False
        # Step 2: Analyze data
        analyze_data(scene_dir)

        # Step 3: Analyze empty frames
        self._analyze_empty_frames(scene_dir)

        # Step 4: Analyze frame drops
        self._analyze_frame_drops(scene_dir)

        # Step 5: Generate HTML report
        self._create_html_report(scene_dir)

        logging.info(f"Report successfully {'updated' if skip_round_selection else 'generated'} for {scene_dir}")
        return True

    def _select_round(self, scene_dirs: List[str], scene_dir: str) -> bool:
        """Select the best round for report generation"""
        if not scene_dirs:
            logging.error("No scene directories provided for round selection")
            return False

        args = ['dbtools',
                '--choose',
                '-i', scene_dir
                ]

        logging.debug(f"Selecting round with command: {' '.join(args)}")
        return ExeUtils.execute_hapray_cmd(args)

    def _analyze_frame_drops(self, scene_dir: str) -> None:
        """Analyze frame drops and log results"""
        logging.info(f"Starting frame drops analysis for {scene_dir}")

        try:
            if FrameAnalyzer.analyze_frame_drops(scene_dir):
                logging.info(f"Successfully analyzed frame drops for {scene_dir}")
            else:
                logging.warning(f"Frame drop analysis completed with warnings for {scene_dir}")
        except Exception as e:
            logging.error(f"Frame drop analysis failed for {scene_dir}: {str(e)}")

    def _analyze_empty_frames(self, scene_dir: str) -> None:
        """分析空帧数据"""
        try:
            # 获取所有步骤的进程信息
            app_pids = self._get_app_pids(scene_dir)
            if not app_pids:
                logging.warning(f"No app PIDs found for scene {scene_dir}")
                return

            # 用于存储所有步骤的分析结果
            all_results = {}

            # 遍历所有步骤目录
            for step_dir in os.listdir(os.path.join(scene_dir, 'htrace')):
                step_path = os.path.join(scene_dir, 'htrace', step_dir)
                if not os.path.isdir(step_path):
                    continue

                # 从step_dir中提取步骤编号（例如从'step1'提取'1'）
                current_step_id = int(step_dir.replace('step', ''))

                # 过滤出当前步骤的进程信息
                current_step_pids = [(name, pid) for step_id, name, pid in app_pids if int(step_id) == current_step_id]

                if not current_step_pids:
                    logging.warning(f"No process info found for step {step_dir}")
                    continue

                # 提取PID列表
                pids = [pid for _, pid in current_step_pids]

                # 记录当前步骤的进程信息
                for name, pid in current_step_pids:
                    logging.info(f"Step {step_dir} - Process: {name} (PID: {pid})")

                # 获取trace和perf数据库路径
                trace_db = os.path.join(step_path, 'trace.db')
                perf_db = os.path.join(scene_dir, 'hiperf', step_dir, 'perf.db')

                if not os.path.exists(trace_db) or not os.path.exists(perf_db):
                    logging.warning(f"Missing database files for step {step_dir}")
                    continue

                # 执行空帧分析
                result = FrameAnalyzer.analyze_empty_frames(trace_db, perf_db, pids)
                if result["status"] == "success":
                    logging.info(f"Successfully analyzed empty frames for step {step_dir}")
                    all_results[step_dir] = result
                else:
                    logging.warning(
                        f"Empty frame analysis failed for step {step_dir}: {result.get('message', 'Unknown error')}")

            # 保存所有步骤的分析结果到htrace子目录
            if all_results:
                output_json = os.path.join(scene_dir, 'htrace', 'empty_frames_analysis.json')
                with open(output_json, 'w', encoding='utf-8') as f:
                    json.dump(all_results, f, ensure_ascii=False, indent=2)
                logging.info(f"All empty frames analysis results saved to {output_json}")
            else:
                logging.warning("No valid analysis results to save")

        except Exception as e:
            logging.error(f"Empty frame analysis failed for {scene_dir}: {str(e)}")

    def _create_html_report(self, scene_dir: str) -> None:
        """Create the final HTML report"""
        try:
            json_data_str = self._get_json_data(scene_dir)

            template_path = os.path.join(
                self.perf_testing_dir, 'hapray-toolbox', 'res', 'report_template.html'
            )
            output_path = os.path.join(scene_dir, 'report', 'hapray_report.html')

            # Create directory structure if needed
            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            # Inject performance data
            self._inject_json_to_html(
                json_data_str=json_data_str,
                placeholder='JSON_DATA_PLACEHOLDER',
                html_path=template_path,
                output_path=output_path
            )

            logging.info(f"HTML report created at {output_path}")
        except Exception as e:
            logging.error(f"Failed to create HTML report: {str(e)}")

    def _get_json_data(
            self,
            scene_dir: str,
    ) -> str:
        """加载并处理所有报告数据"""
        report_data = ReportData.from_paths(
            scene_dir
        )

        return self._build_merged_data(1, report_data)

    def _build_merged_data(self, data_type: int, report_data: 'ReportData') -> str:
        """
        构建并处理合并后的报告数据

        根据指定类型处理数据：
        - 0: 返回原始JSON字符串
        - 1: 返回Base64编码的gzip压缩JSON
        - 2: 返回原始JSON字符串（与类型0相同）
        """
        # 构建基础数据结构
        merged_data = {
            "type": data_type,
            "versionCode": 1,
            "basicInfo": report_data.basic_info or {},
            "perf": {"steps": []}  # 默认空步骤
        }

        # 处理性能数据
        if isinstance(report_data.perf_data, list) and len(report_data.perf_data) > 0:
            first_entry = report_data.perf_data[0]
            merged_data["perf"]["steps"] = first_entry.get("steps", [])

        # 处理跟踪数据（可选）
        if report_data.frame_data:
            trace_data = {
                "componentReuse": report_data.component_reusability_data
            }

            # 添加帧分析数据
            frames = report_data.frame_data
            if frames is not {}:
                trace_data["frames"] = frames

            # 添加空帧分析数据（可选）
            if report_data.empty_frame_data is not {}:
                trace_data["emptyFrame"] = report_data.empty_frame_data

            merged_data["trace"] = trace_data

        # 根据类型处理输出格式
        try:
            if data_type == 1:
                # 路径1: Base64编码的gzip压缩JSON
                json_bytes = json.dumps(merged_data).encode('utf-8')
                compressed_bytes = zlib.compress(json_bytes, level=9)
                base64_bytes = base64.b64encode(compressed_bytes)
                return base64_bytes.decode('ascii')
            else:
                # 路径2: 原始JSON字符串（类型0和2）
                return json.dumps(merged_data)
        except Exception as e:
            logging.error(f"Failed to process merged data: {str(e)}")
            return "未知"

    @staticmethod
    def _inject_json_to_html(
            json_data_str: str,
            placeholder: str,
            html_path: str,
            output_path: str
    ) -> None:
        """Inject JSON data into an HTML template"""
        # Validate path
        if not os.path.exists(html_path):
            raise FileNotFoundError(f"HTML template not found: {html_path}")

        # Load HTML template
        with open(html_path, 'r', encoding='utf-8') as f:
            html_content = f.read()

        # Inject JSON into HTML
        updated_html = html_content.replace(placeholder, json_data_str)

        # Save the updated HTML
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(updated_html)

        logging.debug(f"Injected {json_data_str} into {output_path}")

    def _get_app_pids(self, scene_dir: str) -> list:
        """获取应用进程ID列表
        
        从hiperf_info.json文件中读取进程信息，格式为：
        [
            {
                "steps": [
                    {
                        "step_id": "step1",
                        "data": [
                            {
                                "processName": "com.example.app",
                                "pid": 1234
                            },
                            ...
                        ]
                    },
                    ...
                ]
            }
        ]
        
        Returns:
            list: 进程ID列表
        """
        try:
            # 获取hiperf_info.json文件路径
            perf_data_path = os.path.join(scene_dir, 'hiperf', 'hiperf_info.json')

            if not os.path.exists(perf_data_path):
                logging.warning(f"No hiperf_info.json found at {perf_data_path}")
                return []

            # 读取JSON文件
            with open(perf_data_path, 'r', encoding='utf-8') as f:
                perf_data = json.load(f)

            if not perf_data or not isinstance(perf_data, list) or len(perf_data) == 0:
                logging.warning("Invalid hiperf_info.json format")
                return []

            # 获取第一个item的steps
            steps = perf_data[0].get('steps', [])
            if not steps:
                logging.warning("No steps found in hiperf_info.json")
                return []

            # 收集所有进程信息
            process_info = set()  # 使用set去重
            for step in steps:
                step_id = step.get('step_id')
                if not step_id:
                    continue

                # 遍历data数组
                for item in step.get('data', []):
                    process_name = item.get('processName')
                    pid = item.get('pid')
                    if process_name and pid:
                        process_info.add((step_id, process_name, pid))

            # 转换为列表并返回
            return list(process_info)

        except Exception as e:
            logging.error(f"Failed to get app PIDs: {str(e)}")
            return []


def merge_summary_info(directory: str) -> List[Dict[str, Any]]:
    """合并指定目录下所有summary_info.json文件中的数据"""
    merged_data = []

    for root, dirs, files in os.walk(directory):
        for file in files:
            if file == "summary_info.json":
                file_path = os.path.join(root, file)

                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)

                        if isinstance(data, dict):
                            merged_data.append(data)
                        elif isinstance(data, list):
                            for item in data:
                                if isinstance(item, dict):
                                    merged_data.append(item)
                                else:
                                    logging.warning(f"警告: 文件 {file_path} 包含非字典项，已跳过")
                        else:
                            logging.warning(f"警告: 文件 {file_path} 格式不符合预期，已跳过")
                except Exception as e:
                    logging.error(f"错误: 无法读取文件 {file_path}: {str(e)}")

    return merged_data


def process_to_dataframe(data: List[Dict[str, Any]]) -> pd.DataFrame:
    """将合并后的数据转换为DataFrame并处理为透视表"""
    if not data:
        logging.warning("警告: 没有数据可处理")
        return pd.DataFrame()

    # 转换为DataFrame
    df = pd.DataFrame(data)

    # 组合rom_version和app_version作为列名
    df['version'] = df['rom_version'] + '+' + df['app_version']

    # 使用apply逐行处理step_id
    df['scene_name'] = df['scene'] + '步骤' + df['step_id'].astype(str) + ': ' + df['step_name']

    # 创建透视表，行=scene_name，列=version，值=count
    pivot_table = df.pivot_table(
        index='scene_name',
        columns='version',
        values='count',
        aggfunc='sum',  # 如果有重复值，使用求和聚合
        fill_value=0,
    )

    return pivot_table


def add_percentage_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    添加百分比列，将第一列作为基线与后续每列进行比较

    Args:
        df: 原始透视表DataFrame

    Returns:
        添加了百分比列的DataFrame
    """
    if df.empty or len(df.columns) < 2:
        logging.warning("警告: 数据不足，无法计算百分比")
        return df

    # 获取基线列（第一列）
    baseline_col = df.columns[0]

    # 为除基线列外的每一列计算百分比
    for col in df.columns[1:]:
        # 计算百分比 (新值-基线值)/基线值*100%
        percentage_col = f"{col}_百分比"
        df[percentage_col] = ((df[col] - df[baseline_col]) / df[baseline_col])

        # 将百分比列放在对应数据列之后
        df = df[[c for c in df.columns if c != percentage_col] + [percentage_col]]

    return df


def create_perf_summary_excel(input_path: str) -> bool:
    try:
        if not os.path.isdir(input_path):
            logging.error(f"错误: 目录 {input_path} 不存在")
            return False

        # 合并JSON数据
        merged_data = merge_summary_info(input_path)

        if not merged_data:
            logging.error("错误: 没有找到任何summary_info.json文件或文件内容为空")
            return False

        # 处理为透视表
        pivot_df = process_to_dataframe(merged_data)

        # 确保有足够的列来计算百分比
        if len(pivot_df.columns) > 1:
            # 添加百分比列（以第一列为基线）
            pivot_df = add_percentage_columns(pivot_df)
            logging.info(f"已计算相对于 {pivot_df.columns[0]} 的百分比增长")
        else:
            logging.warning("警告: 数据列不足，无法计算百分比增长")

        # 确定输出路径
        output_path = Path(input_path) / 'summary_pivot.xlsx'

        # 确保输出目录存在
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # 保存到Excel
        report_saver = ExcelReportSaver(str(output_path))
        report_saver.add_sheet(pivot_df, 'Summary')
        report_saver.save()

        return True
    except  Exception as e:
        logging.error("未知错误：没有生成汇总excel" + str(e))
        return False
