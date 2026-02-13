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

冗余线程分析器（Redundant Thread Analysis）。
报告输出为 redundant_thread_analysis.json，结果合并到 result['redundant_thread_analysis']。
"""

from typing import Any, Optional

from hapray.analyze.base_analyzer import BaseAnalyzer
from hapray.analyze.thread_optimization import analyze_optimization_opportunities
from hapray.core.common.thread_wakeup_chain import analyze_all_threads_wakeup_chain

REDUNDANCY_TYPE_LABELS = {
    'normal': '未命中下述唤醒模式，多为高等待或混合行为。',
    'frequent_immediate_sleep': '被频繁唤醒但立即进入等待，典型无效调度。',
    'never_woken': '从未被唤醒，可能未被使用或孤立线程。',
    'busy_waiting': '短运行周期占比高或状态切换极频繁（跑一下就睡、跑一下就睡）。',
    'busy_wait': '高指令数但运行占比极低或含大量yield，属忙等浪费CPU。',
}


class ThreadAnalyzer(BaseAnalyzer):
    """Analyzer for redundant thread analysis (wakeup chain + optimization opportunities)."""

    def __init__(self, scene_dir: str, report_path: str = 'redundant_thread_analysis', **kwargs):
        super().__init__(scene_dir, report_path)

    def _analyze_impl(
        self, step_dir: str, trace_db_path: str, perf_db_path: str, app_pids: list
    ) -> Optional[dict[str, Any]]:
        if not app_pids:
            return {'error': 'no app pids'}

        results = analyze_all_threads_wakeup_chain(
            trace_db_path=trace_db_path,
            perf_db_path=perf_db_path or trace_db_path,
            app_pids=app_pids,
            time_range=None,
        )
        if not results:
            return {'redundant_threads_summary': {'total_redundant_thread_patterns': 0, 'total_redundant_threads': 0, 'redundant_threads': []}}

        try:
            analysis = analyze_optimization_opportunities(results, '', verbose=False)
        except Exception as e:
            self.logger.warning('Optimization analysis failed: %s', e)
            return {
                'redundant_threads_summary': {
                    'total_redundant_thread_patterns': 0,
                    'total_redundant_threads': 0,
                    'redundant_threads': [],
                    'error': str(e),
                }
            }

        s = analysis.get('summary', {})
        redundant_threads_summary = {
            'redundancy_types': REDUNDANCY_TYPE_LABELS,
            'total_redundant_thread_patterns': 0,
            'total_redundant_threads': 0,
            'total_cpu_instructions': s.get('total_cpu_instructions', 0),
            'total_redundant_instructions': s.get('total_redundant_instructions', 0),
            'redundant_instructions_ratio': round(s.get('redundant_instructions_ratio', 0), 6),
            'redundant_threads': [],
        }
        for pattern in analysis.get('redundant_patterns', []):
            unique_tid_count = pattern.get('unique_tid_count', pattern.get('redundant_count', 0))
            try:
                unique_tid_count = int(unique_tid_count) if unique_tid_count is not None else 0
            except (TypeError, ValueError):
                unique_tid_count = 0
            redundant_threads_summary['total_redundant_thread_patterns'] += 1
            redundant_threads_summary['total_redundant_threads'] += unique_tid_count
            variants = pattern.get('thread_name_variants', [])
            display_name = (variants[0] if len(variants) == 1 else (pattern.get('thread_name', 'Unknown') + '_*'))
            wp = pattern.get('wakeup_pattern', 'normal')
            type_label = REDUNDANCY_TYPE_LABELS.get(wp, REDUNDANCY_TYPE_LABELS['normal'])
            redundant_threads_summary['redundant_threads'].append({
                'thread_name': display_name,
                'thread_name_variants': variants,
                'type': wp,
                'type_label': type_label,
                'total_thread_count': pattern.get('total_thread_count', unique_tid_count),
                'redundant_count': unique_tid_count,
                'redundant_instructions': pattern.get('redundant_instructions', 0),
                'redundant_instructions_ratio': round(pattern.get('redundant_instructions_ratio', 0), 6),
                'estimated_memory_mb': round(pattern.get('estimated_memory_mb', 0), 2),
                'redundancy_score': pattern.get('redundancy_score', 0),
                'score_breakdown': pattern.get('score_breakdown', {}),
                'redundancy_level': pattern.get('redundancy_level', 'none'),
                'leak_score': pattern.get('leak_score', 0),
                'leak_level': pattern.get('leak_level', 'none'),
                'waiting_ratio': round(pattern.get('avg_waiting_ratio', 0) * 100, 1),
                'wakeup_pattern': wp,
                'all_thread_ids': pattern.get('all_thread_ids', []),
                'redundant_thread_ids': pattern.get('redundant_thread_ids', []),
                'callchain_sample': pattern.get('callchain_sample', []),
            })
        redundant_threads_summary['redundant_threads'].sort(key=lambda x: x['redundancy_score'], reverse=True)

        return {
            'redundant_threads_summary': redundant_threads_summary,
            'summary': s,
            'below_threshold_patterns': analysis.get('below_threshold_patterns', []),
        }
