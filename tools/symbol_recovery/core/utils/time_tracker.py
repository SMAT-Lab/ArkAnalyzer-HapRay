#!/usr/bin/env python3
"""
时间统计工具
记录各个步骤的执行时间
"""

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from core.utils.logger import get_logger

logger = get_logger(__name__)


class TimeTracker:
    """时间跟踪器"""

    def __init__(self):
        self.start_time = time.time()
        self.steps: list[dict] = []
        self.current_step: Optional[dict] = None

    def start_step(self, step_name: str, description: str = ''):
        """
        开始一个步骤

        Args:
            step_name: 步骤名称
            description: 步骤描述
        """
        if self.current_step:
            # 结束上一个步骤
            self.end_step()

        self.current_step = {
            'name': step_name,
            'description': description,
            'start_time': time.time(),
            'end_time': None,
            'duration': None,
        }

    def end_step(self, description: str = ''):
        """
        结束当前步骤

        Args:
            description: 可选的结束描述
        """
        if self.current_step:
            self.current_step['end_time'] = time.time()
            self.current_step['duration'] = self.current_step['end_time'] - self.current_step['start_time']
            if description:
                self.current_step['description'] = description
            self.steps.append(self.current_step)
            self.current_step = None

    def get_total_time(self) -> float:
        """获取总执行时间"""
        if self.current_step:
            return time.time() - self.start_time
        if self.steps:
            return self.steps[-1]['end_time'] - self.start_time
        return 0.0

    def get_step_time(self, step_name: str) -> Optional[float]:
        """获取指定步骤的执行时间"""
        for step in self.steps:
            if step['name'] == step_name:
                return step['duration']
        return None

    def format_time(self, seconds: float) -> str:
        """格式化时间"""
        if seconds < 60:
            return f'{seconds:.2f}秒'
        if seconds < 3600:
            minutes = int(seconds // 60)
            secs = seconds % 60
            return f'{minutes}分{secs:.2f}秒'
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = seconds % 60
        return f'{hours}小时{minutes}分{secs:.2f}秒'

    def get_summary(self) -> dict:
        """获取统计摘要"""
        total_time = self.get_total_time()

        summary = {
            'total_time': total_time,
            'total_time_formatted': self.format_time(total_time),
            'steps': [],
            'start_time': datetime.fromtimestamp(self.start_time).isoformat(),
            'end_time': datetime.fromtimestamp(time.time()).isoformat() if not self.current_step else None,
        }

        for step in self.steps:
            summary['steps'].append(
                {
                    'name': step['name'],
                    'description': step.get('description', ''),
                    'duration': step['duration'],
                    'duration_formatted': self.format_time(step['duration']),
                    'percentage': (step['duration'] / total_time * 100) if total_time > 0 else 0,
                }
            )

        return summary

    def print_summary(self):
        """打印统计摘要"""
        summary = self.get_summary()
        logger.info('\n' + '=' * 80)
        logger.info('⏱️  执行时间统计')
        logger.info('=' * 80)
        logger.info('总执行时间: %s', summary['total_time_formatted'])
        logger.info('开始时间: %s', summary['start_time'])
        if summary['end_time']:
            logger.info('结束时间: %s', summary['end_time'])
        logger.info('\n各步骤耗时:')
        logger.info('-' * 80)

        for step in summary['steps']:
            logger.info(
                '  %s %s (%5.1f%%)',
                f'{step["name"]:30s}',
                f'{step["duration_formatted"]:15s}',
                step['percentage'],
            )
            if step['description']:
                logger.info('    └─ %s', step['description'])

        logger.info('=' * 80)

    def save_to_file(self, file_path: str):
        """保存统计信息到文件"""
        summary = self.get_summary()
        file_path = Path(file_path)
        file_path.parent.mkdir(parents=True, exist_ok=True)

        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)

    def to_html(self) -> str:
        """生成HTML格式的统计报告"""
        summary = self.get_summary()

        return """
        <div class="section">
            <h2>⏱️ 执行时间统计</h2>
            <div class="time-summary">
                <div class="time-item">
                    <span class="time-label">总执行时间:</span>
                    <span class="time-value">{total_time}</span>
                </div>
                <div class="time-item">
                    <span class="time-label">开始时间:</span>
                    <span class="time-value">{start_time}</span>
                </div>
                {end_time_html}
            </div>
            <table class="time-table">
                <thead>
                    <tr>
                        <th>步骤</th>
                        <th>耗时</th>
                        <th>占比</th>
                        <th>描述</th>
                    </tr>
                </thead>
                <tbody>
                    {steps_html}
                </tbody>
            </table>
        </div>
        <style>
        .time-summary {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 15px;
            margin-bottom: 20px;
        }}
        .time-item {{
            background: white;
            padding: 15px;
            border-radius: 5px;
            border: 1px solid #ddd;
        }}
        .time-label {{
            font-size: 0.9em;
            color: #666;
            display: block;
            margin-bottom: 5px;
        }}
        .time-value {{
            font-size: 1.3em;
            font-weight: bold;
            color: #4CAF50;
        }}
        .time-table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 15px;
        }}
        .time-table th {{
            background-color: #4CAF50;
            color: white;
            padding: 10px;
            text-align: left;
        }}
        .time-table td {{
            padding: 10px;
            border-bottom: 1px solid #ddd;
        }}
        .time-table tr:hover {{
            background-color: #f5f5f5;
        }}
        </style>
        """.format(
            total_time=summary['total_time_formatted'],
            start_time=summary['start_time'],
            end_time_html=f'<div class="time-item"><span class="time-label">结束时间:</span><span class="time-value">{summary["end_time"]}</span></div>'
            if summary['end_time']
            else '',
            steps_html='\n'.join(
                [
                    f"""
                <tr>
                    <td>{step['name']}</td>
                    <td>{step['duration_formatted']}</td>
                    <td>{step['percentage']:.1f}%</td>
                    <td>{step['description'] or ''}</td>
                </tr>
                """
                    for step in summary['steps']
                ]
            ),
        )
