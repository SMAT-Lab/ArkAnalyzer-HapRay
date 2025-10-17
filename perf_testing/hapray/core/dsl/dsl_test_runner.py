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
import os
import time
from dataclasses import dataclass, field
from importlib.resources import files
from typing import Any, Optional, Union

import yaml
from hypium import BY
from jsonschema import validate
from xdevice.__main__ import main_process

from hapray.core.perf_testcase import PerfTestCase


@dataclass
class ComponentSelector:
    """表示 UI 组件的选择器"""

    text: Optional[str] = None
    key: Optional[str] = None
    type: Optional[str] = None
    xpath: Optional[str] = None
    relations: list[dict] = field(default_factory=list)
    pos: Optional[list[float]] = None


@dataclass
class UIEvent:
    """表示 UI 事件的基础类"""

    event_type: str


@dataclass
class TouchEvent(UIEvent):
    """表示触摸事件"""

    target: ComponentSelector
    mode: str = 'normal'
    scroll_target: Optional[ComponentSelector] = None
    wait_time: float = 0.1


@dataclass
class SwipeEvent(UIEvent):
    """表示滑动事件"""

    direction: str
    distance: int = 60
    area: Optional[ComponentSelector] = None
    side: Optional[str] = None
    start_point: Optional[list[float]] = None
    swipe_time: float = 0.3


@dataclass
class InputEvent(UIEvent):
    """表示输入事件"""

    component: ComponentSelector
    text: str


@dataclass
class WaitEvent(UIEvent):
    """表示等待事件"""

    duration: int


@dataclass
class LoopEvent(UIEvent):
    """表示循环事件"""

    count: int
    events: list['UIEvent']


@dataclass
class KeyEvent(UIEvent):
    """表示按键事件"""

    key_code: Union[str, int]
    key_code2: Optional[Union[str, int]] = None
    mode: str = 'normal'


@dataclass
class StartAppEvent(UIEvent):
    """表示启动应用事件"""

    package_name: Optional[str] = None
    page_name: Optional[str] = None
    params: Optional[str] = None
    wait_time: float = 1.0


@dataclass
class StopAppEvent(UIEvent):
    """表示停止应用事件"""

    package_name: Optional[str] = None
    wait_time: float = 0.5


@dataclass
class TestStep:
    """表示测试步骤"""

    name: str
    events: list[UIEvent]
    performance: Optional[dict] = None


@dataclass
class TestCase:
    """表示测试用例"""

    steps: list[TestStep]
    setup: list[UIEvent] = field(default_factory=list)
    cleanup: list[UIEvent] = field(default_factory=list)


@dataclass
class TestConfig:
    """表示测试配置"""

    app_package: str
    app_name: str
    scene_name: str
    source_screen: list[int]
    test_case: TestCase


