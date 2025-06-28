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
import os.path
import re
import sqlite3
from typing import Dict, Any, Optional

from hapray.analyze.base_analyzer import BaseAnalyzer


class ComponentReusableAnalyzer(BaseAnalyzer):
    """
    Analyzer for component reusability metrics.
    """

    pattern = re.compile(r'^H:CustomNode:BuildItem\s*\[([^\]]*)\]')

    def __init__(self, scene_dir: str):
        super().__init__(scene_dir, 'component_reusability_report.json')

    def _analyze_impl(self, step_dir: str, trace_db_path: str, perf_db_path: str) -> Optional[Dict[str, Any]]:
        """Analyze component reusability metrics.

        Metrics:
        - Total component builds
        - Recycled component builds
        - Reusability ratio

        Args:
            step_dir: Identifier for the current step
            trace_db_path: Path to trace database
            perf_db_path: Path to performance database (unused in this analyzer)

        Returns:
            Dictionary containing reusability metrics
        """
        metrics = {
            "max_component": '',
            "total_builds": 0,
            "recycled_builds": 0,
            "reusability_ratio": 0.0
        }

        if not os.path.exists(trace_db_path):
            return None

        try:
            with sqlite3.connect(trace_db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                result = dict({})
                # Get total component builds
                cursor.execute("SELECT name FROM callstack WHERE name LIKE '%H:CustomNode:Build%'")
                for row in cursor.fetchall():
                    # H:CustomNode:BuildItem [ItemView][self:86][parent:-1]
                    # H:CustomNode:BuildRecycle ItemView
                    component = self._extract_component_name(row["name"])
                    if component not in result:
                        result[component] = [0, 0]
                    result[component][0] = result[component][0] + 1
                    if row["name"].startswith('H:CustomNode:BuildRecycle'):
                        result[component][1] = result[component][1] + 1

                # choose max component as build result
                max_component = [0, 0, '']
                for key, value in result.items():
                    if value[0] > max_component[0]:
                        max_component[0] = value[0]
                        max_component[1] = value[1]
                        max_component[2] = key

                metrics["total_builds"] = max_component[0]
                metrics["recycled_builds"] = max_component[1]
                metrics["max_component"] = max_component[2]
                metrics["details"] = result

                # Calculate reusability ratio
                if metrics["total_builds"] > 0:
                    metrics["reusability_ratio"] = round(
                        metrics["recycled_builds"] / metrics["total_builds"],
                        2
                    )
        except sqlite3.Error as e:
            self.logger.error("Database error: %s", str(e))
            return {"error": f"Database operation failed: {str(e)}"}

        return metrics

    def _extract_component_name(self, name) -> str:
        match = self.pattern.search(name)
        if match:
            return match.group(1)
        if name.startswith('H:CustomNode:BuildRecycle'):
            return name.split(' ')[1]
        return 'Unknown'
