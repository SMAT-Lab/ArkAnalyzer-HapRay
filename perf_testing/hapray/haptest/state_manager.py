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

import hashlib
import json
import logging
import re
from typing import Optional

Log = logging.getLogger('HapTest.State')


class UIState:
    """UI状态封装"""

    def __init__(
        self,
        step_id: int,
        screenshot_path: str,
        element_tree_path: str,
        inspector_path: str,
        app_package: str = None,
        current_bundle_name: str = None,
    ):
        self.step_id = step_id
        self.screenshot_path = screenshot_path
        self.element_tree_path = element_tree_path
        self.inspector_path = inspector_path
        self.app_package = app_package
        self.current_bundle_name = current_bundle_name
        self._clickable_elements = None
        self._state_hash = None

    @property
    def clickable_elements(self) -> list:
        """延迟解析可点击元素"""
        if self._clickable_elements is None:
            self._clickable_elements = self._parse_clickable_elements()
        return self._clickable_elements

    @property
    def state_hash(self) -> str:
        """延迟计算状态哈希"""
        if self._state_hash is None:
            self._state_hash = self._compute_hash()
        return self._state_hash

    def is_in_target_app(self) -> bool:
        """检查当前是否在目标应用内"""
        if self.current_bundle_name is None or self.app_package is None:
            return True  # 无法判断时默认认为在应用内
        return self.current_bundle_name == self.app_package

    def _parse_clickable_elements(self) -> list:
        """从inspector JSON解析可点击元素"""
        try:
            with open(self.inspector_path, encoding='utf-8') as f:
                inspector_data = json.load(f)

            clickable = []
            self._extract_clickable_recursive(inspector_data, clickable)
            Log.debug(f'解析到 {len(clickable)} 个可点击元素（bundleName匹配: {self.app_package}）')
            return clickable
        except FileNotFoundError:
            Log.warning(f'Inspector文件不存在: {self.inspector_path}')
            return []
        except json.JSONDecodeError as e:
            Log.error(f'解析Inspector JSON失败: {e}')
            return []
        except Exception as e:
            Log.error(f'解析可点击元素失败: {e}')
            return []

    def _extract_clickable_recursive(self, node: dict, clickable: list, path: str = '', parent_bundle: str = ''):
        """递归提取可点击元素"""
        if not isinstance(node, dict):
            return

        # Inspector JSON结构: {'attributes': {...}, 'children': [...]}
        attrs = node.get('attributes', {})

        node_type = attrs.get('type', '')
        node_id = attrs.get('id', '')
        node_text = attrs.get('text', '')
        clickable_attr = attrs.get('clickable', '') == 'true'  # 注意是字符串'true'
        bounds_str = attrs.get('bounds', '')
        bundle_name = attrs.get('bundleName', parent_bundle)

        current_path = f'{path}/{node_type}[{node_id}]' if path else f'{node_type}[{node_id}]'

        # 判断是否可点击（只信任clickable='true'的元素）
        if clickable_attr:
            # 检查bundleName是否匹配（如果指定了app_package）
            if self.app_package and bundle_name and bundle_name != self.app_package:
                # Log.debug(f'跳过非目标应用元素: {node_type}, bundleName={bundle_name}')
                pass
            else:
                # 解析bounds字符串: '[0,0][1216,2688]' -> {left:0, top:0, right:1216, bottom:2688}
                bounds = self._parse_bounds(bounds_str)
                if bounds and bounds.get('right', 0) > bounds.get('left', 0):
                    clickable.append(
                        {
                            'type': node_type,
                            'id': node_id,
                            'text': node_text,
                            'bounds': bounds,
                            'path': current_path,
                            'bundleName': bundle_name,
                        }
                    )

        # 递归处理子节点（传递bundleName）
        for child in node.get('children', []):
            self._extract_clickable_recursive(child, clickable, current_path, bundle_name)

    def _parse_bounds(self, bounds_str: str) -> dict:
        """
        解析bounds字符串
        输入: '[0,0][1216,2688]'
        输出: {'left': 0, 'top': 0, 'right': 1216, 'bottom': 2688}
        """
        try:
            match = re.match(r'\[(\d+),(\d+)\]\[(\d+),(\d+)\]', bounds_str)
            if match:
                return {
                    'left': int(match.group(1)),
                    'top': int(match.group(2)),
                    'right': int(match.group(3)),
                    'bottom': int(match.group(4)),
                }
        except Exception:
            pass
        return {}

    def _compute_hash(self) -> str:
        """基于element tree计算状态哈希"""
        try:
            with open(self.element_tree_path, encoding='utf-8') as f:
                tree_content = f.read()

            signature = self._extract_tree_signature(tree_content)
            Log.debug(f'signature is: {signature}')
            return hashlib.md5(signature.encode('utf-8')).hexdigest()
        except Exception:
            return hashlib.md5(str(self.step_id).encode()).hexdigest()

    def _extract_tree_signature(self, tree_content: str) -> str:
        """提取树结构签名(忽略动态内容)"""
        lines = tree_content.split('\n')
        signature_lines = []

        for line in lines:
            if '| ID:' in line:
                parts = line.split('| ID:')
                if len(parts) > 1:
                    id_part = parts[1].strip()
                    signature_lines.append(id_part)

        return '|'.join(signature_lines)