class DSLTestRunner(PerfTestCase):
    schema_path = files('hapray.core.dsl').joinpath('dsl_schema.yaml')

    def __init__(self, controllers):
        self.config_data = self._load_config(controllers.get('testargs', {'dsl': ''}).get('dsl')[0])
        self.config = self._parse_config()
        # pylint: disable=C0103
        self.TAG = self.config.scene_name
        super().__init__(self.TAG, controllers)
        self.source_screen_width, self.source_screen_height = self.config.source_screen
        self._app_package = self.config.app_package
        self._app_name = self.config.app_name

    @staticmethod
    def run_testcase(dsl_file: str, output: str, device_id: str):
        device = f'-sn {device_id}' if device_id else ''
        command = f'run -l dsl_test_runner {device} -tcpath {os.path.dirname(__file__)} -rp {output} -ta dsl:{dsl_file}'
        main_process(command)

    @property
    def app_package(self) -> str:
        return self._app_package

    @property
    def steps(self) -> list:
        return self._steps

    @property
    def app_name(self) -> str:
        return self._app_name

    def process(self):
        for step in self.config.test_case.steps:
            if step.performance is None:
                self._process_step(step)
            else:
                self.execute_performance_step(step.name, step.performance.get('duration'), self._process_step, step)

    def _process_step(self, step: TestStep):
        logging.info('Running test case: %s', step.name)
        for event in step.events:
            self._execute_event(event)
        logging.info('Completed test case: %s', step.name)

    def _load_config(self, path: str) -> dict[str, Any]:
        """加载YAML配置文件"""
        if not os.path.exists(path) or not os.path.exists(self.schema_path):
            raise FileNotFoundError(path)
        with open(path, encoding='UTF-8') as f:
            config = yaml.safe_load(f)

        # 加载Schema
        with open(self.schema_path, encoding='UTF-8') as f:
            schema = yaml.safe_load(f)

        validate(instance=config, schema=schema)
        return config

    def _parse_component_selector(self, selector_data: dict) -> ComponentSelector:
        """解析组件选择器"""
        selector = ComponentSelector()

        # 解析基本属性
        if 'text' in selector_data:
            selector.text = selector_data['text']
        if 'key' in selector_data:
            selector.key = selector_data['key']
        if 'type' in selector_data:
            selector.type = selector_data['type']
        if 'xpath' in selector_data:
            selector.xpath = selector_data['xpath']
        if 'pos' in selector_data:
            selector.pos = selector_data['pos']

        # 解析关系属性
        if 'relations' in selector_data:
            for rel_data in selector_data['relations']:
                relation = {
                    'relation': rel_data['relation'],
                    'target': self._parse_component_selector(rel_data['target']),
                }
                selector.relations.append(relation)

        return selector

    def _parse_event(self, event_data: dict) -> UIEvent:
        """解析单个事件"""
        event_type = event_data['type']
        handlers = {
            'touch': self._handle_touch_event,
            'swipe': self._handle_swipe_event,
            'input_text': self._handle_input_event,
            'wait': self._handle_wait_event,
            'loop': self._handle_loop_event,
            'press_key': self._handle_key_event,
            'start_app': self._handle_start_app_event,
            'stop_app': self._handle_stop_app_event,
        }

        handlers = {
            'touch': self._handle_touch_event,
            'swipe': self._handle_swipe_event,
            'input_text': self._handle_input_event,
            'wait': self._handle_wait_event,
            'loop': self._handle_loop_event,
            'press_key': self._handle_key_event,
            'start_app': self._handle_start_app_event,
            'stop_app': self._handle_stop_app_event,
        }

        handler = handlers.get(event_type)
        if handler:
            return handler(event_data)

        raise ValueError(f'未知的事件类型: {event_type}')

    def _handle_touch_event(self, event_data: dict) -> TouchEvent:
        return TouchEvent(
            event_type='touch',
            target=self._parse_component_selector(event_data['target']),
            mode=event_data.get('mode', 'normal'),
            scroll_target=self._parse_component_selector(event_data['scroll_target'])
            if 'scroll_target' in event_data
            else None,
            wait_time=event_data.get('wait_time', 0.1),
        )

    def _handle_swipe_event(self, event_data: dict) -> SwipeEvent:
        return SwipeEvent(
            event_type='swipe',
            direction=event_data['direction'],
            distance=event_data.get('distance', 60),
            area=self._parse_component_selector(event_data['area']) if 'area' in event_data else None,
            side=event_data.get('side'),
            start_point=event_data.get('start_point'),
            swipe_time=event_data.get('swipe_time', 0.3),
        )

    def _handle_input_event(self, event_data: dict) -> InputEvent:
        return InputEvent(
            event_type='input_text',
            component=self._parse_component_selector(event_data['component']),
            text=event_data['text'],
        )

    def _handle_wait_event(self, event_data: dict) -> WaitEvent:
        return WaitEvent(
            event_type='wait',
            duration=event_data['duration'],
        )

    def _handle_loop_event(self, event_data: dict) -> LoopEvent:
        return LoopEvent(
            event_type='loop',
            count=event_data['count'],
            events=[self._parse_event(e) for e in event_data['events']],
        )

    def _handle_key_event(self, event_data: dict) -> KeyEvent:
        return KeyEvent(
            event_type='press_key',
            key_code=event_data['key_code'],
            key_code2=event_data.get('key_code2'),
            mode=event_data.get('mode', 'normal'),
        )

    def _handle_start_app_event(self, event_data: dict) -> StartAppEvent:
        return StartAppEvent(
            event_type='start_app',
            package_name=event_data.get('package_name'),
            page_name=event_data.get('page_name'),
            params=event_data.get('params'),
            wait_time=event_data.get('wait_time', 1.0),
        )

    def _handle_stop_app_event(self, event_data: dict) -> StopAppEvent:
        return StopAppEvent(
            event_type='stop_app',
            package_name=event_data.get('package_name'),
            wait_time=event_data.get('wait_time', 0.5),
        )

    def _parse_step(self, step_data: dict) -> TestStep:
        """解析测试步骤"""
        return TestStep(
            name=step_data['name'],
            events=[self._parse_event(e) for e in step_data['events']],
            performance=step_data.get('performance'),
        )

    def _parse_config(self) -> TestConfig:
        """解析整个配置"""
        config_data = self.config_data['config']
        test_case_data = self.config_data['test_case']

        test_case = TestCase(
            setup=[self._parse_event(e) for e in test_case_data.get('setup', [])],
            cleanup=[self._parse_event(e) for e in test_case_data.get('cleanup', [])],
            steps=[self._parse_step(s) for s in test_case_data['steps']],
        )

        return TestConfig(
            app_package=config_data['app_package'],
            app_name=config_data['app_name'],
            scene_name=config_data['scene_name'],
            source_screen=config_data['source_screen'],
            test_case=test_case,
        )

    def _execute_event(self, event: UIEvent):
        try:
            if isinstance(event, TouchEvent):
                self._process_touch(event)

            elif isinstance(event, SwipeEvent):
                self._process_swipe(event)

            elif isinstance(event, InputEvent):
                self._process_input_text(event)

            elif isinstance(event, WaitEvent):
                self._process_wait(event)

            elif isinstance(event, LoopEvent):
                self._process_loop(event)

            elif isinstance(event, KeyEvent):
                self._process_press_key(event)

            elif isinstance(event, StartAppEvent):
                self.start_app(event.package_name, event.page_name, event.params, event.wait_time)

            elif isinstance(event, StopAppEvent):
                self.stop_app(event.package_name, event.wait_time)

            else:
                logging.warning('Unknown step type: %s', event.event_type)

        except Exception as e:
            logging.error('Failed to execute step: %s - Error: %s', event.event_type, str(e))
            raise

    @staticmethod
    def _process_wait(event: WaitEvent):
        logging.info('Waiting for %dms', event.duration)
        time.sleep(event.duration)

    def _process_press_key(self, event: KeyEvent):
        self.driver.press_key(event.key_code, event.key_code2, event.mode)

    def _process_loop(self, event: LoopEvent):
        for i in range(event.count):
            logging.info('Loop iteration %d/%d', i + 1, event.count)
            for sub_event in event.events:
                self._execute_event(sub_event)

    def _process_touch(self, event: TouchEvent):
        """处理触摸事件"""
        # 转换选择器为驱动可接受的格式
        target = self._convert_selector(event.target)
        scroll_target = self._convert_selector(event.scroll_target) if event.scroll_target else None
        # 执行触摸操作
        self.driver.touch(target=target, mode=event.mode, scroll_target=scroll_target, wait_time=event.wait_time)

    def _process_swipe(self, event: SwipeEvent):
        """处理滑动事件"""
        # 转换区域选择器
        area = self._convert_selector(event.area) if event.area else None

        # 处理起始点坐标转换
        start_point = None
        if event.start_point:
            if all(0 <= coord <= 1 for coord in event.start_point):
                # 比例坐标转绝对坐标
                start_point = (
                    event.start_point[0] * self.source_screen_width,
                    event.start_point[1] * self.source_screen_height,
                )
            else:
                start_point = tuple(event.start_point)

        # 执行滑动操作
        self.driver.swipe(
            direction=event.direction,
            distance=event.distance,
            area=area,
            side=event.side,
            start_point=start_point,
            swipe_time=event.swipe_time,
        )
        logging.info('Swiped: %s direction, distance=%f', event.direction, event.distance)

    def _process_input_text(self, event: InputEvent):
        """处理文本输入事件"""
        # 转换组件选择器
        component = self._convert_selector(event.component)

        # 执行文本输入
        self.driver.input_text(component=component, text=event.text)
        logging.info('Input text: %s', event.text)

    def _convert_selector(self, selector: ComponentSelector):
        """
        将 ComponentSelector 转换为驱动可接受的格式
        返回 ISelector 对象或坐标元组
        """
        # 如果选择器包含坐标，直接返回坐标元组
        if selector.pos:
            if all(0 <= coord <= 1 for coord in selector.pos):
                return (selector.pos[0] * self.source_screen_width, selector.pos[1] * self.source_screen_height)
            return self.convert_coordinate(selector.pos[0], selector.pos[1])

        # 根据属性构建选择器
        if selector.text:
            selector_obj = BY.text(selector.text)
        elif selector.key:
            selector_obj = BY.key(selector.key)
        elif selector.type:
            selector_obj = BY.type(selector.type)
        elif selector.xpath:
            selector_obj = BY.xpath(selector.xpath)
        else:
            raise ValueError('Selector must have at least one property')

        # 添加关系约束
        for relation in selector.relations:
            rel_type = relation['relation']
            target = self._convert_selector(relation['target'])

            if rel_type == 'isAfter':
                selector_obj = selector_obj.isAfter(target)
            elif rel_type == 'isBefore':
                selector_obj = selector_obj.isBefore(target)
            elif rel_type == 'within':
                selector_obj = selector_obj.within(target)
            elif rel_type == 'inWindow':
                selector_obj = selector_obj.inWindow(target)
            else:
                raise ValueError(f'Unsupported relation type: {rel_type}')

        return selector_obj


# pylint: disable=C0103
dsl_test_runner = DSLTestRunner
