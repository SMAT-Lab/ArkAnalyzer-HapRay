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

import base64
import json
import logging
import os
import random
import time
from datetime import datetime
from typing import Optional

from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont

from hapray.haptest.state_manager import StateManager, StateStackEntry, TestContext, UIState
from hapray.haptest.strategy import BaseStrategy

# 加载.env文件
load_dotenv(override=True)

Log = logging.getLogger('HapTest.LLMStrategy')


class LLMStrategy(BaseStrategy):
    """基于大模型的智能探索策略

    使用视觉语言模型分析UI截图,智能决策下一步操作
    优先探索3级页面深度
    """

    def __init__(self, api_key: str = None, model: str = None, target_depth: int = 3, base_url: str = None, use_llm_state_comparison: bool = True):
        """
        初始化LLM策略

        Args:
            api_key: LLM API密钥(如果为None,从环境变量OPENAI_API_KEY读取)
            model: 使用的模型名称(如果为None,从环境变量OPENAI_MODEL读取,默认gpt-4o)
            target_depth: 目标探索深度(默认3级)
            base_url: API基础URL(如果为None,从环境变量OPENAI_BASE_URL读取,默认OpenAI官方地址)
            app_name: 应用名称(用于LLM提示词)
            use_llm_state_comparison: 是否使用LLM状态比较(默认True)
        """
        self.api_key = api_key or os.getenv('OPENAI_API_KEY')
        self.model = model or os.getenv('OPENAI_MODEL', 'gpt-4o')
        self.base_url = (base_url or os.getenv('OPENAI_BASE_URL', 'https://api.openai.com/v1')).rstrip('/')
        self.target_depth = target_depth
        self.current_depth = 0
        self.use_llm_state_comparison = use_llm_state_comparison
        self.state_stack = []  # 状态栈,用于跟踪导航深度
        self.last_state_hash = None  # 上一个状态的哈希
        self.action_history = []  # 操作历史记录
        self.last_page_description = ""  # 最后一次LLM生成的页面描述
        self.last_decision = {}  # 最后一次LLM决策的完整信息

        # LLM state comparator (lazy init)
        self.llm_comparator = None

        if not self.api_key:
            Log.warning('LLM API key not found. Set OPENAI_API_KEY environment variable.')

        Log.info(f'[LLM] 初始化 - Model: {self.model}, Base URL: {self.base_url}, Target Depth: {self.target_depth}, LLM Comparison: {use_llm_state_comparison}')

    def decide_next_action(self, ui_state: UIState, state_mgr: StateManager) -> tuple[str, Optional[dict]]:
        """
        使用LLM决策下一步操作

        Args:
            ui_state: 当前UI状态
            state_mgr: 状态管理器

        Returns:
            (action_type, target) 元组
        """
        Log.info('[LLM] 开始LLM决策')

        # 检查是否在目标应用内
        if not ui_state.is_in_target_app():
            Log.info('[LLM] 不在目标应用内,执行返回操作')
            return ('back', None)

        # 获取未访问的元素
        unvisited = state_mgr.get_unvisited_elements(ui_state)

        # 如果没有未访问元素且已达到目标深度,返回
        if not unvisited and self.current_depth >= self.target_depth:
            Log.info(f'[LLM] 已达到目标深度{self.target_depth},且无未访问元素')
            if self.current_depth > 0:
                self.current_depth -= 1
                return ('back', None)
            return ('stop', None)

        # 如果没有未访问元素,尝试滚动或返回
        if not unvisited:
            if random.random() < 0.3:
                Log.info('[LLM] 无未访问元素,尝试滚动')
                return ('scroll', {'direction': 'up'})
            Log.info('[LLM] 无未访问元素,执行返回')
            if self.current_depth > 0:
                self.current_depth -= 1
            return ('back', None)

        # 调用LLM进行决策
        try:
            action_type, target = self._call_llm_api(ui_state, unvisited, state_mgr)

            # Store page description and decision in UIState for later use
            if self.last_page_description:
                ui_state._llm_description = self.last_page_description

                # Backfill description to the last empty entry in stack
                self._backfill_description_to_stack(self.last_page_description)

            # Store full decision information
            if self.last_decision:
                ui_state._llm_decision = self.last_decision

            return (action_type, target)

        except Exception as e:
            Log.error(f'[LLM] LLM调用失败: {e}')
            # 降级到简单策略
            return self._fallback_strategy(unvisited)

    def update_depth_after_action(self, action_type: str, prev_ui_state: UIState, new_ui_state: UIState, target: Optional[dict] = None, report_path: str = None):
        """
        在执行操作后更新深度 (Enhanced with LLM comparison)

        Args:
            action_type: 执行的操作类型
            prev_ui_state: 操作前的UI状态对象
            new_ui_state: 操作后的UI状态对象
            target: 操作目标（元素或方向信息）
            report_path: 报告路径（用于生成可视化）
        """
        if not self.use_llm_state_comparison:
            # Fallback to hash-based comparison
            self._update_depth_hash_based(action_type, prev_ui_state.state_hash, new_ui_state.state_hash)
            return

        

        # Initialize LLM comparator if needed
        if self.llm_comparator is None:
            from hapray.haptest.llm_state_comparator import LLMStateComparator
            self.llm_comparator = LLMStateComparator(
                api_key=self.api_key,
                model=self.model,
                base_url=self.base_url,
                enable_parallel=True
            )

        # Initialize on first call - add prev_ui_state as initial state
        if not self.state_stack:
            description = getattr(prev_ui_state, '_llm_description', 'Initial state')
            entry = StateStackEntry(
                state_hash=prev_ui_state.state_hash,
                screenshot_path=prev_ui_state.screenshot_path,
                description=description,
                step_id=prev_ui_state.step_id,
                timestamp=time.time(),
                element_count=len(prev_ui_state.clickable_elements),
                depth=0
            )
            self.state_stack.append(entry)
            self.current_depth = 0
            Log.info('[LLM] Initialized state stack with initial state')
            # Don't return - continue to process new_ui_state
        
        # Save stack before for visualization
        import copy
        stack_before = copy.deepcopy(self.state_stack)
        depth_before = self.current_depth

        # Don't generate description for new_ui_state - will be backfilled in next iteration
        new_description = ""  # Empty string, will be filled later

        # Create test context
        test_context = TestContext(
            app_package=new_ui_state.app_package or "Unknown",
            app_name=new_ui_state.app_name,
            target_depth=self.target_depth,
            current_depth=self.current_depth,
            test_goal="Explore the UI up to the third-level page"
        )

        is_new_state = False
        matching_idx = None

        
        # Compare new state with stack
        is_new_state, matching_idx = self.llm_comparator.compare_with_stack(
            new_ui_state,
            new_description,
            self.state_stack,
            test_context
        )

        if is_new_state:
            # Entered new page
            entry = StateStackEntry(
                state_hash=new_ui_state.state_hash,
                screenshot_path=new_ui_state.screenshot_path,
                description=new_description,
                step_id=new_ui_state.step_id,
                timestamp=time.time(),
                element_count=len(new_ui_state.clickable_elements),
                depth=len(self.state_stack)
            )
            self.state_stack.append(entry)
            self.current_depth = len(self.state_stack) - 1
            Log.info(f'[LLM] Entered new page (depth={self.current_depth}): {new_description[:50]}...')
        else:
            # Returned to existing state
            self.state_stack = self.state_stack[:matching_idx + 1]
            self.state_stack[matching_idx].visit_count += 1
            self.current_depth = matching_idx
            Log.info(f'[LLM] Returned to existing state (depth={self.current_depth})')

        

        # Generate visualization if report_path is provided
        if report_path and self.llm_comparator:
            depth_after = self.current_depth
            comparison_results = getattr(self.llm_comparator, 'last_comparison_results', [])

            self._generate_depth_visualization(
                step_id=new_ui_state.step_id,
                report_path=report_path,
                stack_before=stack_before,
                prev_ui_state=prev_ui_state,
                new_ui_state=new_ui_state,
                action_type=action_type,
                target=target,
                comparison_results=comparison_results,
                is_new_state=is_new_state,
                matching_idx=matching_idx,
                stack_after=self.state_stack,
                depth_before=depth_before,
                depth_after=depth_after
            )

    def _update_depth_hash_based(self, action_type: str, prev_state_hash: str, new_state_hash: str):
        """
        Hash-based depth update (fallback method)
        """
        # 如果是第一次,初始化
        if self.last_state_hash is None:
            self.last_state_hash = prev_state_hash
            self.state_stack.append(prev_state_hash)
            self.current_depth = 0
            Log.info('[LLM] 初始化状态栈 (hash-based)')
            # return

        # 状态没有变化,深度不变
        if new_state_hash == prev_state_hash:
            Log.debug('[LLM] 状态未变化,深度保持不变')
            return

        if action_type == 'click':
            # 点击后状态变化,说明进入了新页面
            if new_state_hash not in self.state_stack:
                self.state_stack.append(new_state_hash)
                self.current_depth = len(self.state_stack) - 1
                Log.info(f'[LLM] 进入新页面,深度增加至{self.current_depth}')
            else:
                # 点击后回到了之前的状态(比如点击了返回按钮)
                try:
                    idx = self.state_stack.index(new_state_hash)
                    self.state_stack = self.state_stack[: idx + 1]
                    self.current_depth = len(self.state_stack) - 1
                    Log.info(f'[LLM] 返回到已访问状态,深度减少至{self.current_depth}')
                except ValueError:
                    pass

        elif action_type == 'back':
            # 返回操作
            if len(self.state_stack) > 1:
                self.state_stack.pop()
                self.current_depth = len(self.state_stack) - 1
                Log.info(f'[LLM] 返回操作,深度减少至{self.current_depth}')

        elif action_type == 'scroll':
            # 滚动不改变深度,但可能改变状态哈希
            Log.debug('[LLM] 滚动操作,深度不变')

        self.last_state_hash = new_state_hash

    def _backfill_description_to_stack(self, description: str):
        """
        将描述回填到栈中最后一个空描述的 entry

        由于UI状态的哈希可能在迭代之间发生变化，我们不能依赖哈希匹配。
        相反，我们回填栈中最后一个需要描述的条目（通常是上一次添加的）。

        Args:
            description: 生成的描述
        """
        if not self.use_llm_state_comparison or not self.state_stack:
            return

        # 从后向前查找第一个空描述的entry
        for entry in reversed(self.state_stack):
            if not entry.description or entry.description == "":
                entry.description = description
                Log.info(f'[LLM] Backfilled description to stack entry (step {entry.step_id}): {description[:50]}...')
                return

        Log.debug('[LLM] No empty description entry found in stack for backfill')


    def _generate_depth_visualization(
        self,
        step_id: int,
        report_path: str,
        stack_before: list,
        prev_ui_state: UIState,
        new_ui_state: UIState,
        action_type: str,
        target: Optional[dict],
        comparison_results: list,
        is_new_state: bool,
        matching_idx: Optional[int],
        stack_after: list,
        depth_before: int,
        depth_after: int
    ):
        """
        生成深度计算可视化 HTML

        Args:
            step_id: 步骤 ID
            report_path: 报告路径
            stack_before: 计算前的栈
            prev_ui_state: 操作前的UI状态
            new_ui_state: 操作后的UI状态
            action_type: 操作类型
            target: 操作目标（元素或方向）
            comparison_results: 比较结果列表
            is_new_state: 是否为新状态
            matching_idx: 匹配的索引
            stack_after: 计算后的栈
            depth_before: 计算前深度
            depth_after: 计算后深度
        """
        try:
            import os

            # 创建输出目录
            ui_dir = os.path.join(report_path, 'ui', f'step{step_id}')
            os.makedirs(ui_dir, exist_ok=True)

            output_path = os.path.join(ui_dir, 'depth_calculation.html')

            # 生成 HTML 内容
            html_content = self._build_visualization_html(
                step_id,
                report_path,
                stack_before,
                prev_ui_state,
                new_ui_state,
                action_type,
                target,
                comparison_results,
                is_new_state,
                matching_idx,
                stack_after,
                depth_before,
                depth_after
            )

            # 写入文件
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(html_content)

            Log.info(f'[LLM] Generated depth visualization: {output_path}')

        except Exception as e:
            Log.error(f'[LLM] Failed to generate visualization: {e}')

    def _build_visualization_html(
        self,
        step_id: int,
        report_path: str,
        stack_before: list,
        prev_ui_state: UIState,
        new_ui_state: UIState,
        action_type: str,
        target: Optional[dict],
        comparison_results: list,
        is_new_state: bool,
        matching_idx: Optional[int],
        stack_after: list,
        depth_before: int,
        depth_after: int
    ) -> str:
        """构建可视化 HTML 内容"""

        # CSS 样式
        css = """
        <style>
            body {
                font-family: 'Segoe UI', Arial, sans-serif;
                margin: 20px;
                background: #f5f5f5;
            }
            .container {
                max-width: 1400px;
                margin: 0 auto;
                background: white;
                padding: 30px;
                border-radius: 8px;
                box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            }
            h1 {
                color: #2c3e50;
                border-bottom: 3px solid #3498db;
                padding-bottom: 10px;
            }
            h2 {
                color: #34495e;
                margin-top: 30px;
                border-left: 4px solid #3498db;
                padding-left: 15px;
            }
            .section {
                margin: 30px 0;
                padding: 20px;
                background: #fafafa;
                border-radius: 6px;
            }
            .stack-container {
                display: flex;
                gap: 20px;
                overflow-x: auto;
                padding: 20px 0;
            }
            .state-card {
                border: 2px solid #bdc3c7;
                padding: 15px;
                min-width: 220px;
                background: white;
                border-radius: 6px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }
            .state-card h4 {
                margin-top: 0;
                color: #2c3e50;
                font-size: 14px;
            }
            .state-card.current {
                border-color: #e74c3c;
                background: #fee;
            }
            .state-card.matched {
                border-color: #27ae60;
                background: #efe;
            }
            .state-card img {
                max-width: 100%;
                height: auto;
                max-height: 400px;
                object-fit: contain;
                border: 1px solid #ddd;
                border-radius: 4px;
            }
            .state-card p {
                margin: 8px 0;
                font-size: 13px;
                word-break: break-word;
            }
            .comparison-table {
                width: 100%;
                border-collapse: collapse;
                margin-top: 15px;
                background: white;
            }
            .comparison-table th {
                background: #34495e;
                color: white;
                padding: 12px 8px;
                text-align: left;
                font-weight: 600;
            }
            .comparison-table td {
                border: 1px solid #ddd;
                padding: 10px 8px;
                font-size: 13px;
            }
            .comparison-table tr:hover {
                background: #f8f9fa;
            }
            .same-state { background-color: #d4edda !important; }
            .diff-state { background-color: #f8d7da !important; }
            .decision-box {
                background: #e3f2fd;
                padding: 20px;
                border-left: 5px solid #2196f3;
                border-radius: 4px;
                margin: 20px 0;
            }
            .decision-box p {
                margin: 10px 0;
                font-size: 15px;
            }
            .decision-box strong {
                color: #1976d2;
            }
            .badge {
                display: inline-block;
                padding: 4px 8px;
                border-radius: 3px;
                font-size: 12px;
                font-weight: bold;
            }
            .badge-success { background: #27ae60; color: white; }
            .badge-danger { background: #e74c3c; color: white; }
            .badge-info { background: #3498db; color: white; }
            footer {
                margin-top: 50px;
                padding-top: 20px;
                border-top: 1px solid #ddd;
                color: #7f8c8d;
                text-align: center;
            }
        </style>
        """

        # 构建栈前状态 HTML
        stack_before_html = self._build_stack_html(stack_before, report_path, step_id, "before")

        # 构建当前状态 HTML (展示操作前后的两个状态)
        current_state_html = self._build_current_state_html(prev_ui_state, new_ui_state, action_type, target)

        # 构建比较结果表格
        comparison_table_html = self._build_comparison_table_html(comparison_results)

        # 构建决策信息
        decision_html = self._build_decision_html(
            action_type, is_new_state, matching_idx, depth_before, depth_after
        )

        # 构建栈后状态 HTML
        stack_after_html = self._build_stack_html(stack_after, report_path, step_id, "after", matching_idx)

        # 组装完整 HTML
        html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Depth Calculation - Step {step_id}</title>
    {css}
