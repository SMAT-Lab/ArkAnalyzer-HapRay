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
    Analyzer for trace event statistics.
    Collects trace event statistics and correlates with measure data.

    The analyzer:
    1. Matches patterns against callstack trace event names
    2. Groups by process, thread, and event name
    3. Calculates load from measure table values during event duration
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

    def _merge_time_ranges(self, time_ranges: list[tuple[int, int]]) -> list[tuple[int, int]]:
        """Merge overlapping time ranges.

        Args:
            time_ranges: List of (start_time, end_time) tuples

        Returns:
            List of merged (start_time, end_time) tuples
        """
        if not time_ranges:
            return []

        # Sort by start time
        sorted_ranges = sorted(time_ranges, key=lambda x: x[0])
        merged = [sorted_ranges[0]]

        for current_start, current_end in sorted_ranges[1:]:
            last_start, last_end = merged[-1]

            # If current range overlaps with last merged range
            if current_start <= last_end:
                # Merge by extending the end time
                merged[-1] = (last_start, max(last_end, current_end))
            else:
                # No overlap, add as new range
                merged.append((current_start, current_end))

        return merged

    def _analyze_impl(
        self, step_dir: str, trace_db_path: str, perf_db_path: str, app_pids: list
    ) -> Optional[dict[str, Any]]:
        """Analyze symbols in perf database for the step.

        Process:
        1. Query all time ranges (ts, dur) for symbols matching pattern from callstack
        2. Merge overlapping time ranges
        3. Query perf_sample for event_count values where timeStamp falls in merged ranges
        4. Aggregate by event name and thread
        """
        if not os.path.exists(trace_db_path):
            self.logger.warning(f'Trace DB not found for step {step_dir}')
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

                # Collect all matching events across all patterns (to avoid duplicates)
                all_event_time_ranges = {}

                for pattern in self.symbol_patterns:
                    # Convert pattern to regex (supports wildcards and regex patterns)
                    regex_pattern = self._convert_pattern_to_regex(pattern)

                    # Step 1: Query all time ranges from callstack for this pattern
                    query = """
                    SELECT DISTINCT
                        c.name AS event_name,
                        c.ts AS start_time,
                        c.ts + c.dur AS end_time,
                        c.callid
                    FROM callstack c
                    WHERE c.name IS NOT NULL
                    AND c.name REGEXP ?
                    """
                    params = [regex_pattern]

                    if self.time_ranges:
                        time_range_conditions = ' OR '.join(['(c.ts BETWEEN ? AND ?)'] * len(self.time_ranges))
                        query += f' AND ({time_range_conditions})'
                        for tr in self.time_ranges:
                            params.extend([tr['startTime'], tr['endTime']])

                    cursor.execute(query, params)
                    callstack_rows = cursor.fetchall()

                    if not callstack_rows:
                        continue

                    # Group by event_name (accumulate across patterns)
                    for row in callstack_rows:
                        event_name = row[0]
                        start_time = row[1]
                        end_time = row[2]

                        if event_name not in all_event_time_ranges:
                            all_event_time_ranges[event_name] = []
                        # Avoid duplicate time ranges for the same event
                        time_range_tuple = (start_time, end_time)
                        if time_range_tuple not in all_event_time_ranges[event_name]:
                            all_event_time_ranges[event_name].append(time_range_tuple)

                # Step 2 & 3: For each event, merge time ranges and query perf_sample
                total_matches = 0
                for event_name, time_ranges_list in all_event_time_ranges.items():
                    merged_ranges = self._merge_time_ranges(time_ranges_list)

                    self.logger.info(
                        f'Event "{event_name}": {len(time_ranges_list)} ranges merged to {len(merged_ranges)}'
                    )

                    # Query perf_sample for each merged range and aggregate by thread
                    thread_loads = {}

                    for start_time, end_time in merged_ranges:
                        perf_query = """
                        SELECT
                            ps.thread_id,
                            pt.thread_name,
                            pt.process_id,
                            SUM(ps.event_count) AS total_event_count
                        FROM perf_sample ps
                        LEFT JOIN perf_thread pt ON ps.thread_id = pt.thread_id
                        WHERE ps.timeStamp >= ? AND ps.timeStamp <= ?
                        GROUP BY ps.thread_id
                        """

                        cursor.execute(perf_query, [start_time, end_time])
                        perf_rows = cursor.fetchall()

                        # Accumulate event counts by thread
                        for perf_row in perf_rows:
                            thread_id = perf_row[0]
                            thread_name = perf_row[1] or 'unknown'
                            process_id = perf_row[2] or 0
                            event_count = perf_row[3] or 0

                            thread_key = (thread_id, thread_name, process_id)
                            if thread_key not in thread_loads:
                                thread_loads[thread_key] = 0
                            thread_loads[thread_key] += event_count

                    # Step 4: Add to statistics
                    for (thread_id, thread_name, _process_id), total_load in thread_loads.items():
                        self.statistics.append(
                            {
                                'step': step_dir,
                                'event_name': event_name,
                                'thread': f'{thread_name} ({thread_id})',
                                'load': total_load,
                            }
                        )
                        total_matches += 1

            self.logger.info(f'Analyzed {total_matches} symbol statistics for step {step_dir}')
            return {'analyzed': True, 'matches': total_matches}

        except sqlite3.Error as e:
            self.logger.error(f'Database error in step {step_dir}: {str(e)}')
            return {'error': str(e)}
        except Exception as e:
            self.logger.error(f'Unexpected error in step {step_dir}: {str(e)}')
            return {'error': str(e)}

    def generate_excel(self, output_path: str):
        """Generate Excel report from collected trace event statistics."""
        if not self.statistics:
            self.logger.warning('No statistics to generate Excel')
            return

        df = pd.DataFrame(self.statistics)
        df.to_excel(output_path, index=False, sheet_name='Trace Event Statistics')
        self.logger.info(f'Excel report generated at {output_path}')
