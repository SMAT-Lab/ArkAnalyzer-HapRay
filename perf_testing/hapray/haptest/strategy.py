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
import random
from abc import ABC, abstractmethod
from typing import Optional, Tuple

from hapray.haptest.state_manager import StateManager, UIState

Log = logging.getLogger('HapTest.Strategy')


class BaseStrategy(ABC):
    """探索策略基类"""

    @abstractmethod
    def decide_next_action(self, ui_state: UIState, state_mgr: StateManager) -> Tuple[str, Optional[dict]]:
        """
        决策下一步操作

        Args:
            ui_state: 当前UI状态
            state_mgr: 状态管理器

        Returns:
            (action_type, target) 元组
            - action_type: 'click', 'scroll', 'back', 'stop'
            - target: 操作目标(对于click是元素信息,其他为None或方向)
        """


class DepthFirstStrategy(BaseStrategy):
    """深度优先探索策略"""

    def __init__(self, max_back_count: int = 3):
        self.max_back_count = max_back_count
        self.back_count = 0

    def decide_next_action(self, ui_state: UIState, state_mgr: StateManager) -> Tuple[str, Optional[dict]]:
        """
        深度优先策略:
        1. 优先点击未访问的可点击元素
        2. 若无可点击元素,尝试滑动
        3. 若无法滑动,返回上一层
        4. 达到最大返回次数则停止
        """
        if not ui_state.is_in_target_app():
            Log.info('检测到退出应用,停止探索')
            return ('stop', None)

        unvisited_elements = state_mgr.get_unvisited_elements(ui_state)
        
        Log.debug(f'[DepthFirst] 未访问元素数: {len(unvisited_elements)}, 连续返回次数: {self.back_count}')

        if unvisited_elements:
            self.back_count = 0
            target = unvisited_elements[0]
            Log.debug(f'[DepthFirst] 决策: 点击 {target.get("type", "?")} "{target.get("text", "")[:20]}"')
            return ('click', target)

        if self._can_scroll(ui_state):
            Log.debug('[DepthFirst] 决策: 滑动探索')
            return ('scroll', {'direction': 'up'})

        if self.back_count < self.max_back_count:
            self.back_count += 1
            Log.debug(f'[DepthFirst] 决策: 返回 ({self.back_count}/{self.max_back_count})')
            return ('back', None)

        Log.info('[DepthFirst] 达到最大返回次数,停止探索')
        return ('stop', None)

    def _can_scroll(self, ui_state: UIState) -> bool:
        """判断是否可以滑动(简单实现,可扩展)"""
        clickable = ui_state.clickable_elements
        return len(clickable) > 5


class BreadthFirstStrategy(BaseStrategy):
    """广度优先探索策略"""

    def __init__(self, scroll_prob: float = 0.2):
        self.scroll_prob = scroll_prob
        self.pending_states = []

    def decide_next_action(self, ui_state: UIState, state_mgr: StateManager) -> Tuple[str, Optional[dict]]:
        """
        广度优先策略:
        1. 收集当前页面所有可点击元素
        2. 随机选择未访问的元素点击
        3. 周期性回退到上层页面
        """
        if not ui_state.is_in_target_app():
            Log.info('检测到退出应用,停止探索')
            return ('stop', None)
        unvisited_elements = state_mgr.get_unvisited_elements(ui_state)

        if not unvisited_elements:
            if state_mgr.action_history:
                return ('back', None)
            return ('stop', None)

        if random.random() < self.scroll_prob:
            return ('scroll', {'direction': random.choice(['up', 'down'])})

        target = random.choice(unvisited_elements)
        return ('click', target)


class RandomStrategy(BaseStrategy):
    """随机探索策略"""

    def __init__(self, max_steps: int = 100):
        self.max_steps = max_steps

    def decide_next_action(self, ui_state: UIState, state_mgr: StateManager) -> Tuple[str, Optional[dict]]:
        """
        随机策略:
        1. 随机选择操作类型
        2. 达到最大步数后停止
        """
        
        if not ui_state.is_in_target_app(): 
            Log.info('检测到退出应用,停止探索')
            return ('stop', None)

        if len(state_mgr.action_history) >= self.max_steps:
            return ('stop', None)

        # action_type = random.choice(['click', 'click', 'scroll', 'back'])

        # 动态权重
        current_step = len(state_mgr.action_history)
        if current_step < 5:  # 前5步禁止back
            action_type = random.choice(['click', 'click', 'scroll'])
        else:
            # 随着步数增加，逐渐增加back的概率
            back_weight = min(0.2, current_step * 0.02)  # 最多20%
            action_type = random.choices(
                ['click', 'scroll', 'back'],
                weights=[0.7 - back_weight/2, 0.3 - back_weight/2, back_weight],
                k=1
            )[0]

        if action_type == 'click':
            clickable = ui_state.clickable_elements
            if clickable:
                return ('click', random.choice(clickable))
            # return ('scroll', {'direction': 'up'})
            return ('stop',None)

        if action_type == 'scroll':
            return ('scroll', {'direction': random.choice(['up', 'down'])})

        return ('back', None)


class ExplorationStrategy:
    """组合策略引擎,可动态切换策略"""

    def __init__(self, strategy_type: str = 'depth_first'):
        """
        Args:
            strategy_type: 策略类型
                - 'depth_first': 深度优先
                - 'breadth_first': 广度优先
                - 'random': 随机探索
        """
        self.strategy_type = strategy_type
        self.strategy = self._create_strategy(strategy_type)

    def _create_strategy(self, strategy_type: str) -> BaseStrategy:
        """创建策略实例"""
        strategies = {
            'depth_first': DepthFirstStrategy(max_back_count=5),
            'breadth_first': BreadthFirstStrategy(scroll_prob=0.2),
            'random': RandomStrategy(max_steps=100),
        }

        if strategy_type not in strategies:
            raise ValueError(f'Unknown strategy type: {strategy_type}')

        return strategies[strategy_type]

    def decide_next_action(self, ui_state: UIState, state_mgr: StateManager) -> Tuple[str, Optional[dict]]:
        """
        决策下一步操作

        Args:
            ui_state: 当前UI状态
            state_mgr: 状态管理器

        Returns:
            (action_type, target) 元组
        """
        return self.strategy.decide_next_action(ui_state, state_mgr)

    def switch_strategy(self, new_strategy_type: str):
        """动态切换策略"""
        self.strategy_type = new_strategy_type
        self.strategy = self._create_strategy(new_strategy_type)
