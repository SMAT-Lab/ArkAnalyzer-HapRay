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

import json
import os
from typing import Any, Optional

from hapray.analyze.base_analyzer import BaseAnalyzer
from hapray.core.config.config import Config


class ThermalAnalyzer(BaseAnalyzer):
    """温度数据分析器

    解析采集阶段生成的 thermal/step{N}/thermal_data.jsonl，
    输出各传感器的温度时序曲线与统计信息（起始/结束/最高/平均/温升）。
    """

    THERMAL_DATA_FILENAME = 'thermal_data.jsonl'

    def __init__(self, scene_dir: str):
        super().__init__(scene_dir, 'trace/thermal')

    def _analyze_impl(
        self, step_dir: str, trace_db_path: str, perf_db_path: str, app_pids: list
    ) -> Optional[dict[str, Any]]:
        thermal_file = os.path.join(self.scene_dir, 'thermal', step_dir, self.THERMAL_DATA_FILENAME)
        if not os.path.exists(thermal_file):
            self.logger.debug('Thermal data not found, skipping: %s', thermal_file)
            return None

        records = self._load_thermal_records(thermal_file)
        if not records:
            self.logger.warning('No valid thermal records in %s', thermal_file)
            return None

        return self._build_step_result(records)

    def _load_thermal_records(self, thermal_file: str) -> list[dict]:
        """加载并解析 jsonl 温度记录，过滤无效行"""
        records = []
        with open(thermal_file, encoding='utf-8') as f:
            for line_no, raw_line in enumerate(f, 1):
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    self.logger.warning('Invalid thermal record at %s:%d', thermal_file, line_no)
                    continue
                sensors = record.get('sensors')
                if isinstance(sensors, dict) and sensors:
                    records.append(record)
        return records

    def _build_step_result(self, records: list[dict]) -> dict[str, Any]:
        """汇总温度时序与统计信息"""
        elapsed_s = [round(float(r.get('elapsed_s', 0)), 1) for r in records]
        wall_time = [r.get('wall_time', '') for r in records]

        # 按传感器拆分时序（传感器集合可能随采样轮次变化，缺失轮次置 None）
        sensor_names: list[str] = []
        seen: set[str] = set()
        for record in records:
            for name in record['sensors']:
                if name not in seen:
                    seen.add(name)
                    sensor_names.append(name)

        sensor_series: dict[str, list[Optional[float]]] = {}
        statistics: dict[str, dict[str, float]] = {}
        for name in sensor_names:
            series: list[Optional[float]] = [r['sensors'].get(name) for r in records]
            sensor_series[name] = series
            values = [v for v in series if v is not None]
            if not values:
                continue
            start, end = values[0], values[-1]
            statistics[name] = {
                'start': start,
                'end': end,
                'max': max(values),
                'min': min(values),
                'avg': round(sum(values) / len(values), 2),
                'rise': round(end - start, 2),
            }

        # 采样间隔取中位数（实际间隔受采集耗时影响会略有抖动）
        intervals = [
            elapsed_s[i] - elapsed_s[i - 1] for i in range(1, len(elapsed_s)) if elapsed_s[i] >= elapsed_s[i - 1]
        ]
        interval = round(sorted(intervals)[len(intervals) // 2], 1) if intervals else Config.get(
            'thermal.interval_seconds', 5
        )

        return {
            'status': 'ok',
            'sample_count': len(records),
            'interval_seconds': interval,
            'duration_s': elapsed_s[-1] if elapsed_s else 0,
            'statistics': statistics,
            'series': {
                'elapsed_s': elapsed_s,
                'wall_time': wall_time,
                'sensors': sensor_series,
            },
        }
