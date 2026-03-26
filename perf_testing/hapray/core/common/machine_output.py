"""
Machine-readable CLI result contract for agents (HapRay tool-result v1).

Priority: write JSON to a file (next to --output / report dir, or --result-file).
Fallback: --machine-json prints one JSON line to stdout (stderr for logs).
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from typing import Any

from hapray.core.common.action_return import ActionExecuteReturn
from hapray.core.common.path_utils import get_user_data_root

SCHEMA_VERSION = '1.0'
DEFAULT_RESULT_BASENAME = 'hapray-tool-result.json'


def build_tool_result(
    tool_id: str,
    *,
    success: bool | None,
    exit_code: int,
    action: str | None = None,
    outputs: dict[str, Any] | None = None,
    error: str | None = None,
    tool_version: str | None = None,
) -> dict[str, Any]:
    """Build the canonical tool-result payload."""
    payload: dict[str, Any] = {
        'schema_version': SCHEMA_VERSION,
        'tool_id': tool_id,
        'success': success,
        'exit_code': exit_code,
        'outputs': outputs or {},
        'error': error,
    }
    if action is not None:
        payload['action'] = action
    if tool_version is not None:
        payload['tool_version'] = tool_version
    return payload


def emit_tool_result(payload: dict[str, Any]) -> None:
    """Write one JSON line to stdout (UTF-8)."""
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + '\n')
    sys.stdout.flush()


def write_tool_result_file(path: str, payload: dict[str, Any]) -> None:
    """Write pretty-printed JSON to path (creates parent dirs)."""
    abs_path = os.path.abspath(path)
    parent = os.path.dirname(abs_path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(abs_path, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def finalize_contract(
    payload: dict[str, Any],
    *,
    result_path: str | None,
    machine_json: bool,
) -> str | None:
    """
    Emit contract: prefer file at result_path; on failure or if no path, use stdout if machine_json.

    Returns how the contract was emitted: 'file', 'stdout', or None if skipped.
    """
    out = payload.setdefault('outputs', {})
    if result_path:
        abs_rp = os.path.abspath(result_path)
        out['hapray_tool_result_path'] = abs_rp
        try:
            write_tool_result_file(result_path, payload)
            return 'file'
        except OSError as e:
            logging.warning('无法写入 tool-result 文件 %s: %s', result_path, e)
            if machine_json:
                out['hapray_tool_result_sink'] = 'stdout'
                emit_tool_result(payload)
                return 'stdout'
            return None
    if machine_json:
        out['hapray_tool_result_sink'] = 'stdout'
        emit_tool_result(payload)
        return 'stdout'
    return None


def interpret_perf_testing_return(
    action: str, ret: ActionExecuteReturn
) -> tuple[bool, int, dict[str, Any], str | None]:
    """
    Map action return values to (success, exit_code, outputs, error).

    约定：ActionExecuteReturn 恒为 (exit_code, reports_path)。
    """
    code, rpath = ret
    ok = code == 0
    out: dict[str, Any] = {'reports_path': rpath} if rpath else {}
    return ok, code, out, None if ok else f'exit_code_{code}'


def _parse_static_result_path(sub_args: list[str]) -> str | None:
    p = argparse.ArgumentParser(add_help=False)
    p.add_argument('-o', '--output', default='./static-output')
    p.add_argument('-i', '--input')
    try:
        ns, _ = p.parse_known_args(sub_args)
    except SystemExit:
        return None
    out = ns.output
    if sys.platform == 'darwin':
        out = str(get_user_data_root('static-output') / os.path.basename(out))
    return os.path.join(os.path.abspath(out), DEFAULT_RESULT_BASENAME)


def _parse_compare_result_path(sub_args: list[str]) -> str | None:
    p = argparse.ArgumentParser(add_help=False)
    p.add_argument('--base_dir')
    p.add_argument('--compare_dir')
    p.add_argument('--output', default=None)
    try:
        ns, _ = p.parse_known_args(sub_args)
    except SystemExit:
        return None
    op = os.path.abspath(ns.output) if ns.output else os.path.join(os.getcwd(), 'compare_result.xlsx')
    if sys.platform == 'darwin':
        op = str(get_user_data_root('compare') / os.path.basename(op))
    return os.path.join(os.path.dirname(op), DEFAULT_RESULT_BASENAME)


def _parse_update_result_path(sub_args: list[str]) -> str | None:
    p = argparse.ArgumentParser(add_help=False)
    p.add_argument('-r', '--report_dir', default=None)
    try:
        ns, _ = p.parse_known_args(sub_args)
    except SystemExit:
        return None
    if not ns.report_dir:
        return None
    return os.path.join(os.path.abspath(ns.report_dir), DEFAULT_RESULT_BASENAME)


def _result_file_beside_report_ref(action: str, rpath: str) -> str | None:
    """根据 action 将第二段路径解析为 hapray-tool-result.json 的绝对路径。"""
    if not rpath:
        return None
    ap = os.path.abspath(rpath)
    if action in ('hilog', 'compare'):
        return os.path.join(os.path.dirname(ap), DEFAULT_RESULT_BASENAME)
    return os.path.join(ap, DEFAULT_RESULT_BASENAME)


def resolve_perf_testing_result_path(
    action: str,
    ret: ActionExecuteReturn,
    sub_args: list[str],
    explicit_result_file: str | None,
) -> str | None:
    """Resolve absolute path for hapray-tool-result.json, or None if unknown."""
    if explicit_result_file:
        return os.path.abspath(explicit_result_file)
    _code, rpath = ret
    if rpath:
        p = _result_file_beside_report_ref(action, rpath)
        if p:
            return p
    if action == 'static':
        return _parse_static_result_path(sub_args)
    if action == 'compare':
        return _parse_compare_result_path(sub_args)
    if action == 'update':
        return _parse_update_result_path(sub_args)
    return None


def finish_perf_testing_contract(
    action: str,
    ret: ActionExecuteReturn,
    sub_args: list[str],
    *,
    tool_version: str,
    explicit_result_file: str | None,
    machine_json: bool,
) -> None:
    """Write tool-result for perf_testing entrypoint."""
    if '--multiprocessing-fork' in sys.argv:
        return
    success, exit_code, outputs, err = interpret_perf_testing_return(action, ret)
    payload = build_tool_result(
        'perf_testing',
        success=success,
        exit_code=exit_code,
        action=action,
        outputs=outputs,
        error=err,
        tool_version=tool_version,
    )
    result_path = resolve_perf_testing_result_path(action, ret, sub_args, explicit_result_file)
    finalize_contract(payload, result_path=result_path, machine_json=machine_json)
