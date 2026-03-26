"""
Machine-readable CLI result contract for agents (HapRay tool-result v1).

Priority: write JSON beside -o as dirname(abs(-o))/hapray-tool-result.json.
Fallback: --machine-json prints one line to stdout.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from typing import Any

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
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + '\n')
    sys.stdout.flush()


def write_tool_result_file(path: str, payload: dict[str, Any]) -> None:
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


def default_result_path_for_output_file(output_path: str) -> str:
    """Place hapray-tool-result.json beside the primary -o report file."""
    ap = os.path.abspath(output_path)
    d = os.path.dirname(ap)
    if not d:
        d = os.getcwd()
    return os.path.join(d, DEFAULT_RESULT_BASENAME)
