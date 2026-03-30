"""
perf_testing 与各 Action.execute(sub_args) 的返回值契约。

与 hapray.core.common.machine_output.interpret_perf_testing_return 必须保持一致。
"""

from __future__ import annotations

from typing import Any, TypeAlias

# (exit_code, reports_path)：0 表示成功；reports_path 为报告根目录或主产物路径（可为空字符串）
ActionExecuteReturn: TypeAlias = tuple[int, str]


def is_valid_action_execute_return(value: Any) -> bool:
    """运行时校验 execute 返回值是否为契约类型 (int, str)。"""
    if not isinstance(value, tuple) or len(value) != 2:
        return False
    code, path = value
    return isinstance(code, int) and isinstance(path, str)
