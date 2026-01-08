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

import argparse
import json
import logging
import os
import platform
import re
import subprocess
from pathlib import Path
from typing import Optional

import pandas as pd

from hapray.core.common.excel_utils import ExcelReportSaver
from hapray.core.common.exe_utils import ExeUtils
from hapray.core.config.config import Config


class ExpressionEvaluator:
    """表达式评估器，支持分组值的数学运算和比较"""

    @staticmethod
    def evaluate_expression(expression: str, extracted_values: list) -> bool:
        """
        评估表达式，支持分组值引用和数学运算

        表达式语法：
        - $1, $2, $3... 表示第1、2、3...个分组值（从1开始）
        - 支持数学运算：+, -, *, /, %
        - 支持比较运算符：==, !=, <, >, <=, >=
        - 支持括号：()
        - 支持多个表达式（AND逻辑）：用逗号或 && 分隔，所有表达式都满足才返回True

        示例：
        - "$1 * $2 > $3 * $4"  # 分组1和2的乘积大于分组3和4的乘积
        - "($1 + $2) == ($3 + $4)"  # 分组1和2的和等于分组3和4的和
        - "$1 > 100"  # 分组1大于100
        - "$1*$2>0,$3*$4>512"  # 多个条件：分组1*2>0 且 分组3*4>512
        - "$1>10 && $2<100"  # 使用 && 连接多个条件
        """
        if not expression or not expression.strip():
            return True

        try:
            expr = expression.strip()

            # 检查是否包含多个表达式（用逗号或 && 分隔）
            # 先检查 &&，因为可能包含在比较运算符中（如 >=）
            if ' && ' in expr or expr.count('&&') > 0:
                # 使用 && 分隔（注意处理 >= 和 <= 中的 &）
                # 简单处理：只分割独立的 &&（前后有空格或括号）
                parts = re.split(r'\s+&&\s+', expr)
                if len(parts) > 1:
                    # 多个表达式，所有都满足才返回True
                    for part in parts:
                        if not ExpressionEvaluator._evaluate_single_expression(part.strip(), extracted_values):
                            return False
                    return True

            # 检查逗号分隔（注意：逗号可能在括号内，需要处理）
            if ',' in expr:
                # 分割表达式，但需要考虑括号内的逗号
                # 简单方法：按逗号分割，但检查每个部分是否包含未匹配的括号
                parts = []
                current_part = ''
                paren_count = 0
                for char in expr:
                    if char == '(':
                        paren_count += 1
                        current_part += char
                    elif char == ')':
                        paren_count -= 1
                        current_part += char
                    elif char == ',' and paren_count == 0:
                        # 括号外部的逗号，分割点
                        if current_part.strip():
                            parts.append(current_part.strip())
                        current_part = ''
                    else:
                        current_part += char
                # 添加最后一部分
                if current_part.strip():
                    parts.append(current_part.strip())

                if len(parts) > 1:
                    # 多个表达式，所有都满足才返回True
                    for part in parts:
                        if not ExpressionEvaluator._evaluate_single_expression(part, extracted_values):
                            return False
                    return True

            # 单个表达式
            return ExpressionEvaluator._evaluate_single_expression(expr, extracted_values)

        except Exception as e:
            logging.warning(f'Error evaluating expression "{expression}": {str(e)}')
            return False

    @staticmethod
    def _evaluate_single_expression(expression: str, extracted_values: list) -> bool:
        """
        评估单个表达式
        """
        if not expression or not expression.strip():
            return True

        try:
            expr = expression.strip()

            # 替换分组引用 $1, $2, $3... 为实际值
            # 使用正则表达式匹配 $数字
            def replace_group_ref(match):
                group_num = int(match.group(1))
                # 分组索引从1开始，转换为列表索引（从0开始）
                idx = group_num - 1
                if 0 <= idx < len(extracted_values):
                    value = extracted_values[idx]
                    if value is None:
                        logging.warning(f'Group reference ${group_num} is None')
                        return '0'  # None 值转换为 0，避免表达式错误
                    # 尝试转换为数字（表达式通常用于数值计算）
                    try:
                        # 先尝试整数，再尝试浮点数
                        if isinstance(value, (int, float)):
                            return str(float(value))
                        # 尝试字符串转数字
                        num_value = float(str(value).strip())
                        return str(num_value)
                    except (ValueError, TypeError):
                        # 如果不能转换为数字，记录警告并返回 0
                        logging.warning(
                            f'Group reference ${group_num} value "{value}" cannot be converted to number. '
                            f'Using 0 in expression.'
                        )
                        return '0'
                else:
                    logging.warning(
                        f'Group reference ${group_num} is out of range '
                        f'(available groups: 1-{len(extracted_values)}). Using 0 in expression.'
                    )
                    return '0'

            # 替换所有 $数字 引用
            expr = re.sub(r'\$(\d+)', replace_group_ref, expr)

            # 安全评估表达式
            # 只允许数字、运算符、括号和比较运算符
            # 检查表达式是否只包含安全的字符
            safe_chars = r'[\d\.\+\-\*\/\%\(\)\s<>=!]'
            if not re.match(
                r'^' + safe_chars + r'+$', expr.replace('==', '').replace('!=', '').replace('<=', '').replace('>=', '')
            ):
                logging.warning(f'Expression contains unsafe characters: {expression}')
                return False

            # 使用 eval 计算表达式（表达式来自配置文件，相对安全）
            # 限制可用的内置函数和变量
            safe_dict = {
                '__builtins__': {},
                'abs': abs,
                'min': min,
                'max': max,
                'round': round,
            }

            result = eval(expr, safe_dict)

            # 结果应该是布尔值
            if isinstance(result, bool):
                return result
            if isinstance(result, (int, float)):
                # 如果结果是数字，非零为True
                return bool(result)
            logging.warning(f'Expression result is not boolean: {result}')
            return False

        except Exception as e:
            logging.warning(f'Error evaluating expression "{expression}": {str(e)}')
            return False