</head>
<body>
    <div class="container">
        <h1>🔍 Depth Calculation Visualization - Step {step_id}</h1>

        <div class="section">
            <h2>📚 Stack Before (Current Depth: {depth_before})</h2>
            <div class="stack-container">
                {stack_before_html}
            </div>
        </div>

        <div class="section">
            <h2>🎯 Action Execution: Before → After</h2>
            {current_state_html}
        </div>

        <div class="section">
            <h2>⚖️ Comparison Results</h2>
            {comparison_table_html}
        </div>

        <div class="section">
            <h2>✨ Decision</h2>
            {decision_html}
        </div>

        <div class="section">
            <h2>📚 Stack After (Current Depth: {depth_after})</h2>
            <div class="stack-container">
                {stack_after_html}
            </div>
        </div>

        <footer>
            <p>Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        </footer>
    </div>
</body>
</html>"""

        return html

    def _build_stack_html(self, stack: list, report_path: str, current_step: int, stage: str, highlight_idx: Optional[int] = None) -> str:
        """构建栈的 HTML"""
        if not stack:
            return "<p>Empty stack</p>"

        html_parts = []
        for idx, entry in enumerate(stack):
            # 确定 CSS 类
            css_class = "state-card"
            if stage == "after" and highlight_idx is not None and idx == highlight_idx:
                css_class += " matched"

            # 计算相对路径
            screenshot_rel_path = self._get_relative_screenshot_path(
                entry.screenshot_path, report_path, current_step
            )

            # 截断描述
            description = entry.description[:100] + "..." if len(entry.description) > 100 else entry.description
            if not description:
                description = "[Empty - will be backfilled]"

            html_parts.append(f"""
            <div class="{css_class}" style="max-width:300px">
                <h4>Index {idx} (Depth {entry.depth})</h4>
                <img src="{screenshot_rel_path}" alt="State {idx}" style=" height: auto; max-height: 500px; object-fit: contain;">
                <p><strong>Description:</strong> {description}</p>
                <p><strong>Hash:</strong> {entry.state_hash[:8]}...</p>
                <p><strong>Visits:</strong> {entry.visit_count}</p>
                <p><strong>Step:</strong> {entry.step_id}</p>
            </div>
            """)

        return "\n".join(html_parts)

    def _build_current_state_html(self, prev_ui_state: UIState, new_ui_state: UIState, action_type: str, target: Optional[dict] = None) -> str:
        """构建当前状态的 HTML - 展示操作前后的两个状态"""
        prev_description = getattr(prev_ui_state, '_llm_description', '')
        if not prev_description:
            prev_description = "[Empty - will be backfilled in next iteration]"

        new_description = getattr(new_ui_state, '_llm_description', '')
        if not new_description:
            new_description = "[Empty - will be backfilled in next iteration]"

        # 获取LLM决策信息
        prev_decision = getattr(prev_ui_state, '_llm_decision', {})

        # 构建操作信息 - 使用LLM决策信息
        action_info = f"<strong>Action:</strong> <span class=\"badge badge-info\">{action_type.upper()}</span>"

        # 显示LLM决策的详细信息
        if prev_decision:
            page_desc = prev_decision.get('page_description', '')
            brief = prev_decision.get('brief', '')
            element_idx = prev_decision.get('element_index', None)

            if page_desc:
                action_info += f"<br><br><strong>Page Analysis:</strong><br><em>{page_desc}</em>"

            if brief:
                action_info += f"<br><br><strong>Decision Brief:</strong><br><em>{brief}</em>"

            if element_idx is not None:
                action_info += f"<br><br><strong>Element Index:</strong> {element_idx}"

        # 如果有target信息，也显示
        if target and action_type == 'click':
            target_text = target.get('text', '')
            target_type = target.get('type', '')
            target_id = target.get('id', '')
            action_info += f"<br><br><strong>Target Type:</strong> {target_type}"
            if target_text:
                action_info += f"<br><strong>Target Text:</strong> '{target_text}'"
            if target_id:
                action_info += f"<br><strong>Target ID:</strong> {target_id}"
        elif target and action_type == 'scroll':
            direction = target.get('direction', 'unknown')
            action_info += f"<br><br><strong>Scroll Direction:</strong> {direction}"

        return f"""
        <div style="display: flex; gap: 20px; align-items: center; justify-content: center; flex-wrap: wrap;">
            <div class="state-card" style="max-width: 350px;">
                <h4 style="color: #2c3e50; margin-top: 0;">📱 State Before Action</h4>
                <img src="screenshot_current_1.png" alt="Previous State" style="max-width: 100%; height: auto;">
                <p><strong>Description:</strong> {prev_description}</p>
                <p><strong>Hash:</strong> {prev_ui_state.state_hash[:8]}...</p>
                <p><strong>Step:</strong> {prev_ui_state.step_id}</p>
            </div>

            <div style="min-width: 250px; max-width: 400px; padding: 20px; background: #fff3cd; border: 2px solid #ffc107; border-radius: 8px;">
                <h4 style="color: #856404; margin-top: 0; text-align: center;">⚡ LLM Decision & Action</h4>
                <div style="text-align: left; font-size: 13px; line-height: 1.6;">
                    {action_info}
                </div>
            </div>

            <div class="state-card current" style="max-width: 350px;">
                <h4 style="color: #2c3e50; margin-top: 0;">📱 State After Action</h4>
                <img src="screenshot_end_1.png" alt="Current State" style="max-width: 100%; height: auto;">
                <p><strong>Description:</strong> {new_description}</p>
                <p><strong>Hash:</strong> {new_ui_state.state_hash[:8]}...</p>
                <p><strong>Step:</strong> {new_ui_state.step_id}</p>
            </div>
        </div>
        """

    def _build_comparison_table_html(self, comparison_results: list) -> str:
        """构建比较结果表格的 HTML"""
        if not comparison_results:
            return "<p>No comparison results available</p>"

        rows = []
        for idx, result in enumerate(comparison_results):
            row_class = "same-state" if result.is_same_state else "diff-state"
            is_same_icon = "✅ Yes" if result.is_same_state else "❌ No"

            # 截断 reasoning
            reasoning = result.reasoning[:80] + "..." if len(result.reasoning) > 80 else result.reasoning

            # 格式化 key_differences
            differences = ", ".join(result.key_differences[:3]) if result.key_differences else "None"

            rows.append(f"""
            <tr class="{row_class}">
                <td>{idx}</td>
                <td>{is_same_icon}</td>
                <td>{result.confidence:.2f}</td>
                <td>{result.similarity_score:.2f}</td>
                <td>{reasoning}</td>
                <td>{differences}</td>
            </tr>
            """)

        return f"""
        <table class="comparison-table">
            <thead>
                <tr>
                    <th>Stack Index</th>
                    <th>Is Same State</th>
                    <th>Confidence</th>
                    <th>Similarity</th>
                    <th>Reasoning</th>
                    <th>Key Differences</th>
                </tr>
            </thead>
            <tbody>
                {"".join(rows)}
            </tbody>
        </table>
        """

    def _build_decision_html(
        self,
        action_type: str,
        is_new_state: bool,
        matching_idx: Optional[int],
        depth_before: int,
        depth_after: int
    ) -> str:
        """构建决策信息的 HTML"""
        if is_new_state:
            operation = "Add new state to stack"
            badge_class = "badge-success"
        else:
            operation = f"Navigate back to existing state (index {matching_idx})"
            badge_class = "badge-info"

        depth_change = f"{depth_before} → {depth_after}"
        if depth_after > depth_before:
            depth_icon = "📈"
        elif depth_after < depth_before:
            depth_icon = "📉"
        else:
            depth_icon = "➡️"

        return f"""
        <div class="decision-box">
            <p><strong>Action Type:</strong> <span class="badge badge-info">{action_type.upper()}</span></p>
            <p><strong>Is New State:</strong> <span class="badge {badge_class}">{'YES' if is_new_state else 'NO'}</span></p>
            <p><strong>Matching Index:</strong> {matching_idx if matching_idx is not None else 'N/A'}</p>
            <p><strong>Operation:</strong> {operation}</p>
            <p><strong>Depth Change:</strong> {depth_icon} {depth_change}</p>
        </div>
        """

    def _get_relative_screenshot_path(self, screenshot_path: str, report_path: str, current_step: int) -> str:
        """获取截图的相对路径"""
        import os
        # 从绝对路径提取 step 信息
        # screenshot_path 格式: .../ui/stepX/screenshot_current_1.png
        # 需要返回相对于当前 stepY 的路径: ../../stepX/screenshot_current_1.png

        try:
            # 提取 stepX
            parts = screenshot_path.split(os.sep)
            for i, part in enumerate(parts):
                if part.startswith('step') and part[4:].isdigit():
                    step_num = part[4:]
                    filename = parts[-1]
                    return f"../step{step_num}/{filename}"
        except Exception:
            pass

        # 降级：返回文件名
        return os.path.basename(screenshot_path)


    def _generate_fallback_description(self, ui_state: UIState) -> str:
        """
        Generate simple description without LLM
        """
        element_types = {}
        for elem in ui_state.clickable_elements:
            elem_type = elem.get('type', 'Unknown')
            element_types[elem_type] = element_types.get(elem_type, 0) + 1

        type_summary = ', '.join([f"{count} {type}" for type, count in element_types.items()])

        return f"Page with {len(ui_state.clickable_elements)} clickable elements: {type_summary}"

    def _call_llm_api(
        self, ui_state: UIState, unvisited: list, state_mgr: StateManager
    ) -> tuple[str, Optional[dict]]:
        """
        调用LLM API进行决策

        Args:
            ui_state: 当前UI状态
            unvisited: 未访问的元素列表
            state_mgr: 状态管理器

        Returns:
            (action_type, target) 元组
        """
        # 在截图上绘制边界框
        annotated_image_path = self._draw_bounding_boxes(ui_state.screenshot_path, unvisited)

        # 读取截图并转换为base64
        screenshot_base64 = self._encode_image(annotated_image_path)

        # 构建提示词
        prompt = self._build_prompt(ui_state, unvisited, state_mgr)

        # 调用OpenAI API
        import requests

        headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {self.api_key}'}

        payload = {
            'model': self.model,
            'messages': [
                {
                    'role': 'user',
                    'content': [
                        {'type': 'text', 'text': prompt},
                        {'type': 'image_url', 'image_url': {'url': f'data:image/png;base64,{screenshot_base64}'}},
                    ],
                }
            ],
            # 'max_tokens': 500,
        }

        response = requests.post(
            f'{self.base_url}/chat/completions', headers=headers, json=payload, timeout=300
        )

        if response.status_code != 200:
            raise RuntimeError(f'API调用失败: {response.status_code} - {response.text}')

        result = response.json()
        llm_response = result['choices'][0]['message']['content']

        Log.debug(f'[LLM] 模型响应: {llm_response}')

        # 解析LLM响应
        return self._parse_llm_response(llm_response, unvisited)

    def _draw_bounding_boxes(self, screenshot_path: str, elements: list) -> str:
        """
        在截图上绘制元素边界框

        Args:
            screenshot_path: 原始截图路径
            elements: 元素列表

        Returns:
            标注后的图片路径
        """
        try:
            # 打开图片
            image = Image.open(screenshot_path)
            draw = ImageDraw.Draw(image)

            # 尝试加载字体,如果失败使用默认字体
            try:
                font = ImageFont.truetype('arial.ttf', 30)
            except Exception:
                font = ImageFont.load_default()

            # 为每个元素绘制边界框
            for idx, elem in enumerate(elements):
                bounds = elem.get('bounds')
                if not bounds:
                    continue

                # bounds是字典格式: {'left': x, 'top': y, 'right': x2, 'bottom': y2}
                left = int(bounds['left'])
                top = int(bounds['top'])
                right = int(bounds['right'])
                bottom = int(bounds['bottom'])

                # 绘制矩形框(红色,线宽3)
                draw.rectangle([left, top, right, bottom], outline='red', width=3)

                # 在左上角绘制索引号
                text = str(idx)
                # 绘制文字背景
                draw.rectangle([left, top - 35, left + 40, top], fill='red')
                # 绘制文字
                draw.text((left + 5, top - 32), text, fill='white', font=font)

            # 保存标注后的图片
            annotated_path = screenshot_path.replace('.png', '_annotated.png')
            image.save(annotated_path)
            Log.debug(f'[LLM] 已保存标注图片: {annotated_path}')

            return annotated_path

        except Exception as e:
            Log.error(f'[LLM] 绘制边界框失败: {e}')
            # 如果失败,返回原始图片路径
            return screenshot_path

    def _build_prompt(self, ui_state: UIState, unvisited: list, state_mgr: StateManager) -> str:
        """构建LLM提示词"""
        # 提取元素信息
        elements_info = []
        for idx, elem in enumerate(unvisited):  
            elem_text = elem.get('text', '')
            elem_type = elem.get('type', '')
            elem_id = elem.get('id', '')
            elements_info.append(f"{idx}. {elem_type} - '{elem_text}' (id: {elem_id})")

        elements_str = '\n'.join(elements_info) if elements_info else '无可点击元素'

        # 构建历史记录字符串
        if self.action_history:
            history_str = '\n'.join([f"{i + 1}. {h}" for i, h in enumerate(self.action_history)])
        else:
            history_str = '暂无历史操作'

        prompt = f"""你是一个UI自动化测试助手。当前正在测试应用: {ui_state.app_name} ({ui_state.app_package})
