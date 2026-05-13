import os
import shutil
import sys
from pathlib import Path

_cli_path_applied = False

HARMONY_CLI_ENV_HINT = """
The hdc or node command is not in PATH.
Please Download Command Line Tools for HarmonyOS(https://developer.huawei.com/consumer/cn/download/),
then add the following directories to PATH.
    $command_line_tools/tool/node/ (for Windows)
    $command_line_tools/tool/node/bin (for Mac/Linux)
    $command_line_tools/sdk/default/openharmony/toolchains (for ALL)
Or set HAPRAY_TOOLS_BIN to the directory containing bundled hdc (e.g. .../ArkAnalyzer-HapRay.app/Contents/Resources/tools/bin).
If hdc is found but node is not: install HarmonyOS Command Line Tools, or ensure DevEco Studio is at /Applications/DevEco-Studio.app (bundled node), or add your Node installation to PATH.
"""


def _hdc_exe_name() -> str:
    return 'hdc.exe' if sys.platform == 'win32' else 'hdc'


def _hdc_parent_from_env() -> list[Path]:
    raw = os.environ.get('HAPRAY_HDC_PATH', '').strip()
    if not raw:
        return []
    p = Path(raw).expanduser()
    if p.is_file():
        return [p.parent]
    return []


def _bundled_tools_bin_candidates() -> list[Path]:
    cands: list[Path] = []
    env_bin = os.environ.get('HAPRAY_TOOLS_BIN', '').strip()
    if env_bin:
        cands.append(Path(env_bin).expanduser())
    try:
        exe = Path(sys.executable).resolve()
    except OSError:
        return cands
    parent = exe.parent
    # macOS .app：Contents/Resources/tools/perf-testing/perf-testing → tools/bin
    cands.append(parent.parent / 'bin')
    cands.append(parent / 'bin')
    cands.append(parent.parent.parent / 'Resources' / 'tools' / 'bin')
    return cands


def _ohos_node_path_candidates() -> list[Path]:
    """xdevice 依赖 node；除华为 CLI 默认目录外，补充 DevEco Studio 自带 Node（常见本机未配 ~/code/...）。"""
    out: list[Path] = []
    if sys.platform == 'darwin':
        out.append(Path('/Applications/DevEco-Studio.app/Contents/tools/node/bin'))
    home = Path.home()
    if sys.platform == 'win32':
        base = home / 'code' / 'command-line-tools' / 'tool' / 'node'
        out.extend([base, base / 'bin'])
    else:
        out.append(home / 'code' / 'command-line-tools' / 'tool' / 'node' / 'bin')
    return out


def _sdk_toolchains_dirs() -> list[Path]:
    home = Path.home()
    out = [home / 'code' / 'command-line-tools' / 'sdk' / 'default' / 'openharmony' / 'toolchains']
    if sys.platform == 'darwin':
        out.append(
            Path('/Applications/DevEco-Studio.app/Contents/sdk/default/openharmony/toolchains'),
        )
    if sys.platform == 'win32':
        profile = os.environ.get('USERPROFILE', '').strip()
        if profile:
            out.append(Path(profile) / 'code' / 'command-line-tools' / 'sdk' / 'default' / 'openharmony' / 'toolchains')
    return out


def _path_real_norm(path: str) -> str:
    """用于比较 PATH 片段是否指向同一路径。"""
    try:
        return os.path.normcase(os.path.realpath(path))
    except OSError:
        return os.path.normcase(os.path.abspath(path))