class ConditionEvaluator:
    """条件表达式评估器"""

    @staticmethod
    def evaluate_condition(value: str, condition: str) -> bool:
        """
        评估条件表达式
        支持的运算符：==, !=, <, >, <=, >=
        对于数值比较，如果值能转换为数字则进行数值比较，否则进行字符串比较
        """
        if not condition:
            return True

        try:
            # 尝试转换为数字进行比较
            try:
                num_value = float(value)
                is_numeric = True
            except (ValueError, TypeError):
                is_numeric = False

            # 解析条件表达式
            if condition.startswith('=='):
                expected = condition[2:].strip()
                if is_numeric:
                    try:
                        return num_value == float(expected)
                    except (ValueError, TypeError):
                        return False
                else:
                    return value == expected
            elif condition.startswith('!='):
                expected = condition[2:].strip()
                if is_numeric:
                    try:
                        return num_value != float(expected)
                    except (ValueError, TypeError):
                        return True
                else:
                    return value != expected
            elif condition.startswith('>='):
                expected_str = condition[2:].strip()
                if is_numeric:
                    try:
                        return num_value >= float(expected_str)
                    except (ValueError, TypeError):
                        return False
                else:
                    return value >= expected_str
            elif condition.startswith('<='):
                expected_str = condition[2:].strip()
                if is_numeric:
                    try:
                        return num_value <= float(expected_str)
                    except (ValueError, TypeError):
                        return False
                else:
                    return value <= expected_str
            elif condition.startswith('>'):
                expected_str = condition[1:].strip()
                if is_numeric:
                    try:
                        return num_value > float(expected_str)
                    except (ValueError, TypeError):
                        return False
                else:
                    return value > expected_str
            elif condition.startswith('<'):
                expected_str = condition[1:].strip()
                if is_numeric:
                    try:
                        return num_value < float(expected_str)
                    except (ValueError, TypeError):
                        return False
                else:
                    return value < expected_str
            else:
                # 不支持的条件，默认为真
                logging.warning(f'Unsupported condition: {condition}, treating as true')
                return True
        except Exception as e:
            logging.warning(f'Error evaluating condition "{condition}" for value "{value}": {str(e)}')
            return True