class StateManager:
    """UI状态管理器,负责状态去重和历史记录"""

    def __init__(self):
        self.visited_states = set()
        self.state_history = []
        self.action_history = []

    def add_state(self, ui_state: UIState) -> bool:
        """
        添加新状态

        Args:
            ui_state: UI状态对象

        Returns:
            是否为新状态(True=新状态, False=已访问)
        """
        state_hash = ui_state.state_hash

        if state_hash in self.visited_states:
            return False

        self.visited_states.add(state_hash)
        self.state_history.append(ui_state)
        return True

    def is_visited(self, ui_state: UIState) -> bool:
        """检查状态是否已访问"""
        return ui_state.state_hash in self.visited_states

    def record_action(self, action_type: str, target: Optional[dict] = None, result: str = 'success'):
        """
        记录执行的操作

        Args:
            action_type: 操作类型('click', 'scroll', 'back')
            target: 操作目标(元素信息)
            result: 执行结果
        """
        self.action_history.append(
            {'type': action_type, 'target': target, 'result': result, 'step': len(self.action_history) + 1}
        )

    def get_last_state(self) -> Optional[UIState]:
        """获取最后一个状态"""
        return self.state_history[-1] if self.state_history else None

    def get_unvisited_elements(self, ui_state: UIState) -> list:
        """获取当前状态中未访问过的可点击元素"""
        all_clickable = ui_state.clickable_elements
        clicked_elements = set()

        for action in self.action_history:
            if action['type'] == 'click' and action['target']:
                clicked_elements.add(self._get_element_id(ui_state, action['target']))

        unvisited = [elem for elem in all_clickable if self._get_element_id(ui_state, elem) not in clicked_elements]
        Log.debug(
            f'总可点击: {len(all_clickable)}, 已点击: {len(all_clickable) - len(unvisited)}, 未访问: {len(unvisited)}'
        )
        return unvisited

    @staticmethod
    def _get_element_id(ui_state: UIState, elem: dict) -> str:
        """生成元素的唯一标识符，基于path、text和bounds的组合"""
        path = elem.get('path', '')
        text = elem.get('text', '')
        bounds = elem.get('bounds', {})
        hash = ui_state.state_hash

        # 使用 hash + path + text + bounds 确保唯一性
        # 即使path和text相同，bounds（位置）也必然不同
        bounds_str = (
            f'{bounds.get("left", 0)},{bounds.get("top", 0)},{bounds.get("right", 0)},{bounds.get("bottom", 0)}'
        )
        return f'{hash}|{path}|{text}|{bounds_str}'

    def get_statistics(self) -> dict:
        """获取统计信息"""
        return {
            'total_states': len(self.state_history),
            'unique_states': len(self.visited_states),
            'total_actions': len(self.action_history),
            'click_count': sum(1 for a in self.action_history if a['type'] == 'click'),
            'scroll_count': sum(1 for a in self.action_history if a['type'] == 'scroll'),
            'back_count': sum(1 for a in self.action_history if a['type'] == 'back'),
        }
