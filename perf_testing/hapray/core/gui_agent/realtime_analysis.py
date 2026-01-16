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
import threading
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from typing import Optional

from hapray.analyze import analyze_data
from hapray.core.report import ReportGenerator


class RealTimeAnalysisProcess:
    """
    实时分析进程 - 负责在数据采集完成后进行实时分析

    根据架构图，实时分析进程包含三种分析：
    1. Image分析 - 分析图像尺寸和优化
    2. 空刷检测 - 检测空刷帧
    3. hilog分析 - 分析系统日志

    该进程与主进程同步运行，通过文件系统共享数据。
    """

    def __init__(self, max_workers: int = 4, logger: Optional[logging.Logger] = None):
        """
        初始化实时分析进程

        Args:
            max_workers: 线程池最大工作线程数
            logger: 日志记录器
        """
        self.max_workers = max_workers
        self.logger = logger or logging.getLogger(__name__)
        self.executor: Optional[ThreadPoolExecutor] = None
        self.futures: dict[Future, dict] = {}
        self.lock = threading.Lock()
        self.task_analysis_status: dict[str, list[Future]] = {}  # 任务名 -> 分析任务列表

    def start(self):
        """启动实时分析进程"""
        self.executor = ThreadPoolExecutor(max_workers=self.max_workers)
        self.logger.info('实时分析进程已启动 (workers: %d)', self.max_workers)

    def notify_data_collected(self, task_id: int, step_count: int, task_report_path: str) -> None:
        """
        通知数据采集完成，触发实时分析任务

        根据架构图，采集完成后通知数据分析任务，包括：
        - perf/trace数据
        - 截屏
        - 组件树
        - hilog

        Args:
            task_id: 任务ID
            step_count: 步骤编号
            task_report_path: 步骤数据路径
        """
        if not self.executor:
            self.logger.warning('实时分析进程未启动，跳过分析任务')
            return

        self.logger.info(
            '数据采集完成，提交实时分析任务: task_id=%d, step=%d, path=%s',
            task_id,
            step_count,
            task_report_path,
        )

        task_key = f'task{task_id}'
        if task_key not in self.task_analysis_status:
            self.task_analysis_status[task_key] = []

        # 提交实时步骤分析任务（使用 analyze_data 和 ReportGenerator 执行完整分析管线）
        def analyze_and_generate_report(scene_dir: str, step_id: int):
            """分析数据并生成报告"""
            try:
                # 分析数据
                result = analyze_data(scene_dir)
                # 生成报告
                report_generator = ReportGenerator()
                report_generator.generate_report(
                    scene_dirs=[scene_dir],
                    scene_dir=scene_dir,
                )
                return result
            except Exception as e:
                self.logger.error('分析任务执行失败: %s', str(e))
                return {}

        future = self.executor.submit(analyze_and_generate_report, task_report_path, step_count)
        with self.lock:
            self.futures[future] = {
                'type': 'step_analysis',
                'step': step_count,
                'path': task_report_path,
                'task_id': task_id,
            }
            self.task_analysis_status[task_key].append(future)

    def wait_completion(self) -> None:
        """等待所有分析任务完成"""
        if not self.executor:
            return

        self.logger.info('等待所有实时分析任务完成...')

        for future in as_completed(self.futures):
            task_info = self.futures[future]
            try:
                success = future.result()
                status = '成功' if success else '失败'
                self.logger.info(
                    '分析任务完成 [%s]: %s (step=%d, task_id=%d)',
                    status,
                    task_info['type'],
                    task_info['step'],
                    task_info['task_id'],
                )
            except Exception as e:
                self.logger.error('分析任务异常: %s, Error: %s', task_info['type'], str(e))

    def shutdown(self) -> None:
        """关闭实时分析进程"""
        if self.executor:
            self.logger.info('正在关闭实时分析进程...')
            self.executor.shutdown(wait=True)
            self.executor = None
            self.logger.info('实时分析进程已关闭')
