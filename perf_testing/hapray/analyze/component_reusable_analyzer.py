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

"""
Analyzer for component reusability metrics.
"""

import sqlite3
from typing import Dict, Any

from hapray.analyze.base_analyzer import BaseAnalyzer


class ComponentReusableAnalyzer(BaseAnalyzer):
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

                # Get total component builds
                cursor.execute("SELECT COUNT(*) AS count FROM callstack WHERE name LIKE '%H:CustomNode:Build%'")
                total_row = cursor.fetchone()
                metrics["total_builds"] = total_row["count"] if total_row else 0

                # Get recycled component builds
                cursor.execute("SELECT COUNT(*) AS count FROM callstack WHERE name LIKE '%H:CustomNode:BuildRecycle%'")
                recycled_row = cursor.fetchone()
                metrics["recycled_builds"] = recycled_row["count"] if recycled_row else 0

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
