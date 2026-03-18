import os
import sys
from pathlib import Path


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