测试目标: 优先遍历第{self.target_depth}级深度的页面，尽可能覆盖更多不同的{self.target_depth}级页面，提高{self.target_depth}级页面的覆盖率

**当前状态:**
- 当前深度: {self.current_depth}/{self.target_depth}
- 可点击元素数: {len(unvisited)}
- 已访问状态数: {len(state_mgr.visited_states)}

**可点击元素列表:**
{elements_str}

**截图说明:**
截图中的红色边界框标注了可点击元素的位置,左上角的数字对应元素列表中的索引号。

**历史操作记录:**
{history_str}

**任务目标和策略:**
1. **当深度 < {self.target_depth} 时**: 优先选择能够进入更深层级的操作（如导航按钮、菜单项、列表项等），快速到达第{self.target_depth}级
2. **当深度 = {self.target_depth} 时**:
   - 优先探索当前页面的不同功能和区域，尽可能点击不同的元素
   - 避免重复点击相似的元素
   - 充分遍历第{self.target_depth}级的不同页面，提高覆盖率
3. **当深度 > {self.target_depth} 时**: 使用back操作返回到第{self.target_depth}级，继续探索其他区域

**决策要求:**
请分析截图和元素列表,完成以下任务:
1. 提供当前页面的简短描述(2-3句话,描述页面类型和主要功能)
2. 根据当前深度选择最合适的下一步操作

