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
import re
from pathlib import Path

from hapray.core.common.action_return import ActionExecuteReturn


# Mapping from Agent action names to HapRay script descriptions
ACTION_DESCRIPTIONS = {
    'Launch': '启动应用',
    'Tap': '点击坐标',
    'Double Tap': '双击坐标',
    'Long Press': '长按坐标',
    'Swipe': '滑动',
    'Type': '输入文本',
    'Type_Name': '输入文本',
    'Back': '返回',
    'Home': '回到桌面',
    'Wait': '等待',
}

# Common known Chinese → pinyin mappings
KNOWN_PINYIN = {
    '微信': 'wechat',
    'QQ': 'qq',
    '微博': 'weibo',
    '淘宝': 'taobao',
    '京东': 'jingdong',
    '拼多多': 'pdd',
    '小红书': 'xhs',
    '知乎': 'zhihu',
    '美团': 'meituan',
    '美团外卖': 'meituan_waimai',
    '百度': 'baidu',
    '快手': 'kuaishou',
    '抖音': 'douyin',
    '高德地图': 'amap',
    '百度地图': 'baidumap',
    '网易云音乐': 'netease_music',
    '哔哩哔哩': 'bilibili',
    '今日头条': 'jinritoutiao',
    '携程': 'ctrip',
    '天猫': 'tmall',
    '饿了么': 'eleme',
    '滴滴': 'didi',
    '花呗': 'huabei',
    '闲鱼': 'xianyu',
    '钉钉': 'dingtalk',
    '企业微信': 'wxwork',
    '西瓜视频': 'xigua',
    '百度极速版': 'baidu_jisu',
}


def _py_str(s: str) -> str:
    """Safely escape a string for embedding in Python code literals."""
    return repr(s)


def app_name_to_pinyin_id(app_name: str) -> str:
    """Convert Chinese app name to a simple pinyin-like identifier."""
    if app_name in KNOWN_PINYIN:
        return KNOWN_PINYIN[app_name]
    return re.sub(r'[^a-zA-Z0-9]', '', app_name).lower() or 'app'


def convert_coordinates(element: list, src_w: int, src_h: int) -> tuple[int, int]:
    """Convert relative coordinates (0-1000) to source screen pixels."""
    x = int(element[0] / 1000 * src_w)
    y = int(element[1] / 1000 * src_h)
    return x, y


def _swipe_direction_from_step(step: dict) -> str:
    """Determine swipe direction from a single step (relative coords 0-1000)."""
    params = step['params']
    start = params.get('start')
    end = params.get('end')
    if start and end and len(start) >= 2 and len(end) >= 2:
        dy = end[1] - start[1]
        dx = end[0] - start[0]
        if dy < -100:
            return '向上'
        elif dy > 100:
            return '向下'
        elif dx < -100:
            return '向左'
        elif dx > 100:
            return '向右'
    return '自定义'


def _describe_single_step(step: dict, app_name: str, index: int) -> str:
    """Generate a human-readable description for a single step."""
    action = step['action']
    action_cn = ACTION_DESCRIPTIONS.get(action, action)

    if action == 'Type':
        text = step['params'].get('text', '')
        short = text[:10] + '...' if len(text) > 10 else text
        return f'step{index}-{app_name}-{action_cn}-{short}'
    elif action == 'Swipe':
        direction = _swipe_direction_from_step(step)
        return f'step{index}-{app_name}-{action_cn}-{direction}'
    else:
        return f'step{index}-{app_name}-{action_cn}'


def _action_to_code(step: dict, src_w: int, src_h: int, indent: int = 12) -> str:
    """Convert a single step action to HapRay Python code line."""
    prefix = ' ' * indent
    action = step['action']
    params = step['params']

    if action == 'Launch':
        app = params.get('app', '')
        return f'{prefix}# 启动应用: {app}（已在前置准备中完成）'

    elif action in ('Tap',):
        element = params.get('element')
        if element and len(element) >= 2:
            x, y = convert_coordinates(element, src_w, src_h)
            return f'{prefix}self.touch_by_coordinates({x}, {y}, 2)'
        return f'{prefix}# {action} (no coordinates)'

    elif action == 'Double Tap':
        element = params.get('element')
        if element and len(element) >= 2:
            x, y = convert_coordinates(element, src_w, src_h)
            return f'{prefix}self.driver.double_click(BY.coords({x}, {y}))'
        return f'{prefix}# {action} (no coordinates)'

    elif action == 'Long Press':
        element = params.get('element')
        if element and len(element) >= 2:
            x, y = convert_coordinates(element, src_w, src_h)
            return f'{prefix}self.driver.long_click(BY.coords({x}, {y}))'
        return f'{prefix}# {action} (no coordinates)'

    elif action == 'Swipe':
        start = params.get('start')
        end = params.get('end')
        if start and end and len(start) >= 2 and len(end) >= 2:
            dy = end[1] - start[1]
            dx = end[0] - start[0]
            if dy < -100:
                return f'{prefix}self.swipes_up(1, 1)'
            elif dy > 100:
                return f'{prefix}self.swipes_down(1, 1)'
            elif dx < -100:
                return f'{prefix}self.swipes_left(1, 1)'
            elif dx > 100:
                return f'{prefix}self.swipes_right(1, 1)'
            else:
                sx, sy = convert_coordinates(start, src_w, src_h)
                ex, ey = convert_coordinates(end, src_w, src_h)
                return f'{prefix}self.driver.drag(BY.coords({sx}, {sy}), BY.coords({ex}, {ey}))'
        return f'{prefix}# Swipe (no coordinates)'

    elif action == 'Type':
        text = params.get('text', '')
        return f'{prefix}self.driver.input_text(BY.type(\'TextInput\'), {_py_str(text)})'

    elif action == 'Back':
        return f'{prefix}self.swipe_to_back(1)'

    elif action == 'Home':
        return f'{prefix}self.swipe_to_home()'

    elif action == 'Wait':
        duration = params.get('duration', '1 seconds')
        match = re.match(r'([\d.]+)', str(duration))
        seconds = match.group(1) if match else '1'
        return f'{prefix}self.driver.wait({seconds})'

    else:
        return f'{prefix}# Unsupported action: {action}'