def _path_with_priority_dirs_first(priority_dirs: list[Path]) -> None:
    """
    将 priority_dirs 中存在的目录整体移到 PATH 最前。

    若包内 tools/bin 已在 PATH 末尾、而前面还有系统 hdc，则「仅去重跳过 prepend」会仍命中系统；
    这里会先从原 PATH 去掉与 priority 同路径的片段，再按顺序置于最前。
    """
    existing = os.environ.get('PATH', '')
    segments = [s for s in existing.split(os.pathsep) if s]

    front: list[str] = []
    front_norm: set[str] = set()
    for d in priority_dirs:
        if not d.is_dir():
            continue
        try:
            resolved = str(d.resolve())
        except OSError:
            continue
        key = _path_real_norm(resolved)
        if key in front_norm:
            continue
        front_norm.add(key)
        front.append(resolved)

    if not front:
        return

    rest: list[str] = []
    rest_norm: set[str] = set()
    for seg in segments:
        key = _path_real_norm(seg)
        if key in front_norm or key in rest_norm:
            continue
        rest_norm.add(key)
        rest.append(seg)

    os.environ['PATH'] = os.pathsep.join(front + rest)


def ensure_harmony_cli_on_path() -> None:
    """
    为 PyInstaller / App 子进程补齐 PATH：包内 tools/bin（hdc）、华为 CLI 的 node / toolchains。

    须在首次解析 hdc/node 前调用一次；内部幂等。
    """
    global _cli_path_applied
    if _cli_path_applied:
        return
    _cli_path_applied = True

    hdc_name = _hdc_exe_name()
    priority: list[Path] = []
    priority.extend(_hdc_parent_from_env())
    for cand in _bundled_tools_bin_candidates():
        if (cand / hdc_name).is_file():
            priority.append(cand)
            break
    priority.extend(_ohos_node_path_candidates())
    priority.extend(_sdk_toolchains_dirs())
    _path_with_priority_dirs_first(priority)


def harmony_cli_check() -> tuple[bool, str]:
    """
    返回 (是否就绪, 失败时的简短说明)。
    说明用于日志，避免「hdc or node」笼统提示时误判为 hdc 问题。
    """
    ensure_harmony_cli_on_path()
    hdc = shutil.which('hdc')
    node = shutil.which('node')
    if hdc and node:
        return True, ''
    parts: list[str] = []
    if not hdc:
        parts.append('未找到 hdc（已尝试包内 tools/bin、HAPRAY_HDC_PATH、PATH、常见 SDK）')
    if not node:
        parts.append('未找到 node（已尝试华为 CLI node 目录、DevEco 自带 node、PATH）')
    return False, ' '.join(parts) + '. '


def harmony_cli_available() -> bool:
    """与 harmony_cli_check 等价，仅返回是否就绪。"""
    ok, _ = harmony_cli_check()
    return ok


def get_user_data_root(subdir: str) -> Path:
    """
    获取工具在当前平台下的用户数据根目录。

    - macOS：固定放到用户主目录的 `~/ArkAnalyzer-HapRay/<subdir>` 下，避免 App 包 cwd 落在只读目录。
    - 其他平台：仍然使用当前工作目录作为基准目录（向后兼容原有行为）。
    """
    if sys.platform == 'darwin':
        root = Path.home() / 'ArkAnalyzer-HapRay' / subdir
        root.mkdir(parents=True, exist_ok=True)
        return root
    return Path(os.getcwd()) / subdir


def get_log_file_path(log_file: str) -> str:
    """
    统一获取日志文件路径。

    - macOS：`~/ArkAnalyzer-HapRay/logs/<log_file>`
    - 其他平台：`./logs/<log_file>`（相对当前工作目录）
    """
    base_dir = get_user_data_root('logs')
    return str(base_dir / log_file)


def get_reports_root() -> Path:
    """
    性能测试 reports 根目录：

    - macOS：`~/ArkAnalyzer-HapRay/reports`
    - 其他平台：`./reports`
    """
    return get_user_data_root('reports')


def get_haptest_reports_root() -> Path:
    """
    HapTest reports 根目录：

    - macOS：`~/ArkAnalyzer-HapRay/haptest_reports`
    - 其他平台：`./haptest_reports`
    """
    return get_user_data_root('haptest_reports')


def get_runtime_root() -> Path:
    """
    运行期临时根目录（给第三方依赖用相对路径时兜底）。

    - macOS：`~/ArkAnalyzer-HapRay/runtime`
    - 其他平台：`./runtime`
    """
    return get_user_data_root('runtime')
