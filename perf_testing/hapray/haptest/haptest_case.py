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
import logging
import os
from typing import Optional

from hapray.core.perf_testcase import PerfTestCase
from hapray.haptest.state_manager import StateManager, UIState
from hapray.haptest.strategy import ExplorationStrategy

Log = logging.getLogger('HapTest')


class NoOpCaptureUI:
    """空操作的UI捕获类,用于避免execute_performance_step中的重复UI捕获"""
    
    def __init__(self, driver):
        self.driver = driver
    
    def capture_ui(self, step_id, report_path, stage):
        """空操作,不执行任何UI捕获"""
        pass


def setup_haptest_logger(report_path: str, app_name: str):
    """
    为HapTest设置独立的日志文件
    
    Args:
        report_path: 报告路径
        app_name: 应用名称
    """
    # 创建日志目录
    log_dir = os.path.join(report_path, 'logs')
    os.makedirs(log_dir, exist_ok=True)
    
    # HapTest日志文件
    haptest_log_file = os.path.join(log_dir, 'haptest.log')
    
    # 创建文件处理器
    file_handler = logging.FileHandler(haptest_log_file, mode='w', encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    
    # 创建格式化器
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )
    file_handler.setFormatter(formatter)
    
    # 为HapTest相关的logger添加文件处理器
    haptest_logger = logging.getLogger('HapTest')
    haptest_logger.addHandler(file_handler)
    haptest_logger.setLevel(logging.DEBUG)

    # 只在控制台显示INFO及以上级别

    Log.info(f'HapTest日志已保存至: {haptest_log_file}')
    Log.info(f'应用: {app_name}')
    Log.info('='*60)


