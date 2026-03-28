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
import re
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


_STEP_DIR = re.compile(r'^step(\d+)$', re.IGNORECASE)


def _perf_steps_summary_from_steps_json(sj: str) -> list[dict[str, Any]]:
    """steps.json 中的性能用例步（与 LLM 步不同），仅保留索引与名称类字段。"""
    out: list[dict[str, Any]] = []
    try:
        with open(sj, encoding='utf-8') as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return out
    if isinstance(data, list):
        for item in data:
            if not isinstance(item, dict):
                continue
            out.append(
                {
                    'step_index': item.get('stepIdx'),
                    'name': item.get('name'),
                    'description': item.get('description'),
                }
            )
    return out


def _llm_step_events_from_scene(scene_dir: str) -> list[dict[str, Any]]:
    """
    从 ui/stepN/pages.json 聚合 LLM 环路边界（与 perf step 可能一对多）。
    依赖 gui_agent_runner 写入的 gui_agent.step_index / finished / success / error_code。
    """
    events: list[dict[str, Any]] = []
    ui_root = os.path.join(scene_dir, 'ui')
    if not os.path.isdir(ui_root):
        return events
    try:
        names = sorted(os.listdir(ui_root))
    except OSError:
        return events
    for name in names:
        m = _STEP_DIR.match(name)
        if not m:
            continue
        perf_step_id = int(m.group(1))
        pp = os.path.join(ui_root, name, 'pages.json')
        if not os.path.isfile(pp):
            continue
        try:
            with open(pp, encoding='utf-8') as f:
                pages = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(pages, list):
            continue
        for page in pages:
            if not isinstance(page, dict):
                continue
            ga = page.get('gui_agent')
            if not isinstance(ga, dict):
                continue
            msg = ga.get('message') or ''
            act = ga.get('action') or ''
            events.append(
                {
                    'perf_step_id': perf_step_id,
                    'page_idx': page.get('page_idx'),
                    'step_index': ga.get('step_index'),
                    'finished': ga.get('finished'),
                    'success': ga.get('success', True),
                    'error_code': ga.get('error_code'),
                    'message_excerpt': msg[:160],
                    'action_excerpt': act[:120],
                }
            )
    return events


def enrich_gui_agent_contract_outputs(reports_path: str) -> dict[str, Any]:
    """
    从 gui-agent 报告根目录收集轻量场景摘要，写入 tool-result 的 outputs（供 Agent 编排，非全量 steps 内容）。
    目录约定：reports_path/<app_package>/<scene_dir>/{testInfo.json,steps.json,ui/stepN/pages.json}

    默认（当前实现）：进程结束时一次性写入契约，outputs.partial=false；LLM 步边界见各 scene 的 llm_step_events。
    若将来支持长跑中多次刷盘，可约定 outputs.partial=true（schema_version 仍为 1.0 时仅扩展 outputs）。
    """
    extra: dict[str, Any] = {}
    if not reports_path or not os.path.isdir(reports_path):
        return extra
    ap = os.path.abspath(reports_path)
    scenes: list[dict[str, Any]] = []
    try:
        for app_name in sorted(os.listdir(ap)):
            app_dir = os.path.join(ap, app_name)
            if not os.path.isdir(app_dir):
                continue
            for scene_entry in sorted(os.listdir(app_dir)):
                scene_dir = os.path.join(app_dir, scene_entry)
                if not os.path.isdir(scene_dir):
                    continue
                ti = os.path.join(scene_dir, 'testInfo.json')
                sj = os.path.join(scene_dir, 'steps.json')
                row: dict[str, Any] = {
                    'app_package': app_name,
                    'scene_dir': scene_entry,
                    'test_info_present': os.path.isfile(ti),
                    'steps_present': os.path.isfile(sj),
                }
                if os.path.isfile(sj):
                    try:
                        with open(sj, encoding='utf-8') as f:
                            data = json.load(f)
                        if isinstance(data, list):
                            row['step_count'] = len(data)
                        elif isinstance(data, dict):
                            row['step_count'] = len(data)
                        else:
                            row['step_count'] = None
                    except (OSError, json.JSONDecodeError):
                        row['step_count'] = None
                    row['perf_steps_summary'] = _perf_steps_summary_from_steps_json(sj)
                else:
                    row['perf_steps_summary'] = []
                row['llm_step_events'] = _llm_step_events_from_scene(scene_dir)
                last_ev = row['llm_step_events'][-1] if row['llm_step_events'] else None
                row['last_llm_finished'] = (last_ev or {}).get('finished')
                row['last_llm_error_code'] = (last_ev or {}).get('error_code')
                scenes.append(row)
    except OSError as e:
        logging.debug('enrich_gui_agent_contract_outputs: %s', e)
    if scenes:
        extra['gui_agent'] = {
            'reports_dir': ap,
            'contract_mode': 'final',
            'scenes': scenes,
        }
        extra['partial'] = False
    return extra


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
    if action == 'gui-agent' and outputs.get('reports_path'):
        outputs.update(enrich_gui_agent_contract_outputs(outputs['reports_path']))
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