def _get_auto_testcases_dir() -> Path:
    """Return the directory for auto-generated test scripts."""
    return Path(__file__).resolve().parent.parent / 'testcases' / '__auto_generated__'


def generate_hapray_script(
    steps: list[dict],
    app_name: str,
    bundle_name: str,
    screen_width: int,
    screen_height: int,
    scene_id: str = '',
    time_stamp: str = '',
) -> str:
    """Generate HapRay PerfLoad Python script from steps.

    Args:
        steps: List of step dicts, each with 'action' (str) and 'params' (dict).
        app_name: Human-readable app name (Chinese).
        bundle_name: Application package name.
        screen_width: Source screen width in pixels.
        screen_height: Source screen height in pixels.
        scene_id: 4-digit scene ID suffix (e.g. '0020'). Appended to class/filename.
    """
    pinyin_id = app_name_to_pinyin_id(app_name)
    suffix = f'_{scene_id}' if scene_id else ''
    class_name = f'PerfLoad_{pinyin_id}{suffix}_{time_stamp}'

    lines = []

    # Separate Launch step from the rest

    action_steps = []
    for s in steps:
        if s['action'] == 'Launch':
            pass
        else:
            action_steps.append(s)

    # --- Preamble: preparation (outside performance collection) ---
    lines.append('    def process(self):')
    lines.append('        # === 前置准备（不采集数据）===')

    # launch
    lines.append('        self.driver.swipe_to_home()')
    lines.append('        self.start_app(self.app_package)')
    lines.append('        self.driver.wait(3)')

    # --- Performance collection steps ---
    if action_steps:
        lines.append('')
        lines.append('        # === 性能采集步骤 ===')

        for i, s in enumerate(action_steps, 1):
            lines.append('')
            lines.append(f'        def step{i}():')
            lines.append(_action_to_code(s, screen_width, screen_height, indent=12))

        lines.append('')
        lines.append('        # === 执行性能采集 ===')
        for i, s in enumerate(action_steps, 1):
            step_desc = _describe_single_step(s, app_name, i)
            if s['action'] == 'Wait':
                lines.append(f'        step{i}()  # {step_desc}')
            else:
                lines.append(f'        self.execute_performance_step({_py_str(step_desc)}, 10, step{i})')
    else:
        lines.append('')
        lines.append('        def step1():')
        lines.append('            self.driver.wait(5)')
        lines.append('')
        lines.append(f"        self.execute_performance_step({_py_str(app_name + '-基础场景')}, 15, step1)")

    # --- Assemble full script ---
    script_lines = [
        'from hypium import BY',
        '',
        'from hapray.core.perf_testcase import PerfTestCase',
        '',
        '',
        f'class {class_name}(PerfTestCase):',
        '    def __init__(self, controllers):',
        '        self.TAG = self.__class__.__name__',
        '        super().__init__(self.TAG, controllers)',
        '',
        f"        self._app_package = {_py_str(bundle_name)}",
        f"        self._app_name = {_py_str(app_name)}",
        f'        self.source_screen_width = {screen_width}',
        f'        self.source_screen_height = {screen_height}',
        '',
        '    @property',
        '    def app_package(self) -> str:',
        '        return self._app_package',
        '',
        '    @property',
        '    def app_name(self) -> str:',
        '        return self._app_name',
        '',
    ]

    script_lines.extend(lines)

    return '\n'.join(script_lines) + '\n'