class HapTest(PerfTestCase):
    """
    自动化测试工具,基于PerfTestCase实现策略驱动的UI探索

    核心特性:
    1. 自动探索应用UI
    2. 采集每步操作的性能数据
    3. 生成完整的执行路径和性能报告
    """

    def __init__(self, tag: str, configs, app_package: str, app_name: str, ability_name: Optional[str] = None, strategy_type: str = 'depth_first', max_steps: int = 50):
        """
        初始化HapTest

        Args:
            tag: 测试标识
            configs: 测试配置
            app_package: 应用包名
            app_name: 应用名称
            ability_name: 主ability名称(可选,不指定则自动检测)
            strategy_type: 探索策略类型('depth_first', 'breadth_first', 'random')
            max_steps: 最大探索步数
        """
        self.TAG = tag
        super().__init__(tag, configs)
        self._app_package = app_package
        self._app_name = app_name
        self._ability_name = ability_name
        self.max_steps = max_steps

        self.state_mgr = StateManager()
        self.strategy = ExplorationStrategy(strategy_type)
        self.current_step = 0

        # 保存原始的UI捕获handler,用于手动捕获
        self._real_capture_ui_handler = self.capture_ui_handler
        # 替换为空操作handler,避免execute_performance_step中的重复捕获
        # self.capture_ui_handler = NoOpCaptureUI(self.driver)

        # 设置独立的日志文件
        setup_haptest_logger(self.report_path, app_name)

    @property
    def app_package(self) -> str:
        return self._app_package

    @property
    def app_name(self) -> str:
        return self._app_name

    def setup(self):
        """HapTest setup - 增强错误处理"""
        Log.info('HapTest setup')
        
        # 尝试获取bundle信息,如果失败则使用默认值
        try:
            from hypium.uidriver.ohos.app_manager import get_bundle_info
            self.bundle_info = get_bundle_info(self.driver, self.app_package)
            self.module_name = self.bundle_info.get('entryModuleName')
            Log.info(f'Bundle info loaded: module_name={self.module_name}')
        except Exception as e:
            Log.debug(f'Failed to get bundle info: {e}')
            Log.debug('Using default values for bundle_info and module_name')
            self.bundle_info = {'entryModuleName': 'entry'}
            self.module_name = 'entry'
        
        
        
        # 创建必要的目录
        os.makedirs(os.path.join(self.report_path, 'hiperf'), exist_ok=True)
        os.makedirs(os.path.join(self.report_path, 'htrace'), exist_ok=True)
        
        # 准备测试环境
        self.stop_app()
        self.driver.wake_up_display()
        self.driver.swipe_to_home()

    def process(self):
        """主测试流程"""
        Log.info(f'开始HapTest自动化测试: {self.app_name}')
        Log.info(f'策略: {self.strategy.strategy_type}, 最大步数: {self.max_steps}')
        Log.info('='*60)

        self.start_app(page_name=self._ability_name)
        self.driver.wait(3)

        while self.current_step < self.max_steps:
            self.current_step += 1
            Log.info(f'\n{"="*60}')
            Log.info(f'Step {self.current_step}/{self.max_steps}')
            Log.info(f'{"="*60}')

            # 先执行一次UI采集,获取当前状态
            ui_state = self._execute_ui_capture()

            # 添加状态到管理器
            is_new_state = self.state_mgr.add_state(ui_state)
            Log.info(f'UI状态: {"新状态" if is_new_state else "已访问"}')
            Log.info(f'当前应用: {ui_state.current_bundle_name or "未知"}')
            Log.info(f'目标应用: {ui_state.app_package}')
            Log.info(f'在目标应用内: {"是" if ui_state.is_in_target_app() else "否"}')
            Log.info(f'可点击元素数: {len(ui_state.clickable_elements)}')
            
            # 获取未访问的元素
            unvisited = self.state_mgr.get_unvisited_elements(ui_state)
            Log.info(f'未访问元素数: {len(unvisited)}')
            if unvisited:
                # 只显示前3个元素
                examples = [(e.get("text") or e.get("type") or e.get("id","unknown"))[:20]  for e in unvisited[:3]]
                Log.debug(f'未访问元素示例: {examples}')

            # 决策下一步操作
            action_type, target = self.strategy.decide_next_action(ui_state, self.state_mgr)
            
            if action_type == 'stop':
                Log.info('探索完成,停止测试')
                break
                
            # 格式化操作信息
            action_info = self._format_action_info(action_type, target)
            Log.info(f'决策: {action_info}')

            # 执行操作并采集性能数据
            self._execute_action_with_perf(action_type, target)

        Log.info('\n' + '='*60)
        Log.info('HapTest测试完成')
        Log.info('='*60)
        self._print_summary()

    def _execute_ui_capture(self) -> UIState:
        """
        执行UI数据采集,返回UI状态
        这个方法会立即采集当前屏幕的UI数据
        """
        step_id = self.current_step
        ui_dir = os.path.join(self.report_path, 'ui', f'step{step_id}')
        os.makedirs(ui_dir, exist_ok=True)

        # 立即采集UI数据(只采集一次作为当前状态,使用真实的handler)
        self._real_capture_ui_handler.capture_ui(step_id, self.report_path, 'current')

        # 从element_tree中提取当前bundleName
        element_tree_path = os.path.join(ui_dir, 'element_tree_current_1.txt')
        current_bundle_name = self._extract_bundle_name(element_tree_path)

        # 创建UI状态对象
        return UIState(
            step_id=step_id,
            screenshot_path=os.path.join(ui_dir, 'screenshot_current_1.png'),
            element_tree_path=element_tree_path,
            inspector_path=os.path.join(ui_dir, 'inspector_current.json'),
            app_package=self.app_package,
            current_bundle_name=current_bundle_name,
        )

    def _extract_bundle_name(self, element_tree_path: str) -> Optional[str]:
        """从element_tree文件中提取bundleName"""
        try:
            with open(element_tree_path, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.startswith('bundleName:'):
                        return line.split(':', 1)[1].strip()
        except Exception as e:
            Log.warning(f'Failed to extract bundleName: {e}')
        return None

    def _format_action_info(self, action_type: str, target: Optional[dict]) -> str:
        """格式化操作信息用于日志"""
        if action_type == 'click' and target:

            target_str = json.dumps(target, indent=2, ensure_ascii=False)
            Log.debug(f"完整target信息:\n{target_str}")


            text = target.get('text', '')
            elem_type = target.get('type', '')
            return f'点击 {elem_type} "{text[:20]}"' if text else f'点击 {elem_type}'
        elif action_type == 'scroll':
            direction = target.get('direction', 'up') if target else 'up'
            return f'滑动 {direction}'
        elif action_type == 'back':
            return '返回'
        else:
            return action_type

    def _execute_action_with_perf(self, action_type: str, target: Optional[dict]):
        """
        执行操作并采集性能数据

        Args:
            action_type: 操作类型('click', 'scroll', 'back')
            target: 操作目标
        """
        action_desc = self._format_action_description(action_type, target)

        def do_action():
            try:
                if action_type == 'click':
                    self._do_click(target)
                elif action_type == 'scroll':
                    self._do_scroll(target)
                elif action_type == 'back':
                    self._do_back()
                else:
                    Log.warning(f'未知操作类型: {action_type}')

                self.state_mgr.record_action(action_type, target, 'success')
            except Exception as e:
                Log.error(f'执行操作失败: {e}')
                self.state_mgr.record_action(action_type, target, 'failed')

        self.execute_performance_step(action_desc, duration=5, action=do_action)

    def _do_click(self, target: dict):
        """执行点击操作"""
        if not target:
            Log.warning('点击目标为空')
            return

        text = target.get('text', '')
        elem_id = target.get('id', '')

        if text:
            success = self.touch_by_text(text, wait_seconds=1)
            if not success:
                Log.warning(f'点击文本失败: {text}, 尝试使用坐标')
                self._click_by_bounds(target)
        elif elem_id:
            success = self.touch_by_id(elem_id, wait_seconds=1)
            if not success:
                self._click_by_bounds(target)
        else:
            self._click_by_bounds(target)

    def _click_by_bounds(self, target: dict):
        """通过坐标点击"""
        bounds = target.get('bounds', {})
        if not bounds:
            Log.warning('元素bounds为空，无法点击')
            return
        
        left = bounds.get('left')
        top = bounds.get('top')
        right = bounds.get('right')
        bottom = bounds.get('bottom')
        
        if None in (left, top, right, bottom):
            Log.warning(f'元素bounds包含None值: {bounds}')
            return
        
        if left >= right or top >= bottom:
            Log.warning(f'元素bounds无效: {bounds}')
            return
        
        x = (left + right) // 2
        y = (top + bottom) // 2
        self.touch_by_coordinates(x, y, wait_seconds=1)

    def _do_scroll(self, target: Optional[dict]):
        """执行滑动操作"""
        direction = target.get('direction', 'up') if target else 'up'

        if direction == 'up':
            self.swipes_up(swip_num=1, sleep=1)
        elif direction == 'down':
            self.swipes_down(swip_num=1, sleep=1)
        elif direction == 'left':
            self.swipes_left(swip_num=1, sleep=1)
        elif direction == 'right':
            self.swipes_right(swip_num=1, sleep=1)

    def _do_back(self):
        """执行返回操作"""
        self.swipe_to_back(sleep=1)

    def _format_action_description(self, action_type: str, target: Optional[dict]) -> str:
        """格式化操作描述"""
        if action_type == 'click' and target:
            text = target.get('text', '')
            elem_type = target.get('type', '')
            return f'点击_{elem_type}_{text}' if text else f'点击_{elem_type}'
        elif action_type == 'scroll':
            direction = target.get('direction', 'up') if target else 'up'
            return f'滑动_{direction}'
        elif action_type == 'back':
            return '返回'
        else:
            return action_type

    def _print_summary(self):
        """打印测试摘要"""
        stats = self.state_mgr.get_statistics()

        Log.info('\n' + '=' * 60)
        Log.info('HapTest 测试摘要')
        Log.info('=' * 60)
        Log.info(f'应用: {self.app_name} ({self.app_package})')
        Log.info(f'策略: {self.strategy.strategy_type}')
        Log.info(f'总步数: {stats["total_actions"]}')
        Log.info(f'唯一状态数: {stats["unique_states"]}')
        Log.info(f'点击次数: {stats["click_count"]}')
        Log.info(f'滑动次数: {stats["scroll_count"]}')
        Log.info(f'返回次数: {stats["back_count"]}')
        Log.info(f'报告路径: {self.report_path}')
        Log.info('=' * 60)
