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
import re

"""
Analyzer for component reusability metrics.
"""

import sqlite3
from typing import Dict, Any

from hapray.analyze.base_analyzer import BaseAnalyzer


class ComponentReusableAnalyzer(BaseAnalyzer):
    pattern = re.compile(r'^H:CustomNode:BuildItem\s*\[([^\]]*)\]')

    def __init__(self, scene_dir: str):
        super().__init__(scene_dir, 'component_reusability_report.json')

    def _analyze_impl(self, trace_db_path: str, perf_db_path: str) -> Dict[str, Any]:
        """Analyze component reusability metrics.

        Metrics:
        - Total component builds
        - Recycled component builds
        - Reusability ratio

        Args:
            trace_db_path: Path to trace database
            perf_db_path: Path to performance database (unused in this analyzer)

        Returns:
            Dictionary containing reusability metrics
        """
        metrics = {
            "total_builds": 0,
            "recycled_builds": 0,
            "reusability_ratio": 0.0
        }

        try:
            with sqlite3.connect(trace_db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                result = dict()
                # Get total component builds
                cursor.execute("SELECT name FROM callstack WHERE name LIKE '%H:CustomNode:Build%'")
                for row in cursor.fetchall():
                    # H:CustomNode:BuildItem [ItemView][self:86][parent:-1]
                    # H:CustomNode:BuildRecycle ItemView
                    component = self._extract_component_name(row["name"])
                    if component not in result.keys():
                        result[component] = [0, 0]
                    result[component][0] = result[component][0] + 1
                    if row["name"].startswith('H:CustomNode:BuildRecycle'):
                        result[component][1] = result[component][1] + 1

                # choose max component as build result
                max_component = [0, 0]
                for value in result.values():
                    if value[0] > max_component[0]:
                        max_component[0] = value[0]
                        max_component[1] = value[1]

                metrics["total_builds"] = max_component[0]
                metrics["recycled_builds"] = max_component[1]

                # Calculate reusability ratio
                if metrics["total_builds"] > 0:
                    metrics["reusability_ratio"] = round(
                        metrics["recycled_builds"] / metrics["total_builds"],
                        2
                    )
        except sqlite3.Error as e:
            self.logger.error(f"Database error: {str(e)}")
            return {"error": f"Database operation failed: {str(e)}"}

        return metrics

    def _extract_component_name(self, name) -> str:
        match = self.pattern.search(name)
        if match:
            return match.group(1)
        if name.startswith('H:CustomNode:BuildRecycle'):
            return name.split(' ')[1]
        return 'Unknown'
