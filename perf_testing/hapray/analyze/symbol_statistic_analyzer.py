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
import re
import sqlite3
from typing import Any, Optional

import pandas as pd

from hapray.analyze.base_analyzer import BaseAnalyzer


class SymbolStatisticAnalyzer(BaseAnalyzer):
    """
    Analyzer for symbol statistics based on external configuration.
    """

    def __init__(self, scene_dir: str, symbol_file: str, time_ranges: list[dict] = None):
        super().__init__(scene_dir, 'symbol_statistic')
        self.symbol_patterns = self._load_patterns(symbol_file)
        self.statistics = []  # List to hold statistic dicts
        self.time_ranges = time_ranges or []
        self.logger = logging.getLogger(self.__class__.__name__)

    def _load_patterns(self, symbol_file: str) -> list[str]:
        """Load symbol patterns from file."""
        if not os.path.exists(symbol_file):
            raise FileNotFoundError(f'Symbol file not found: {symbol_file}')
        with open(symbol_file, encoding='utf-8') as f:
            patterns = [line.strip() for line in f if line.strip()]
        self.logger.info(f'Loaded {len(patterns)} symbol patterns')
        return patterns

    def _convert_pattern_to_regex(self, pattern: str) -> str:
        """Convert pattern to regex, supporting both wildcard and regex patterns.

        Supports:
        - Wildcard patterns: * (matches any sequence), ? (matches single char)
        - Regex patterns: If pattern contains regex special chars (^, $, [, ], etc.),
          treat as regex pattern
        - Fuzzy matching: By default, patterns match anywhere in the string (contains match)

        Args:
            pattern: Pattern string that may contain wildcards or regex

        Returns:
            Regex pattern string for matching
        """
        if not pattern:
            return '.*'

        # Check if pattern looks like a regex (contains regex special chars)
        # Common regex special chars: ^ $ [ ] { } ( ) | + \
        # But we allow * and ? as wildcards unless they're part of a regex pattern
        regex_special_chars = r'^$\[\]{}\(\)\|\\'
        has_regex_chars = any(char in pattern for char in regex_special_chars)
        has_wildcards = '*' in pattern or '?' in pattern

        # If pattern has regex chars and no wildcards, treat as regex (use as-is)
        if has_regex_chars and not has_wildcards:
            return pattern

        # Convert wildcard pattern to regex
        # Escape regex special characters first (this will escape * and ? too)
        regex_pattern = re.escape(pattern)
        # Replace escaped wildcards with regex equivalents
        regex_pattern = regex_pattern.replace(r'\*', '.*')  # * -> .*
        return regex_pattern.replace(r'\?', '.')  # ? -> .

        # Note: By default, regex supports fuzzy matching (contains match)
        # No need to add ^ and $ anchors unless explicitly specified

    def _analyze_impl(
        self, step_dir: str, trace_db_path: str, perf_db_path: str, app_pids: list
    ) -> Optional[dict[str, Any]]:
        """Analyze symbols in perf database for the step."""
        if not os.path.exists(trace_db_path):
            self.logger.warning(f'Perf DB not found for step {step_dir}')
            return None

        try:
            with sqlite3.connect(trace_db_path) as conn:

                def regexp(expr, item):
                    if item is None:
                        return False
                    try:
                        return re.search(expr, item) is not None
                    except Exception:
                        return False

                conn.create_function('REGEXP', 2, regexp)
                cursor = conn.cursor()

                total_matches = 0
                for pattern in self.symbol_patterns:
                    # Convert pattern to regex (supports wildcards and regex patterns)
                    regex_pattern = self._convert_pattern_to_regex(pattern)

                    query = """
                    SELECT
                        pf.symbol AS symbol,
                        proc.thread_name AS process_name,
                        t.process_id AS process_id,
                        t.thread_name AS thread_name,
                        t.thread_id AS thread_id,
                        pf.path AS file,
                        SUM(sa.event_count) AS load
                    FROM perf_files pf
                    JOIN perf_callchain c ON pf.serial_id = c.symbol_id AND pf.file_id = c.file_id
                    JOIN perf_sample sa ON c.callchain_id = sa.callchain_id
                    JOIN perf_thread t ON sa.thread_id = t.thread_id
                    LEFT JOIN perf_thread proc ON t.process_id = proc.thread_id AND proc.thread_id = proc.process_id
                    JOIN perf_report r ON sa.event_type_id = r.id
                    WHERE pf.symbol IS NOT NULL
                    AND pf.symbol REGEXP ?
                    AND r.report_value IN ('instructions', 'raw-instruction-retired', 'hw-instructions')
                    """
                    params = [regex_pattern]
                    if self.time_ranges:
                        for tr in self.time_ranges:
                            query += ' AND sa.timestamp_trace BETWEEN ? AND ?'
                            params.extend([tr['startTime'], tr['endTime']])
                    query += ' GROUP BY pf.symbol, t.process_id, t.thread_id, pf.path'
                    cursor.execute(query, params)
                    rows = cursor.fetchall()
                    total_matches += len(rows)

                    for row in rows:
                        self.statistics.append(
                            {
                                'step': step_dir,
                                'symbol': row[0],
                                'process': f'{row[1] or "unknown"} ({row[2]})',
                                'thread': f'{row[3]} ({row[4]})',
                                'file': row[5],
                                'load': row[6],
                            }
                        )

            self.logger.info(f'Analyzed {total_matches} symbols for step {step_dir}')
            return {'analyzed': True, 'matches': total_matches}

        except sqlite3.Error as e:
            self.logger.error(f'Database error in step {step_dir}: {str(e)}')
            return {'error': str(e)}
        except Exception as e:
            self.logger.error(f'Unexpected error in step {step_dir}: {str(e)}')
            return {'error': str(e)}

    def generate_excel(self, output_path: str):
        """Generate Excel report from collected statistics."""
        if not self.statistics:
            self.logger.warning('No statistics to generate Excel')
            return

        df = pd.DataFrame(self.statistics)
        df.to_excel(output_path, index=False, sheet_name='Symbol Statistics')
        self.logger.info(f'Excel report generated at {output_path}')
