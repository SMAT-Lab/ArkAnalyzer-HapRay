"""
update 流程内集成 root-cause（空刷根因）分析，并将结果写入场景报告目录与总报告 JSON。
"""

from __future__ import annotations

import html
import json
import logging
import os
from pathlib import Path
from typing import Any, Optional

from hapray.actions.root_cause_action import RootCauseAction
from hapray.analyze.llm_root_cause.runner import apply_agent_result_to_report, run_comprehensive_analysis
from hapray.core.common.device_app_packages import (
    ROOT_CAUSE_INPUT_HAP,
    bundle_packages_dir,
    detect_root_cause_input_kind,
    prepare_root_cause_artifacts,
    resolve_root_cause_artifacts,
    root_cause_llm_mode_for_bundle,
)
from hapray.core.common.symbol_recovery_bridge import try_load_dotenv_for_llm

logger = logging.getLogger(__name__)

_ROOT_CAUSE_MARKER = '<!-- hapray-root-cause-embedded -->'


def scene_report_dir(case_dir: str) -> Path:
    return Path(case_dir) / 'report'


def trace_empty_frame_available(case_dir: str) -> bool:
    p = scene_report_dir(case_dir) / 'trace_emptyFrame.json'
    return p.is_file()


def load_root_cause_llm_config() -> dict:
    """与 ``RootCauseAction._load_config`` 对齐的轻量配置（无 argparse）。"""

    class _Parsed:
        config = None
        llm_tokens = None
        api_key = None
        base_url = None
        model = None

    return RootCauseAction._load_config(_Parsed()) or {'llm': {}, 'analysis': {'language': 'zh', 'top_n_hotspots': 10}}


def run_root_cause_for_case(
    case_dir: str,
    report_dir: str,
    bundle_name: str,
    *,
    skip_llm: bool = False,
) -> bool:
    """对单个用例执行多信号 root-cause；输出 ``report/root_cause.md`` 等。"""
    report_sub = scene_report_dir(case_dir)
    if not report_sub.is_dir():
        logger.info('Root-cause skipped for %s: no report directory', case_dir)
        return False
    if not trace_empty_frame_available(case_dir):
        # 空刷已降为可选信号；无 trace_emptyFrame.json 仍可做其余高负载信号的全面根因。
        logger.info('Root-cause for %s: no trace_emptyFrame.json; empty-frame is optional, continuing comprehensive.', case_dir)

    output_md = report_sub / 'root_cause.md'
    pkg_root = bundle_packages_dir(report_dir, bundle_name)
    if pkg_root.is_dir():
        prepare_root_cause_artifacts(pkg_root)
    input_kind = detect_root_cause_input_kind(pkg_root) if pkg_root.is_dir() else ROOT_CAUSE_INPUT_HAP
    index_dir, source_dir = resolve_root_cause_artifacts(report_dir, bundle_name)
    llm_mode = root_cause_llm_mode_for_bundle(report_dir, bundle_name)
    if llm_mode == 'analyze' and input_kind == ROOT_CAUSE_INPUT_HAP:
        manifest = pkg_root / 'app_packages_manifest.json'
        if manifest.is_file():
            try:
                raw = json.loads(manifest.read_text(encoding='utf-8'))
                if isinstance(raw, dict) and raw.get('hap_files'):
                    logger.warning(
                        'Root-cause analyze mode: HAP only for %s (no decompiled source). '
                        'Provide decompiled/*.ts via --app-packages-dir for with_source, '
                        'or set HAPRAY_HAP_DECOMPILER_CMD to decompile HAP.',
                        bundle_name,
                    )
            except (OSError, json.JSONDecodeError):
                pass
    elif llm_mode == 'with_source':
        logger.info(
            'Root-cause with_source for %s (input_kind=%s, source_dir=%s)',
            bundle_name,
            input_kind,
            source_dir,
        )

    try_load_dotenv_for_llm()
    llm_config = load_root_cause_llm_config()
    if llm_config is None:
        logger.warning('Root-cause skipped: LLM config unavailable')
        return False

    logger.info(
        'Running root-cause for %s (mode=%s, index_dir=%s, source_dir=%s, skip_llm=%s)',
        case_dir,
        llm_mode,
        index_dir,
        source_dir,
        skip_llm,
    )
    try:
        run_comprehensive_analysis(
            report_dir=str(report_sub),
            output_path=str(output_md),
            llm_config=llm_config,
            index_dir=index_dir,
            source_dir=source_dir,
            llm_mode=llm_mode,
            stream=False,
            skip_llm=skip_llm,
        )
    except FileNotFoundError as e:
        logger.warning('Root-cause failed for %s: %s', case_dir, e)
        return False
    except Exception:
        logger.exception('Root-cause failed for %s', case_dir)
        return False

    if (
        output_md.is_file()
        and 'Pending Agent Inference' in output_md.read_text(encoding='utf-8', errors='replace')
        and apply_agent_result_to_report(report_sub)
    ):
        logger.info('Root-cause report finalized from agent result for %s', case_dir)

    return output_md.is_file()