def load_steps_from_pages_json(scene_dir: Path) -> list[dict]:
    """Extract action steps from pages.json.

    Each page entry may contain a 'gui_agent' field with an 'action' dict.
    Only steps with _metadata='do' and success=True are included.
    """
    pages_file = scene_dir / 'ui' / 'step1' / 'pages.json'
    if not pages_file.exists():
        # Fallback: try direct path
        pages_file = scene_dir / 'pages.json'
    if not pages_file.exists():
        raise FileNotFoundError(f'pages.json not found in {scene_dir}')

    with open(pages_file, 'r', encoding='utf-8') as f:
        pages = json.load(f)

    steps = []
    for page in pages:
        if not isinstance(page, dict):
            continue
        ga = page.get('gui_agent')
        if not isinstance(ga, dict):
            continue
        if not ga.get('success', True):
            continue

        action = ga.get('action')
        if not action or not isinstance(action, dict):
            continue

        # Only include 'do' actions, skip 'finish'
        if action.get('_metadata') == 'finish':
            continue

        action_name = action.get('action')
        if not action_name:
            continue

        # Build message annotation from gui_agent.message
        message = ga.get('message', '')

        steps.append({
            'index': ga.get('step_index', len(steps) + 1),
            'action': action_name,
            'params': action,
            'message': message,
        })

    return steps


def load_test_info(scene_dir: Path) -> dict:
    """Load testInfo.json from scene directory."""
    test_info_file = scene_dir / 'testInfo.json'
    if test_info_file.exists():
        with open(test_info_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def convert_scene_to_script(scene_dir: str, device_id: str = None) -> ActionExecuteReturn:
    """Convert a single scene's gui-agent output to a HapRay PerfLoad script.

    Args:
        scene_dir: Path to the scene directory containing pages.json and testInfo.json.
        device_id: Device ID for screen resolution detection (optional).

    Returns:
        (exit_code, output_path) tuple.
    """
    scene_path = Path(scene_dir).resolve()
    if not scene_path.is_dir():
        print(f'Error: directory not found: {scene_path}')
        return (1, '')

    # Load test info
    test_info = load_test_info(scene_path)
    app_package = test_info.get('app_id', '')
    app_name = test_info.get('app_name', '')

    if not app_name:
        print('Error: cannot determine app_name from testInfo.json')
        return (1, '')

    # Extract steps from pages.json
    try:
        steps = load_steps_from_pages_json(scene_path)
    except FileNotFoundError as e:
        print(f'Error: {e}')
        return (1, '')

    if not steps:
        print('Warning: no action steps found in pages.json')
        return (0, '')

    # Get screen resolution from device
    screen_width, screen_height = _get_device_display_size_by_hdc(device_id)

    # Determine output directory and scene ID
    pinyin_id = app_name_to_pinyin_id(app_name)
    auto_dir = _get_auto_testcases_dir() 
    auto_dir.mkdir(parents=True, exist_ok=True)

    # print(scene_dir)
    parts = Path(scene_dir).parts
    scene_id_str = parts[-1]       # e.g. scene1
    time_str = parts[-3]           # e.g. 20260408152721

    # Generate script
    script = generate_hapray_script(
        steps=steps,
        app_name=app_name,
        bundle_name=app_package,
        screen_width=screen_width,
        screen_height=screen_height,
        scene_id=scene_id_str,
        time_stamp=time_str,
    )

    # Save to _auto_generated_ directory
    script_filename = f'PerfLoad_{pinyin_id}_{scene_id_str}_{time_str}.py'
    output_path = auto_dir / script_filename
    output_path.write_text(script, encoding='utf-8')

    json_data = {
        "description": "",
        "environment": [
            {
                "type": "device",
                "label": "phone"
            }
        ],
        "driver": {
            "type": "DeviceTest",
            "py_file": [
                f"{script_filename}"
            ]
        },
        "kits": []
    }
    json_filename = f'PerfLoad_{pinyin_id}_{scene_id_str}_{time_str}.json'
    output_path_json = auto_dir / json_filename
    with open(output_path_json, 'w', encoding='utf-8') as f:
        json.dump(json_data, f, indent=4, ensure_ascii=False)

    print("")
    print(f"report dir: {scene_dir}")
    print(f'Generated: {output_path}')
    print(f'Generated: {output_path_json}')
    print(f'  App: {app_name} ({app_package})')
    print(f'  Steps: {len(steps)}')
    print(f'  Screen: {screen_width}x{screen_height} ')
    print(f'test: python -m scripts.main perf --run_testcases PerfLoad_{pinyin_id}_{scene_id_str}_{time_str}'+"\n")


    return (0, str(output_path))


def _get_device_display_size_by_hdc(device_id: str = None) -> tuple[int, int]:
    """Get display size via hdc shell hidumper DisplayManagerService."""
    try:
        import subprocess
        cmd = ['hdc']
        if device_id:
            cmd.extend(['-t', device_id])
        cmd.extend(['shell', 'hidumper', '-s', 'DisplayManagerService', '-a', '-a'])
        output = subprocess.run(cmd, capture_output=True, text=True, timeout=10).stdout
        # Parse Bounds<L,T,W,H>: line
        match = re.search(r'Bounds<L,T,W,H>:\s*(\d+),\s*(\d+),\s*(\d+),\s*(\d+)', output)
        if match:
            return int(match.group(3)), int(match.group(4))
    except Exception:
        pass
    return (1084, 2412)  # fallback
