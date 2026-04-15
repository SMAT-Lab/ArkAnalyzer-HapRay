"""Convert PhoneAgent execution events to Hapray PerfLoad test scripts.

Reads events.ndjson from a run directory, extracts step actions,
and generates a Hapray-compatible Python test script.
"""

import argparse
import json
import re
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from phone_agent.config.apps_harmonyos import APP_PACKAGES


# Mapping from Agent action names to Hapray script descriptions
ACTION_DESCRIPTIONS = {
    "Launch": "启动应用",
    "Tap": "点击坐标",
    "Double Tap": "双击坐标",
    "Long Press": "长按坐标",
    "Swipe": "滑动",
    "Type": "输入文本",
    "Type_Name": "输入文本",
    "Back": "返回",
    "Home": "回到桌面",
    "Wait": "等待",
}


def load_events(run_dir: Path) -> list[dict]:
    """Load and parse events from events.ndjson."""
    events_file = run_dir / "events.ndjson"
    if not events_file.exists():
        print(f"Error: events.ndjson not found in {run_dir}")
        sys.exit(1)

    events = []
    with open(events_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    return events


def load_meta(run_dir: Path) -> dict:
    """Load meta.json from run directory."""
    meta_file = run_dir / "meta.json"
    if meta_file.exists():
        with open(meta_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def extract_steps(events: list[dict]) -> list[dict]:
    """Extract step events with action data."""
    steps = []
    for event in events:
        if event.get("type") != "step":
            continue

        action = event.get("action")
        if not action:
            continue

        metadata = action.get("_metadata")
        if not metadata or metadata not in ("do", "finish"):
            continue

        # Skip finish actions (they mark task completion, not UI operations)
        if metadata == "finish":
            continue

        action_name = action.get("action")
        if not action_name:
            continue

        steps.append({
            "index": event.get("index", 0),
            "action": action_name,
            "params": action,
            "status": event.get("status", ""),
        })

    return steps


def convert_coordinates(element: list, src_w: int, src_h: int) -> tuple[int, int]:
    """Convert relative coordinates (0-1000) to source screen pixels."""
    x = int(element[0] / 1000 * src_w)
    y = int(element[1] / 1000 * src_h)
    return x, y


def get_bundle_name(app_name: str) -> str:
    """Look up bundle name from app name."""
    return APP_PACKAGES.get(app_name, "")


def app_name_to_pinyin_id(app_name: str) -> str:
    """Convert Chinese app name to a simple pinyin-like identifier.

    Falls back to removing non-ascii characters if no mapping exists.
    """
    # Common known mappings
    KNOWN = {
        "微信": "wechat",
        "QQ": "qq",
        "微博": "weibo",
        "淘宝": "taobao",
        "京东": "jd",
        "拼多多": "pdd",
        "小红书": "xhs",
        "知乎": "zhihu",
        "美团": "meituan",
        "美团外卖": "meituan_waimai",
        "百度": "baidu",
        "快手": "kuaishou",
        "抖音": "douyin",
        "高德地图": "amap",
        "百度地图": "baidumap",
        "网易云音乐": "netease_music",
        "哔哩哔哩": "bilibili",
        "今日头条": "jinritoutiao",
        "携程": "ctrip",
        "天猫": "tmall",
        "饿了么": "eleme",
        "滴滴": "didi",
        "花呗": "huabei",
        "闲鱼": "xianyu",
        "钉钉": "dingtalk",
        "企业微信": "wxwork",
        "西瓜视频": "xigua",
        "百度极速版": "baidu_jisu",
    }
    if app_name in KNOWN:
        return KNOWN[app_name]
    # Fallback: keep only ascii characters
    return re.sub(r"[^a-zA-Z0-9]", "", app_name).lower() or "app"


def generate_hapray_script(
    steps: list[dict],
    task_desc: str,
    app_name: str,
    bundle_name: str,
    screen_width: int,
    screen_height: int,
    run_id: str,
) -> str:
    """Generate Hapray PerfLoad Python script from steps."""

    pinyin_id = app_name_to_pinyin_id(app_name)
    class_name = f"PerfLoad_{pinyin_id}"

    # --- Build process() body ---
    lines = []

    # Separate Launch step from the rest
    launch_step = None
    action_steps = []
    for s in steps:
        if s["action"] == "Launch":
            launch_step = s
        else:
            action_steps.append(s)

    # --- Preamble: preparation (outside performance collection) ---
    lines.append("    def process(self):")
    lines.append("        # === 前置准备（不采集数据）===")

    if launch_step:
        lines.append("        self.driver.swipe_to_home()")
        lines.append(f"        self.start_app(self.app_package)")
        lines.append("        self.driver.wait(3)")

    # --- Performance collection steps: one perf step per event step ---
    if action_steps:
        lines.append("")
        lines.append("        # === 性能采集步骤（每个操作对应一个采集点）===")

        for i, s in enumerate(action_steps, 1):
            lines.append("")
            lines.append(f"        def step{i}():")
            lines.append(_action_to_code(s, screen_width, screen_height, indent=12))

        # Collect all execute_performance_step calls at the end
        lines.append("")
        lines.append("        # === 执行性能采集 ===")
        for i, s in enumerate(action_steps, 1):
            step_desc = _describe_single_step(s, app_name,i)
            if s["action"] == "Wait":
                lines.append(f"        step{i}() # {step_desc}")
            else:
                lines.append(f"        self.execute_performance_step('{step_desc}', 10, step{i})")
    else:
        # No action steps: create a single step with basic interaction
        lines.append("")
        lines.append("        def step1():")
        lines.append("            self.driver.wait(5)")
        lines.append("")
        lines.append("        self.execute_performance_step('{app_name}-基础场景', 15, step1)")

    # --- Assemble full script ---
    script_lines = [
        "from hapray.core.perf_testcase import PerfTestCase",
        "",
        "",
        f"class {class_name}(PerfTestCase):",
        "    def __init__(self, controllers):",
        "        self.TAG = self.__class__.__name__",
        "        super().__init__(self.TAG, controllers)",
        "",
        f"        self._app_package = '{bundle_name}'",
        f"        self._app_name = '{app_name}'",
        f"        self.source_screen_width = {screen_width}",
        f"        self.source_screen_height = {screen_height}",
        "",
        "    @property",
        "    def app_package(self) -> str:",
        "        return self._app_package",
        "",
        "    @property",
        "    def app_name(self) -> str:",
        "        return self._app_name",
        "",
    ]

    script_lines.extend(lines)

    return "\n".join(script_lines) + "\n"


def _action_to_code(step: dict, src_w: int, src_h: int, indent: 8) -> str:
    """Convert a single step action to Hapray Python code line."""
    prefix = " " * indent
    action = step["action"]
    params = step["params"]

    if action == "Launch":
        app = params.get("app", "")
        # Use touch_by_text if we know the app name, else use start_app
        return f"{prefix}# 启动应用: {app}（已在前置准备中完成）"

    elif action == "Tap":
        element = params.get("element")
        if element and len(element) >= 2:
            x, y = convert_coordinates(element, src_w, src_h)
            return f"{prefix}self.touch_by_coordinates({x}, {y}, 2)"
        return f"{prefix}# Tap (no coordinates)"

    elif action == "Double Tap":
        element = params.get("element")
        if element and len(element) >= 2:
            x, y = convert_coordinates(element, src_w, src_h)
            return f"{prefix}self.touch_by_coordinates({x}, {y}, 2)"
        return f"{prefix}# Double Tap (no coordinates)"

    elif action == "Long Press":
        element = params.get("element")
        if element and len(element) >= 2:
            x, y = convert_coordinates(element, src_w, src_h)
            return f"{prefix}self.touch_by_coordinates({x}, {y}, 2)"
        return f"{prefix}# Long Press (no coordinates)"

    elif action == "Swipe":
        start = params.get("start")
        end = params.get("end")
        if start and end and len(start) >= 2 and len(end) >= 2:
            dy = end[1] - start[1]
            dx = end[0] - start[0]
            if dy < -100:
                return f"{prefix}self.swipes_up(1, 1)"
            elif dy > 100:
                return f"{prefix}self.swipes_down(1, 1)"
            elif dx < -100:
                return f"{prefix}self.swipes_left(1, 1)"
            elif dx > 100:
                return f"{prefix}self.swipes_right(1, 1)"
            else:
                sx, sy = convert_coordinates(start, src_w, src_h)
                ex, ey = convert_coordinates(end, src_w, src_h)
                return f"{prefix}self.driver.touch(BY.coords({sx}, {sy}))  # short swipe to ({ex}, {ey})"
        return f"{prefix}# Swipe (no coordinates)"

    elif action == "Type":
        text = params.get("text", "")
        return f'{prefix}self.driver.input_text(BY.type("TextInput"), "{text}")'

    elif action == "Back":
        return f"{prefix}self.swipe_to_back(1)"

    elif action == "Home":
        return f"{prefix}self.swipe_to_home()"

    elif action == "Wait":
        duration = params.get("duration", "1 seconds")
        # Parse duration string like "2 seconds"
        match = re.match(r"([\d.]+)", str(duration))
        seconds = match.group(1) if match else "1"
        return f"{prefix}self.driver.wait({seconds})"

    else:
        return f"{prefix}# Unsupported action: {action}"


def _describe_single_step(step: dict, app_name: str, index: int) -> str:
    """Generate a human-readable description for a single step."""
    action = step["action"]
    action_cn = ACTION_DESCRIPTIONS.get(action, action)

    if action == "Type":
        text = step["params"].get("text", "")
        short = text[:10] + "..." if len(text) > 10 else text
        return f"step{index}-{app_name}-{action_cn}-{short}"
    elif action == "Swipe":
        direction = _swipe_direction_from_step(step)
        return f"step{index}-{app_name}-{action_cn}-{direction}"
    else:
        return f"step{index}-{app_name}-{action_cn}"


def _swipe_direction_from_step(step: dict) -> str:
    """Determine swipe direction from a single step (relative coords 0-1000)."""
    start = step["params"].get("start")
    end = step["params"].get("end")
    if start and end and len(start) >= 2 and len(end) >= 2:
        dy = end[1] - start[1]
        dx = end[0] - start[0]
        if dy < -100:
            return "向上"
        elif dy > 100:
            return "向下"
        elif dx < -100:
            return "向左"
        elif dx > 100:
            return "向右"
    return "自定义"


def main():
    parser = argparse.ArgumentParser(description="Convert execution events to Hapray script")
    parser.add_argument("--run-dir", required=True, help="Run directory containing events.ndjson")
    parser.add_argument("--output-dir", default=None, help="Output directory for Hapray script (optional)")
    parser.add_argument("--screen-width", type=int, default=1084, help="Source screen width in pixels")
    parser.add_argument("--screen-height", type=int, default=2412, help="Source screen height in pixels")
    parser.add_argument("--steps", default=None, help="Comma-separated step indices to include (e.g. '1,3,5')")

    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    if not run_dir.exists():
        print(json.dumps({"success": False, "error": f"Run directory not found: {run_dir}"}))
        sys.exit(1)

    # Load data
    events = load_events(run_dir)
    meta = load_meta(run_dir)
    steps = extract_steps(events)

    if args.steps:
        allowed = set(int(x.strip()) for x in args.steps.split(","))
        steps = [s for s in steps if s["index"] in allowed]

    if not steps:
        print(json.dumps({"success": False, "error": "No action steps found in events"}))
        sys.exit(1)

    # Extract info
    task_desc = meta.get("task", "")
    run_id = meta.get("run_id", run_dir.name)

    # Find app name from Launch step
    app_name = ""
    bundle_name = ""
    for s in steps:
        if s["action"] == "Launch":
            app_name = s["params"].get("app", "")
            bundle_name = get_bundle_name(app_name)
            break

    if not app_name:
        app_name = "UnknownApp"
    if not bundle_name:
        bundle_name = f"com.unknown.{app_name_to_pinyin_id(app_name)}"

    # Get screen resolution from meta, fallback to defaults
    screen_width = meta.get("screen_width") or args.screen_width
    screen_height = meta.get("screen_height") or args.screen_height

    # Generate script
    script = generate_hapray_script(
        steps=steps,
        task_desc=task_desc,
        app_name=app_name,
        bundle_name=bundle_name,
        screen_width=screen_width,
        screen_height=screen_height,
        run_id=run_id,
    )

    # Save to run directory
    script_filename = f"PerfLoad_{app_name_to_pinyin_id(app_name)}.py"
    local_path = run_dir / script_filename
    local_path.write_text(script, encoding="utf-8")

    output_path = str(local_path)

    # Also save to output-dir if specified
    if args.output_dir:
        output_dir = Path(args.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        out_file = output_dir / script_filename
        out_file.write_text(script, encoding="utf-8")
        output_path = str(out_file)

    # Output result as JSON
    result = {
        "success": True,
        "app_name": app_name,
        "bundle_name": bundle_name,
        "script_filename": script_filename,
        "script_path": output_path,
        "local_path": str(local_path),
        "steps_count": len(steps),
        "script_content": script,
    }

    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