def root_cause_payload_for_result(case_dir: str) -> Optional[dict[str, Any]]:
    """供 ``hapray_report.json`` 嵌入的 root-cause 摘要。"""
    md_path = scene_report_dir(case_dir) / 'root_cause.md'
    evidence_path = scene_report_dir(case_dir) / 'root_cause_evidence.md'
    agent_task = scene_report_dir(case_dir) / 'root_cause_agent_task.json'
    agent_result = scene_report_dir(case_dir) / 'root_cause_agent_result.json'
    if not md_path.is_file():
        return None
    try:
        markdown = md_path.read_text(encoding='utf-8', errors='replace')
    except OSError:
        return None
    pending_agent = 'Pending Agent Inference' in markdown or agent_task.is_file()
    return {
        'markdown': markdown,
        'markdown_path': 'root_cause.md',
        'evidence_path': 'root_cause_evidence.md' if evidence_path.is_file() else '',
        'agent_task_path': 'root_cause_agent_task.json' if agent_task.is_file() else '',
        'agent_result_path': 'root_cause_agent_result.json' if agent_result.is_file() else '',
        'pending_agent': pending_agent,
        'execution': os.environ.get('HAPRAY_ROOT_CAUSE_EXECUTION', 'agent').strip().lower() or 'agent',
    }


def merge_root_cause_into_result(case_dir: str, result: dict) -> None:
    payload = root_cause_payload_for_result(case_dir)
    if not payload:
        return
    more = result.setdefault('more', {})
    if not isinstance(more, dict):
        return
    more['root_cause'] = payload


def embed_root_cause_into_hapray_html(case_dir: str) -> bool:
    """在 ``report/hapray_report.html`` 末尾嵌入 root-cause Markdown 面板。"""
    html_path = scene_report_dir(case_dir) / 'hapray_report.html'
    md_path = scene_report_dir(case_dir) / 'root_cause.md'
    if not html_path.is_file() or not md_path.is_file():
        return False
    try:
        text = html_path.read_text(encoding='utf-8', errors='replace')
        md = md_path.read_text(encoding='utf-8', errors='replace')
    except OSError:
        return False
    if _ROOT_CAUSE_MARKER in text:
        return True

    rel_md = 'root_cause.md'
    escaped = html.escape(md)
    block = (
        f'{_ROOT_CAUSE_MARKER}\n'
        '<div id="hapray-root-cause-panel" style="margin:16px;font-family:sans-serif;">\n'
        '<h2>性能根因分析（Root Cause）</h2>\n'
        f'<p><a href="{rel_md}" target="_blank">root_cause.md</a></p>\n'
        f'<pre style="white-space:pre-wrap;max-height:640px;overflow:auto;border:1px solid #ccc;'
        f'padding:12px;">{escaped}</pre>\n'
        '</div>\n'
    )
    lower = text.lower()
    idx = lower.rfind('</body>')
    new_text = text[:idx] + block + '\n' + text[idx:] if idx != -1 else text + '\n' + block
    try:
        html_path.write_text(new_text, encoding='utf-8')
    except OSError:
        return False
    logger.info('Embedded root-cause report into %s', html_path)
    return True
