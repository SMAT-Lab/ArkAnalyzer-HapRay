import json
import logging
import os
import re
from typing import Dict, Any, List, Optional

from hapray.analyze.base_analyzer import BaseAnalyzer


class ColdStartAnalyzer(BaseAnalyzer):
    """Analyzer for cold start redundant file analysis"""

    def __init__(self, scene_dir: str):
        super().__init__(scene_dir, 'cold_start_analysis_summary.json')

    def _analyze_impl(self, step_dir: str, trace_db_path: str, perf_db_path: str) -> Optional[Dict[str, Any]]:
        """Analyze cold start redundant file for a single step.

        Args:
            step_dir: Identifier for the current step (not used for path building)
            trace_db_path: Path to trace database (not used in this analyzer)
            perf_db_path: Path to performance database (not used in this analyzer)

        Returns:
            Dictionary containing cold start analysis result for this step, or None if no data
        """
        # 从testInfo.json中提取bundle name
        bundle_name = self._extract_bundle_name()
        if not bundle_name:
            logging.warning("Could not extract bundle name from testInfo.json")
            return None

        # 构建redundant file路径 - 在scene_dir/result/目录下
        redundant_file_path = os.path.join(self.scene_dir, 'result', f'{bundle_name}_redundant_file.txt')

        if not os.path.exists(redundant_file_path):
            logging.warning("Redundant file not found: %s", redundant_file_path)
            return None

        try:
            logging.info("Analyzing cold start redundant file for %s...", step_dir)
            result = self._parse_redundant_file(redundant_file_path)

            if result is None:
                logging.info("No cold start data found for step %s", step_dir)
                return None

            return result

        except Exception as e:
            logging.error("Cold start analysis failed: %s", str(e))
            return None

    def _extract_bundle_name(self) -> Optional[str]:
        """Extract bundle name from testInfo.json file.

        Returns:
            Bundle name (app_id) or None if extraction fails
        """
        try:
            test_info_path = os.path.join(self.scene_dir, 'testInfo.json')
            if not os.path.exists(test_info_path):
                logging.warning("testInfo.json not found: %s", test_info_path)
                return None

            with open(test_info_path, 'r', encoding='utf-8') as f:
                test_info = json.load(f)

            app_id = test_info.get('app_id')
            if app_id:
                return app_id

            logging.warning("app_id not found in testInfo.json")
            return None

        except Exception as e:
            logging.error("Failed to extract bundle name from testInfo.json: %s", str(e))
            return None

    def _parse_redundant_file(self, file_path: str) -> Optional[Dict[str, Any]]:
        """Parse the redundant file and extract summary and top 10 data.

        Args:
            file_path: Path to the redundant file

        Returns:
            Dictionary containing parsed data, or None if parsing fails
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            result = {}

            # 解析Summary信息
            summary_match = re.search(
                r'<----Summary---->\s*'
                r'Total file number:\s*(\d+),'
                r'\s*total time:\s*(\d+)ms,'
                r'\s*including used file:(\d+),'
                r'\s*cost time:\s*(\d+)ms,'
                r'\s*and unused file:\s*(\d+),'
                r'\s*cost time:\s*(\d+)ms',
                content)

            if summary_match:
                result['summary'] = {
                    'total_file_number': int(summary_match.group(1)),
                    'total_time_ms': int(summary_match.group(2)),
                    'used_file_count': int(summary_match.group(3)),
                    'used_file_time_ms': int(summary_match.group(4)),
                    'unused_file_count': int(summary_match.group(5)),
                    'unused_file_time_ms': int(summary_match.group(6))
                }

            # 解析used file前10
            used_files = self._extract_file_list(content, 'used file', 10)
            result['used_files_top10'] = used_files

            # 解析unused file前10
            unused_files = self._extract_file_list(content, 'unused file', 10)
            result['unused_files_top10'] = unused_files

            return result

        except Exception as e:
            logging.error("Failed to parse redundant file: %s", str(e))
            return None

    def _extract_file_list(self, content: str, file_type: str, top_n: int) -> List[Dict[str, Any]]:
        """Extract top N files of specified type.

        Args:
            content: File content
            file_type: 'used file' or 'unused file'
            top_n: Number of top files to extract

        Returns:
            List of dictionaries containing file information
        """
        files = []

        # 构建正则表达式模式
        if file_type == 'used file':
            pattern = r'used file (\d+):\s*([^,]+),\s*cost time:\s*([\d.]+)ms'
        else:  # unused file
            pattern = r'unused file (\d+):\s*([^,]+),\s*cost time:\s*([\d.]+)ms'

        matches = re.findall(pattern, content)

        for i, match in enumerate(matches[:top_n]):
            file_info = {
                'rank': int(match[0]),
                'file_name': match[1].strip(),
                'cost_time_ms': float(match[2])
            }

            # 尝试提取parent module信息
            parent_pattern = r'parentModule (\d+):\s*([^&]+)'
            parent_matches = re.findall(parent_pattern, content)

            # 查找对应的parent module（这里简化处理，实际可能需要更复杂的逻辑）
            if i < len(parent_matches):
                file_info['parent_module'] = parent_matches[i][1].strip()

            files.append(file_info)

        return files