class HilogAction:
    """Handles hilog analysis and statistics generation"""

    @staticmethod
    def execute(args) -> Optional[str]:
        """Execute hilog analysis workflow"""
        parser = argparse.ArgumentParser(
            description='Analyze hilog files and generate statistics', prog='ArkAnalyzer-HapRay hilog'
        )

        parser.add_argument(
            '-d', '--hilog-dir', required=True, help='Directory containing hilog files or single hilog file path'
        )

        parser.add_argument(
            '-o',
            '--output',
            default='hilog_analysis.xlsx',
            help='Output Excel file path (default: hilog_analysis.xlsx)',
        )

        parser.add_argument(
            '--detail',
            action='store_true',
            default=False,
            help='Enable detailed logging: save matched strings to hilog_detail.json',
        )

        parsed_args = parser.parse_args(args)
        action = HilogAction()
        return action.run(parsed_args.hilog_dir, parsed_args.output, parsed_args.detail)

    def run(self, hilog_dir: str, output_file: str, detail: bool = False) -> Optional[str]:
        """Run hilog analysis"""
        try:
            # Validate input
            if not os.path.exists(hilog_dir):
                logging.error(f'Hilog directory/file not found: {hilog_dir}')
                return None

            # Execute hilogtool to decrypt logs
            if not self._execute_hilogtool(hilog_dir):
                logging.error('Failed to execute hilogtool')
                return None

            # Get hilog patterns from config
            config = Config()
            if hasattr(config.data, 'hilog') and hasattr(config.data.hilog, 'patterns'):
                patterns = config.data.hilog.patterns
            else:
                logging.error('No hilog patterns found in config')
                return None

            # Analyze decrypted logs
            results, detail_data = self._analyze_hilog_files(hilog_dir, patterns, detail)

            # Generate Excel report
            scene_name = Path(hilog_dir).name
            self._generate_excel_report(scene_name, results, output_file)

            # Generate detail JSON file if detail mode is enabled
            if detail and detail_data:
                output_path = Path(output_file)
                detail_json_path = output_path.parent / 'hilog_detail.json'
                self._save_detail_json(detail_data, detail_json_path)
                logging.info(f'Detail data saved to: {detail_json_path}')

            logging.info(f'Hilog analysis completed. Results saved to: {output_file}')
            return output_file

        except Exception as e:
            logging.error(f'Hilog analysis failed: {str(e)}')
            return None

    def _execute_hilogtool(self, hilog_dir: str) -> bool:
        """Execute hilogtool to decrypt hilog files"""
        try:
            # Get hilogtool directory using the standard method
            tools_dir = ExeUtils.get_tools_dir('hilogtool')

            # Select appropriate executable based on platform
            if platform.system() == 'Windows':
                hilogtool_path = os.path.join(tools_dir, 'hilogtool.exe')
            else:
                hilogtool_path = os.path.join(tools_dir, 'hilogtool')

            if not os.path.exists(hilogtool_path):
                logging.error(f'Hilogtool not found at: {hilogtool_path}')
                return False

            # Prepare command
            hilog_dir_path = Path(hilog_dir)
            cmd = [str(hilogtool_path), 'parse', '-i', str(hilog_dir_path), '-d', str(hilog_dir_path)]

            logging.info(f'Executing hilogtool: {" ".join(cmd)}')

            # Execute command
            result = subprocess.run(cmd, check=False, capture_output=True, text=True, cwd=str(hilog_dir_path.parent))

            # Print hilogtool output
            if result.stdout:
                logging.info(f'Hilogtool output:\n{result.stdout}')

            if result.stderr:
                logging.warning(f'Hilogtool stderr: {result.stderr}')

            # Check execution result
            if result.returncode != 0:
                logging.error(f'Hilogtool execution failed with return code: {result.returncode}')
                return False

            return True

        except Exception as e:
            logging.error(f'Error executing hilogtool: {str(e)}')
            return False

    def _analyze_hilog_files(
        self, hilog_dir: str, patterns: list, detail: bool = False
    ) -> tuple[dict[str, list], dict]:
        """Analyze decrypted hilog files and extract pattern matches with groups"""
        results = {}
        detail_data = {} if detail else None

        try:
            hilog_path = Path(hilog_dir)

            # Find all decrypted hilog txt files recursively
            hilog_files = [hilog_path] if hilog_path.is_file() else list(hilog_path.rglob('hilog*.txt'))

            logging.info(f'Found {len(hilog_files)} hilog files to analyze')

            # Initialize pattern results
            pattern_configs = {}
            for pattern in patterns:
                # All patterns should be dict format from config
                pattern_name = pattern.get('name', str(pattern))
                regex_pattern = pattern.get('regex', str(pattern))
                groups = pattern.get('groups', [0])
                conditions = pattern.get('conditions', [])

                # 兼容旧的 expression 配置（已废弃，建议使用 conditions）
                if 'expression' in pattern:
                    expression = pattern.get('expression')
                    if conditions:
                        logging.warning(
                            f'Pattern "{pattern_name}": Both "expression" and "conditions" are specified. '
                            f'Using "expression" and ignoring "conditions". '
                            f'Note: "expression" is deprecated, please use "conditions" instead.'
                        )
                        conditions = []
                    else:
                        # 将 expression 转换为 conditions 字符串格式
                        conditions = expression
                        logging.warning(
                            f'Pattern "{pattern_name}": "expression" is deprecated, please use "conditions" instead.'
                        )

                pattern_configs[pattern_name] = {'regex': regex_pattern, 'groups': groups, 'conditions': conditions}
                results[pattern_name] = []
                if detail:
                    detail_data[pattern_name] = {'matched': [], 'unmatched': []}

            for file_path in hilog_files:
                if not file_path.exists():
                    continue

                try:
                    with open(file_path, encoding='utf-8', errors='ignore') as f:
                        content = f.read()

                    # Extract matches for each pattern
                    for pattern_name, config in pattern_configs.items():
                        regex_pattern = config['regex']
                        groups = config['groups']
                        conditions = config['conditions']

                        try:
                            # Compile regex and find matches
                            regex = re.compile(regex_pattern, re.IGNORECASE | re.MULTILINE)

                            if detail:
                                # Use finditer to get full match strings
                                matches_with_strings = []
                                for match_obj in regex.finditer(content):
                                    full_match_string = match_obj.group(0)  # Full matched string
                                    match_tuple = match_obj.groups() if match_obj.groups() else full_match_string
                                    matches_with_strings.append((match_tuple, full_match_string))
                                matches = [m[0] for m in matches_with_strings]
                            else:
                                matches = regex.findall(content)
                                matches_with_strings = None

                            # Extract specified groups from matches and apply conditions
                            for idx, match in enumerate(matches):
                                # Get full match string for detail mode
                                full_match_string = (
                                    matches_with_strings[idx][1] if (detail and matches_with_strings) else None
                                )

                                if isinstance(match, tuple):
                                    # Multiple groups captured
                                    extracted_values = []
                                    for group_idx in groups:
                                        if group_idx == 0:
                                            extracted_values.append(match)  # Full match (tuple)
                                        elif 1 <= group_idx <= len(match):
                                            extracted_values.append(match[group_idx - 1])  # Group index starts from 1
                                        else:
                                            extracted_values.append(None)  # Invalid group index
                                # Single group or no groups
                                elif 0 in groups:
                                    extracted_values = [match]  # Full match
                                elif groups == [1]:
                                    extracted_values = [match]  # Single captured group
                                else:
                                    extracted_values = []

                                # Apply conditions filtering
                                conditions_met = True
                                if extracted_values and conditions:
                                    # 如果 conditions 是字符串且包含 $，使用表达式评估器
                                    if isinstance(conditions, str) and '$' in conditions:
                                        # 使用表达式评估（支持分组值的数学运算和比较）
                                        conditions_met = ExpressionEvaluator.evaluate_expression(
                                            conditions, extracted_values
                                        )
                                    elif isinstance(conditions, list):
                                        # 使用传统的条件数组方式（向后兼容）
                                        # Check if all conditions are satisfied (AND logic)
                                        for i, (value, condition) in enumerate(zip(extracted_values, conditions)):
                                            if i < len(conditions) and condition:
                                                value_str = str(value) if value is not None else ''
                                                if not ConditionEvaluator.evaluate_condition(value_str, condition):
                                                    conditions_met = False
                                                    break
                                    else:
                                        logging.warning(
                                            f'Pattern "{pattern_name}": Invalid conditions type: {type(conditions)}'
                                        )
                                        conditions_met = False

                                # Handle detail mode: save matched strings
                                if detail and full_match_string:
                                    if conditions_met:
                                        detail_data[pattern_name]['matched'].append(full_match_string)
                                    else:
                                        detail_data[pattern_name]['unmatched'].append(full_match_string)

                                # Only add to results if conditions are met (or no conditions)
                                if conditions_met and extracted_values:
                                    results[pattern_name].append(extracted_values)

                        except re.error as e:
                            logging.warning(f'Invalid regex pattern "{regex_pattern}": {str(e)}')
                            continue

                except Exception as e:
                    logging.warning(f'Error analyzing file {file_path}: {str(e)}')
                    continue

            return results, detail_data

        except Exception as e:
            logging.error(f'Error analyzing hilog files: {str(e)}')
            return {}, {} if detail else {}

    def _generate_excel_report(self, scene_name: str, results: dict[str, list], output_file: str):
        """Generate Excel report from analysis results"""
        try:
            # Create summary sheet with counts
            saver = ExcelReportSaver(output_file)

            # Prepare summary data
            summary_data = {'场景名称': [scene_name]}
            for pattern_name, matches in results.items():
                summary_data[pattern_name] = [len(matches)]

            summary_df = pd.DataFrame(summary_data)
            saver.add_sheet(summary_df, '汇总统计')

            # Create detailed sheets for patterns with matches
            for pattern_name, matches in results.items():
                if not matches:
                    continue

                # Prepare detailed data for DataFrame
                data_rows = []
                for i, match in enumerate(matches):
                    row = {'场景名称': scene_name, '序号': i + 1}
                    if isinstance(match, list):
                        for j, value in enumerate(match):
                            row[f'分组{j + 1}'] = str(value) if value is not None else ''
                    else:
                        row['匹配内容'] = str(match)
                    data_rows.append(row)

                df = pd.DataFrame(data_rows)
                saver.add_sheet(df, pattern_name[:31])  # Excel sheet name limit

            saver.save()

        except ImportError:
            logging.error('pandas or xlsxwriter not installed. Please install required packages.')
        except Exception as e:
            logging.error(f'Error generating Excel report: {str(e)}')

    def _save_detail_json(self, detail_data: dict, output_path: Path):
        """Save detailed match data to JSON file"""
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(detail_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logging.error(f'Error saving detail JSON file: {str(e)}')