**注意事项:**
1. 请勿跳转到其他应用
2. 请勿进行支付操作
3. 在第{self.target_depth}级页面时，优先探索不同的功能模块和区域，避免重复访问相同类型的页面
4. 如果当前页面已经充分探索，考虑返回上一级寻找其他入口到达不同的第{self.target_depth}级页面

返回JSON格式:
{{
    "page_description": "当前页面的简短描述",
    "action": "click",
    "element_index": 0,
    "brief": "简短描述本次操作的目的和预期结果"
}}

或者返回其他操作:
- {{"page_description": "描述", "action": "scroll", "direction": "up", "brief": "描述"}} - 向上滚动
- {{"page_description": "描述", "action": "scroll", "direction": "down", "brief": "描述"}} - 向下滚动
- {{"page_description": "描述", "action": "back", "brief": "描述"}} - 返回上一页
- {{"page_description": "描述", "action": "stop", "brief": "描述"}} - 停止探索

请直接返回JSON,不要包含其他文字。"""
        
        Log.debug(prompt)

        return prompt

    def _parse_llm_response(self, llm_response: str, unvisited: list) -> tuple[str, Optional[dict]]:
        """解析LLM响应"""
        try:
            # 尝试提取JSON
            llm_response = llm_response.strip()
            if '```json' in llm_response:
                llm_response = llm_response.split('```json')[1].split('```')[0].strip()
            elif '```' in llm_response:
                llm_response = llm_response.split('```')[1].split('```')[0].strip()

            decision = json.loads(llm_response)

            action = decision.get('action', 'click')
            brief = decision.get('brief', '')
            page_description = decision.get('page_description', '')

            # Store full decision for later use in visualization
            self.last_decision = {
                'page_description': page_description,
                'action': action,
                'brief': brief,
                'element_index': decision.get('element_index', None),
                'direction': decision.get('direction', None)
            }

            # Store page description for later use in state comparison
            if page_description:
                self.last_page_description = page_description
                Log.debug(f'[LLM] 页面描述: {page_description}')

            Log.info(f'[LLM] 决策: {action}, Brief: {brief}')

            # 记录到历史
            if brief and page_description:
                self.action_history.append(f"{page_description}。{brief}(当前深度：{self.current_depth})")
                if len(self.action_history) > 10:
                    self.action_history.pop(0)

            if action == 'click':
                element_index = decision.get('element_index', 0)
                if 0 <= element_index < len(unvisited):
                    return ('click', unvisited[element_index])
                # 如果索引无效,返回第一个元素
                return ('click', unvisited[0]) if unvisited else ('scroll', {'direction': 'up'})

            if action == 'scroll':
                direction = decision.get('direction', 'up')
                return ('scroll', {'direction': direction})

            if action == 'back':
                return ('back', None)

            if action == 'stop':
                return ('stop', None)

            # 默认返回点击第一个元素
            return ('click', unvisited[0]) if unvisited else ('back', None)

        except Exception as e:
            Log.error(f'[LLM] 解析响应失败: {e}')
            # 降级策略
            return ('click', unvisited[0]) if unvisited else ('back', None)

    def _encode_image(self, image_path: str) -> str:
        """将图片编码为base64"""
        try:
            with open(image_path, 'rb') as image_file:
                return base64.b64encode(image_file.read()).decode('utf-8')
        except Exception as e:
            Log.error(f'[LLM] 图片编码失败: {e}')
            raise

    def _fallback_strategy(self, unvisited: list) -> tuple[str, Optional[dict]]:
        """降级策略:当LLM失败时使用"""
        Log.info('[LLM] 使用降级策略')

        if not unvisited:
            if self.current_depth > 0:
                self.current_depth -= 1
                return ('back', None)
            return ('stop', None)

        # 优先选择按钮类型的元素
        for elem in unvisited:
            elem_type = elem.get('type', '').lower()
            if 'button' in elem_type:
                self.current_depth += 1
                return ('click', elem)

        # 否则选择第一个元素
        self.current_depth += 1
        return ('click', unvisited[0])
