"""
runner.py

LLM root cause analysis runner for HapRay empty frame reports.

Public API:
    run_empty_frame_analysis(...)  - analyze a HapRay report directory

Modes
-----
analyze (default)
    LLM receives structured evidence (proc source hits, wakeup chains, UI snapshot)
    and reasons independently to produce a root cause report.
    Available whenever a HapRay report exists — no application source required.

with_source (enhanced)
    LLM additionally receives source code snippets and call graphs.
    Produces line-level fix recommendations referencing actual code.
    Requires --source-dir; automatically selected when source_dir is provided.
"""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
from pathlib import Path
from typing import Any

import yaml

from .callgraph_traverser import CallgraphTraverser
from .code_index_lookup import CodeIndexLookup, format_module_attribution_text, get_module_attributions
from .code_snippet_extractor import CodeSnippetExtractor
from .context_builder import ContextBuilder
from .empty_frame_evidence import EmptyFrameEvidenceExtractor
from .knowledge_loader import load_knowledge
from .llm_client import is_llm_configured, load_client_from_config
from .proc_source_match import pick_aligned_candidates, source_path_aligned
from .prompts import build_user_prompt, get_system_prompt
from .report_renderer import EvidenceReportRenderer
from .signal_extractors import OBSERVATION_EXTRACTORS, SUSPECT_EXTRACTORS
from .structured_output import (
    CATEGORY_LABELS,
    OUTPUT_SCHEMA_STR,
    parse_llm_output,
    render_fallback_markdown,
    render_to_markdown,
    result_has_content,
)

_KNOWLEDGE_DIR = Path(__file__).parent / 'knowledge'
_TIMER_RISK_RE = re.compile(r'\b(setInterval|requestAnimationFrame|setTimeout)\b')


def _collect_timer_risk_snippets(
    source_root: Path,
    owner_names: list[str],
    extractor: Any,
    *,
    max_snippets: int = 3,
) -> list[dict[str, Any]]:
    """Scan owner source files for timer/VSync-risk APIs when /proc hints are missing."""
    results: list[dict[str, Any]] = []
    seen_keys: set[str] = set()

    for owner in owner_names:
        if len(results) >= max_snippets:
            break
        matches = sorted(source_root.rglob(f'{owner}.ets')) + sorted(source_root.rglob(f'{owner}.ts'))
        for path in matches[:2]:
            try:
                lines = path.read_text(encoding='utf-8', errors='replace').splitlines()
            except OSError:
                continue
            rel = str(path.relative_to(source_root)).replace('\\', '/')
            for line_no, line in enumerate(lines, 1):
                if not _TIMER_RISK_RE.search(line):
                    continue
                key = f'{rel}:{line_no}'
                if key in seen_keys:
                    continue
                seen_keys.add(key)
                snippet = extractor.extract(rel, max(1, line_no - 3), min(len(lines), line_no + 8), annotate=True)
                if not snippet:
                    continue
                results.append(
                    {
                        'file': rel,
                        'line_start': line_no,
                        'line_end': line_no,
                        'owner_name': owner,
                        'symbol_name': 'timer_callback',
                        'match_kind': 'timer_risk_scan',
                        'code_snippet': snippet,
                        'confidence_hint': '含 setInterval/requestAnimationFrame/setTimeout',
                    }
                )
                if len(results) >= max_snippets:
                    break
    return results


def _enrich_with_code_and_callgraph(
    evidence: dict[str, Any],
    source_root: Path,
    index_dir: str | None = None,
) -> tuple[str, str]:
    """
    Enrich proc_source_hints with code snippets and call graph info.

    Returns:
        (call_chains_text, module_attribution_text)
    """
    extractor = CodeSnippetExtractor(source_root)
    proc_hints = evidence.get('proc_source_hints', [])
    proc_hints = extractor.enrich_proc_source_hints(proc_hints)
    evidence['proc_source_hints'] = proc_hints

    ui_snapshot_hints = evidence.get('ui_snapshot_hints', []) or []
    snapshot_owner_names = [
        str(item.get('name') or '').strip() for item in ui_snapshot_hints if str(item.get('name') or '').strip()
    ][:5]
    ui_snapshot_snippets: list[dict[str, Any]] = []

    if index_dir and ui_snapshot_hints:
        lookup = CodeIndexLookup(index_dir)
        ui_candidates = lookup.lookup_ui_snapshot_candidates(ui_snapshot_hints)
        extractor.enrich_candidates(ui_candidates)
        ui_snapshot_snippets = [item for item in ui_candidates if item.get('code_snippet')]
        if ui_snapshot_snippets:
            evidence['ui_snapshot_snippets'] = ui_snapshot_snippets
            count_by_name = {str(item.get('name') or ''): int(item.get('count', 0) or 0) for item in ui_snapshot_hints}
            for item in ui_snapshot_snippets:
                item['ui_snapshot_count'] = count_by_name.get(str(item.get('owner_name') or ''), 0)
            logging.info(
                'UI snapshot matched %d source snippets from symbol index',
                len(ui_snapshot_snippets),
            )

    if snapshot_owner_names:
        timer_snippets = _collect_timer_risk_snippets(
            source_root,
            snapshot_owner_names,
            extractor,
            max_snippets=3,
        )
        if timer_snippets:
            existing = evidence.get('ui_snapshot_snippets') or ui_snapshot_snippets
            existing_keys = {f'{item.get("file")}:{item.get("line_start")}' for item in existing}
            merged = list(existing)
            for item in timer_snippets:
                key = f'{item.get("file")}:{item.get("line_start")}'
                if key not in existing_keys:
                    merged.append(item)
                    existing_keys.add(key)
            evidence['ui_snapshot_snippets'] = merged
            ui_snapshot_snippets = merged
            logging.info('Timer-risk scan added %d source snippets', len(timer_snippets))

    if index_dir:
        ui_index_path = Path(index_dir) / 'ui_index.jsonl'
        if ui_index_path.exists():
            existing_owners = list(
                {
                    c.get('owner_name', '')
                    for h in proc_hints
                    for c in (h.get('source_candidates') or [])
                    if c.get('owner_name')
                }
            )
            all_owners = list(dict.fromkeys(existing_owners + snapshot_owner_names))
            if all_owners:
                ui_extra = extractor.enrich_with_ui_index(
                    owner_names=all_owners,
                    ui_index_path=ui_index_path,
                    max_extra_snippets=4,
                )
                evidence['ui_extra_snippets'] = ui_extra

    traverser = CallgraphTraverser(source_root)
    proc_hints = traverser.enrich_proc_source_hints(proc_hints)
    call_chains_text = traverser.format_chains_for_prompt(proc_hints)

    module_attribution_text = ''
    if index_dir:
        all_owners = list(
            dict.fromkeys(
                snapshot_owner_names
                + [
                    c.get('owner_name', '')
                    for h in proc_hints
                    for c in (h.get('source_candidates') or [])
                    if c.get('owner_name')
                ]
            )
        )
        if all_owners:
            attributions = get_module_attributions(index_dir, all_owners)
            evidence['module_attributions'] = attributions
            module_attribution_text = format_module_attribution_text(attributions)

    return call_chains_text, module_attribution_text


def _load_source_stats(source_dir: Path, index_dir: str | None) -> dict[str, Any]:
    """Load index/stats.json plus shallow dir listing for evidence scope notices."""
    stats_path = Path(index_dir or source_dir / 'index') / 'stats.json'
    stats: dict[str, Any] = {}
    if stats_path.is_file():
        try:
            stats = json.loads(stats_path.read_text(encoding='utf-8'))
        except (OSError, json.JSONDecodeError):
            stats = {}
    top_dirs = sorted(p.name for p in source_dir.iterdir() if p.is_dir() and p.name != 'index')
    stats.setdefault('input_root', str(source_dir))
    stats['top_level_dirs'] = top_dirs
    return stats


def _collect_code_snippets_for_prompt(evidence: dict[str, Any]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    result: list[dict[str, Any]] = []

    def _add_candidates(
        cands: list[dict[str, Any]],
        hits: int = 0,
        *,
        hint: dict[str, Any] | None = None,
    ) -> None:
        ordered = list(cands)
        if hint is not None:
            ordered.sort(
                key=lambda c: 0 if source_path_aligned(c.get('file', ''), hint.get('source_path', '')) else 1,
            )
        for c in ordered:
            if not c.get('code_snippet'):
                continue
            key = f'{c.get("file")}:{c.get("line_start")}'
            if key in seen:
                continue
            seen.add(key)
            entry = dict(c)
            entry['evidence_hits'] = hits
            if hint is not None:
                entry['owner_name'] = entry.get('owner_name') or hint.get('owner_name', '')
                entry['symbol_name'] = entry.get('symbol_name') or ((hint.get('symbols') or [''])[0])
            result.append(entry)

    for hint in evidence.get('proc_source_hints', []):
        direct = hint.get('direct_source_snippet')
        if isinstance(direct, dict) and direct.get('code_snippet'):
            _add_candidates([direct], hint.get('hit_count', 1), hint=hint)
        _add_candidates(
            pick_aligned_candidates(hint, hint.get('source_candidates') or []),
            hint.get('hit_count', 1),
            hint=hint,
        )

    for item in evidence.get('ui_snapshot_snippets', []):
        _add_candidates([item], int(item.get('ui_snapshot_count', 0) or 0) or 1)

    for item in evidence.get('ui_extra_snippets', []):
        _add_candidates([item], 0)

    result.sort(
        key=lambda c: (
            c.get('evidence_hits', 0),
            1 if c.get('match_kind') == 'ui_snapshot' else 0,
            1 if c.get('owner_name') else 0,
        ),
        reverse=True,
    )
    return result[:8]


def _run_analyze_with_llm(
    config: dict,
    language: str,
    context_text: str,
    structured_evidence: dict,
    stream: bool,
    code_snippets: list[dict[str, Any]] | None = None,
    checker: str = 'empty-frame',
) -> str | None:
    """
    analyze mode: LLM receives raw evidence (+ optional source snippets) and reasons independently.
    Returns the rendered Markdown report, or None on failure.
    """
    domain_knowledge = load_knowledge(_KNOWLEDGE_DIR, checker=checker, context_signals=[])
    system_prompt = get_system_prompt(
        language=language,
        checker=checker,
        mode='analyze',
        domain_knowledge=domain_knowledge,
    )
    user_prompt = build_user_prompt(
        checker=checker,
        context_text=context_text,
        structured_evidence=structured_evidence,
        code_snippets=code_snippets or [],
        mode='analyze',
    )
    try:
        client = load_client_from_config(config)
        if stream:
            parts: list[str] = []
            for token in client.chat_stream(system_prompt, user_prompt):
                parts.append(token)
            raw_output = ''.join(parts)
        else:
            raw_output = client.chat(system_prompt, user_prompt)

        result = parse_llm_output(raw_output)
        if result.parse_success:
            if code_snippets:
                _attach_code_snippets(result.suspects, code_snippets)
            return render_to_markdown(result)
        return render_fallback_markdown(result)
    except Exception as exc:
        logging.warning('LLM analyze mode failed: %s', exc)
        return None


def _apply_module_attributions(suspects: list, structured_evidence: dict) -> None:
    attributions = structured_evidence.get('module_attributions', {}) or {}
    for s in suspects:
        attr = attributions.get(s.owner, {})
        if attr:
            s.module_package = attr.get('package', '')
            s.module_version = attr.get('version', '')
            s.business_domain = attr.get('business_domain', '')


def _build_agent_prompts(
    language: str,
    context_text: str,
    structured_evidence: dict,
    mode: str,
    code_snippets: list[dict[str, Any]],
    call_chains_text: str,
    checker: str = 'empty-frame',
) -> tuple[str, str]:
    domain_knowledge = load_knowledge(_KNOWLEDGE_DIR, checker=checker, context_signals=[])
    system_prompt = get_system_prompt(
        language=language,
        checker=checker,
        mode=mode,
        domain_knowledge=domain_knowledge,
    )
    user_prompt = build_user_prompt(
        checker=checker,
        context_text=context_text,
        structured_evidence=structured_evidence,
        code_snippets=code_snippets,
        call_chains_text=call_chains_text,
        mode=mode,
    )
    return system_prompt, user_prompt


def _write_agent_task(
    output_path: Path,
    language: str,
    mode: str,
    system_prompt: str,
    user_prompt: str,
    checker: str = 'empty-frame',
) -> Path:
    task_path = output_path.parent / f'{output_path.stem}_agent_task.json'
    task = {
        'task_type': 'hapray_root_cause',
        'checker': checker,
        'mode': mode,
        'language': language,
        'instructions': [
            'Read system_prompt and user_prompt.',
            'Use the current Cursor/default agent model, not local API tokens.',
            'Return a JSON *data object* with summary and suspects (see system_prompt example), '
            'NOT a JSON Schema with type/properties.',
            'Write the JSON result to the requested agent result path if running through HAPRAY_ROOT_CAUSE_AGENT_CMD.',
        ],
        'expected_schema_json': json.loads(OUTPUT_SCHEMA_STR),
        'system_prompt': system_prompt,
        'user_prompt': user_prompt,
    }
    task_path.write_text(json.dumps(task, ensure_ascii=False, indent=2), encoding='utf-8')
    return task_path


def _run_inprocess_agent_inference(
    task_path: Path,
    result_path: Path,
    llm_config: dict,
) -> bool:
    """Agent 编排：读取 task JSON，经 OpenAI-compatible API 推断并写入 result（与符号恢复 Step2 同层）。"""
    if not task_path.is_file():
        return False
    try:
        task = json.loads(task_path.read_text(encoding='utf-8', errors='replace'))
    except (OSError, json.JSONDecodeError) as exc:
        logging.warning('Failed to read root-cause agent task %s: %s', task_path, exc)
        return False
    system_prompt = str(task.get('system_prompt') or '')
    user_prompt = str(task.get('user_prompt') or '')
    if not system_prompt.strip() or not user_prompt.strip():
        logging.warning('Root-cause agent task missing prompts: %s', task_path)
        return False
    if not is_llm_configured(llm_config):
        logging.info(
            'In-process root-cause agent skipped: no LLM API key (set LLM_API_KEY or HAPRAY_ROOT_CAUSE_AGENT_CMD)'
        )
        return False
    try:
        client = load_client_from_config(llm_config)
        raw_output = client.chat(system_prompt, user_prompt)
    except Exception as exc:
        logging.warning('In-process root-cause agent LLM call failed: %s', exc)
        return False
    if not (raw_output or '').strip():
        logging.warning('In-process root-cause agent returned empty output')
        return False

    parsed = parse_llm_output(raw_output)
    if not parsed.parse_success or not result_has_content(parsed):
        preview = (raw_output or '').strip()[:500]
        logging.warning(
            'In-process root-cause agent: invalid or empty structured output (parse_success=%s, preview=%r)',
            parsed.parse_success,
            preview,
        )
        return False
    payload = {
        'summary': parsed.summary,
        'suspects': [s.to_dict() for s in parsed.suspects],
        'caveats': parsed.caveats,
        'needs_more_data': parsed.needs_more_data,
    }
    result_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    logging.info('Root-cause agent result written: %s', result_path)
    return True


def _run_agent_command(task_path: Path, result_path: Path, report_path: Path) -> bool:
    env_cmd = (os.environ.get('HAPRAY_ROOT_CAUSE_AGENT_CMD') or '').strip()
    if not env_cmd:
        return False
    rendered = (
        env_cmd.replace('{task}', str(task_path))
        .replace('{tasks}', str(task_path))
        .replace('{output}', str(result_path))
        .replace('{result}', str(result_path))
        .replace('{report}', str(report_path))
        .replace('{out_dir}', str(report_path.parent))
    )
    logging.info('Running root-cause agent command: %s', rendered)
    try:
        cp = subprocess.run(
            rendered,
            cwd=str(report_path.parent),
            check=False,
            shell=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            capture_output=True,
        )
    except OSError as exc:
        logging.warning('Root-cause agent command failed to start: %s', exc)
        return False
    if cp.stdout:
        logging.info(cp.stdout[:8000])
    if cp.stderr:
        logging.info(cp.stderr[:8000])
    if cp.returncode != 0:
        logging.warning('Root-cause agent command exited with code %s', cp.returncode)
        return False
    return result_path.is_file()


def _render_agent_result(
    result_path: Path,
    structured_evidence: dict,
    code_snippets: list[dict[str, Any]],
) -> str | None:
    if not result_path.is_file():
        return None

    raw_output = result_path.read_text(encoding='utf-8', errors='ignore')
    result = parse_llm_output(raw_output)
    if result.parse_success and result_has_content(result):
        _attach_code_snippets(result.suspects, code_snippets)
        _apply_module_attributions(result.suspects, structured_evidence)
        return render_to_markdown(result)
    return render_fallback_markdown(result)


def _render_skip_llm_report(
    context_text: str,
    sections: dict[str, Any] | None = None,
    evidence_report: str = '',
    checker: str = 'empty-frame',
) -> str:
    """Render a structured placeholder for root_cause.md when --skip-llm is used.

    Unlike the evidence report (which dumps all raw JSON), this template
    provides a concise summary per signal category and marks each as
    "Pending Agent Inference", guiding the Agent to complete the analysis.
    """
    lines: list[str] = [
        '# Root Cause Analysis (Pending Agent Inference)',
        '',
        '> 本报告由 HapRay 规则引擎自动生成，未经过 LLM/Agent 推断。',
        '> 各信号类别的根因推断标记为 **Pending Agent Inference**，需要 Agent 补充深挖。',
        '> 完整原始证据见同目录 `root_cause_evidence.md`。',
        '',
    ]

    lines.append('## 性能摘要')
    lines.append(context_text)
    lines.append('')

    if sections:
        lines.append('## 信号概要与待推断项')
        lines.append('')
        for cat, sec in sections.items():
            label = CATEGORY_LABELS.get(cat, cat)
            kind = sec.get('kind', '')
            kind_label = 'suspect' if kind == 'suspect' else 'observation'
            summary = sec.get('summary')
            items = sec.get('items') or []

            lines.append(f'### [{kind_label}] {label}')
            lines.append('')

            if cat == 'empty-frame' and isinstance(summary, dict):
                total = summary.get('total_empty_frames', '?')
                pct = summary.get('empty_frame_percentage', '?')
                sev = summary.get('severity_level', '?')
                lines.append(f'- 空刷总数: {total}，占比: {pct}%，严重程度: {sev}')
            elif cat == 'component-reuse' and isinstance(summary, dict):
                per_step = summary.get('per_step', [])
                total_builds = sum(s.get('total_builds', 0) for s in per_step)
                total_recycled = sum(s.get('recycled_builds', 0) for s in per_step)
                max_comp = ''
                for s in per_step:
                    if s.get('max_component'):
                        max_comp = s['max_component']
                        break
                lines.append(f'- 总构建: {total_builds}，总回收: {total_recycled}，复用率: {0 if total_builds == 0 else total_recycled / total_builds:.2%}')
                if max_comp:
                    lines.append(f'- 最高构建组件: {max_comp}')
            elif cat == 'frame-load' and isinstance(summary, dict):
                per_step = summary.get('per_step', [])
                if per_step:
                    heaviest = max(per_step, key=lambda s: s.get('average_load', 0))
                    lines.append(
                        f'- 最重步骤: {heaviest.get("step", "?")}，'
                        f'平均负载: {heaviest.get("average_load", 0):.0f}，'
                        f'高负载帧: {heaviest.get("high_load_frames", "?")}/{heaviest.get("total_frames", "?")}'
                    )
            elif cat == 'thread' and isinstance(summary, dict):
                has = summary.get('has_redundancy', False)
                lines.append(f'- 冗余线程: {"是" if has else "无"}')
            elif cat == 'ipc' and isinstance(summary, dict):
                lines.append(f'- 注: {summary.get("note", "")}')
            elif cat == 'so-load' and isinstance(summary, dict):
                total = summary.get('total_so_load', 0)
                lines.append(f'- SO 总负载: {total:,} 指令')
            elif cat == 'ui-animate' and items:
                pass
            elif isinstance(summary, dict):
                keys = [k for k in summary if k not in ('per_step',)]
                if keys:
                    lines.append(f'- 关键指标: {", ".join(keys[:5])}')

            if items:
                lines.append(f'- 明细条目数: {len(items)}')

            lines.append('')
            lines.append(f'**Pending Agent Inference** — 需要 Agent 基于上述证据推断根因、定位源码、给出修复建议。')
            lines.append('')
    else:
        lines.append('## Pending Agent Inference')
        lines.append('')
        lines.append('未提供结构化信号数据。请 Agent 读取 `root_cause_evidence.md` 中的完整证据，')
        lines.append('推断根因、定位源码、给出修复建议。')
        lines.append('')

    return '\n'.join(lines).strip() + '\n'


def _render_agent_pending_report(task_path: Path, result_path: Path, evidence_report: str) -> str:
    return (
        '# Root Cause Analysis Pending Agent Inference\n\n'
        '未检测到本地 LLM API Key，因此未走 OpenAI-compatible API。'
        '已按符号恢复的离线编排方式导出 Agent 任务，请使用当前 Cursor/default Agent 处理。\n\n'
        '## Agent Task\n\n'
        f'- 任务文件: `{task_path}`\n'
        f'- 期望结果文件: `{result_path}`\n\n'
        '## How To Use\n\n'
        '1. 让当前 Agent 读取任务文件中的 `system_prompt` 和 `user_prompt`。\n'
        '2. 按 `expected_schema_json` 输出合法 JSON。\n'
        '3. 将 JSON 写入期望结果文件。\n'
        '4. 重新运行 `hapray root-cause`，或配置 `HAPRAY_ROOT_CAUSE_AGENT_CMD` 自动生成结果。\n\n'
        '可选自动命令环境变量：\n\n'
        '```bash\n'
        'HAPRAY_ROOT_CAUSE_AGENT_CMD="<your-agent-command> --task {task} --output {output}"\n'
        '```\n\n'
        '## Evidence Report\n\n'
        f'{evidence_report}'
    )


def _run_agent_fallback(
    output_path: Path,
    language: str,
    context_text: str,
    structured_evidence: dict,
    mode: str,
    code_snippets: list[dict[str, Any]],
    call_chains_text: str,
    evidence_report: str,
    llm_config: dict | None = None,
    checker: str = 'empty-frame',
) -> str:
    system_prompt, user_prompt = _build_agent_prompts(
        language=language,
        context_text=context_text,
        structured_evidence=structured_evidence,
        mode=mode,
        code_snippets=code_snippets,
        call_chains_text=call_chains_text,
        checker=checker,
    )
    task_path = _write_agent_task(output_path, language, mode, system_prompt, user_prompt, checker=checker)
    result_path = output_path.parent / f'{output_path.stem}_agent_result.json'
    cfg = llm_config or {}

    logging.info('Root-cause agent task exported: %s', task_path)

    if _run_agent_command(task_path, result_path, output_path):
        rendered = _render_agent_result(result_path, structured_evidence, code_snippets)
        if rendered:
            return rendered

    if _run_inprocess_agent_inference(task_path, result_path, cfg):
        rendered = _render_agent_result(result_path, structured_evidence, code_snippets)
        if rendered:
            return rendered

    rendered = _render_agent_result(result_path, structured_evidence, code_snippets)
    if rendered:
        return rendered
    logging.warning(
        'Root-cause agent inference incomplete; pending manual/Cursor agent. '
        'Configure HAPRAY_ROOT_CAUSE_AGENT_CMD or LLM_API_KEY.'
    )
    return _render_agent_pending_report(task_path, result_path, evidence_report)


def _root_cause_execution_mode(llm_config: dict) -> str:
    """Return root-cause execution mode: agent (default), api, or auto."""
    raw = (
        os.environ.get('HAPRAY_ROOT_CAUSE_EXECUTION') or llm_config.get('analysis', {}).get('execution_mode') or 'agent'
    )
    mode = str(raw).strip().lower()
    if mode not in {'agent', 'api', 'auto'}:
        logging.warning('Unknown root-cause execution mode %r; using agent', raw)
        return 'agent'
    return mode


def _normalize_symbol(name: str) -> str:
    """Normalize indexed symbol names for matching.
    e.g. '___0__aboutToAppear' → 'abouttoappear', 'AboutToAppear' → 'abouttoappear'
    """
    # strip ___N__ prefixes used in symbol index / source output
    name = re.sub(r'^___\d+__', '', name)
    return name.lower().replace('_', '')


def _attach_code_snippets(
    suspects: list,
    code_snippets: list[dict[str, Any]],
) -> None:
    """
    Attach source code snippets to LLM-output suspects.

    Matching strategy (in priority order):
    1. Exact (file, line_start) — most reliable, source line ranges are stable
    2. Normalized owner + symbol — handles ___0__ prefix differences
    3. Normalized owner only — last resort when symbol names diverge heavily
    """
    if not code_snippets:
        return

    # Build lookup tables
    by_location: dict[tuple[str, int], str] = {}
    by_owner_symbol: dict[tuple[str, str], str] = {}
    by_owner: dict[str, str] = {}

    for c in code_snippets:
        snippet = c.get('code_snippet', '')
        if not snippet:
            continue
        file_ = c.get('file', '')
        line_start = int(c.get('line_start', 0) or 0)
        owner = _normalize_symbol(c.get('owner_name', ''))
        symbol = _normalize_symbol(c.get('symbol_name', ''))

        if file_ and line_start:
            by_location[(file_, line_start)] = snippet
        if owner and symbol:
            by_owner_symbol[(owner, symbol)] = snippet
        if owner and owner not in by_owner:
            by_owner[owner] = snippet

    for s in suspects:
        if s.code_snippet:
            continue

        # 1. file + line_start
        loc_key = (s.file or '', int(s.line_start or 0))
        if loc_key[1] > 0 and loc_key in by_location:
            s.code_snippet = by_location[loc_key]
            continue

        # 2. owner + symbol (normalized)
        owner_n = _normalize_symbol(s.owner)
        symbol_n = _normalize_symbol(s.symbol)
        if (owner_n, symbol_n) in by_owner_symbol:
            s.code_snippet = by_owner_symbol[(owner_n, symbol_n)]
            continue

        # 3. owner only
        if owner_n in by_owner:
            s.code_snippet = by_owner[owner_n]


def _run_with_source_llm(
    config: dict,
    language: str,
    context_text: str,
    structured_evidence: dict,
    code_snippets: list[dict[str, Any]],
    call_chains_text: str,
    evidence_report: str,
    stream: bool,
    checker: str = 'empty-frame',
) -> str | None:
    """
    with_source mode: LLM reads source code snippets and produces line-level fix recommendations.
    Falls back to analyze mode if no code snippets are available.
    Returns the rendered Markdown report, or None on failure.
    """
    # Fall back to pure analyze only when there are neither code snippets nor
    # any meaningful /proc evidence hints to reason from.
    proc_hints = structured_evidence.get('proc_source_hints', [])
    if not code_snippets and not proc_hints and not structured_evidence.get('sections'):
        logging.info('No code snippets or evidence; falling back to analyze mode.')
        return _run_analyze_with_llm(config, language, context_text, structured_evidence, stream, checker=checker)

    if not code_snippets:
        logging.info(
            'No code snippets for with_source mode; will reason from evidence only (%d proc hints available).',
            len(proc_hints),
        )

    domain_knowledge = load_knowledge(_KNOWLEDGE_DIR, checker=checker, context_signals=[])
    system_prompt = get_system_prompt(
        language=language,
        checker=checker,
        mode='with_source',
        domain_knowledge=domain_knowledge,
    )
    user_prompt = build_user_prompt(
        checker=checker,
        context_text=context_text,
        structured_evidence=structured_evidence,
        code_snippets=code_snippets,
        call_chains_text=call_chains_text,
        mode='with_source',
    )

    try:
        client = load_client_from_config(config)
        if stream:
            parts: list[str] = []
            for token in client.chat_stream(system_prompt, user_prompt):
                parts.append(token)
            raw_output = ''.join(parts)
        else:
            raw_output = client.chat(system_prompt, user_prompt)

        result = parse_llm_output(raw_output)
        if result.parse_success:
            attributions = structured_evidence.get('module_attributions', {}) or {}
            _attach_code_snippets(result.suspects, code_snippets)
            for s in result.suspects:
                attr = attributions.get(s.owner, {})
                if attr:
                    s.module_package = attr.get('package', '')
                    s.module_version = attr.get('version', '')
                    s.business_domain = attr.get('business_domain', '')
            return render_to_markdown(result)
        return render_fallback_markdown(result)
    except Exception as exc:
        logging.warning('LLM with_source mode failed: %s', exc)
        return None


def run_empty_frame_analysis(
    report_dir: str,
    output_path: str,
    llm_config: dict,
    index_dir: str | None = None,
    source_dir: str | None = None,
    llm_mode: str = 'analyze',
    stream: bool = False,
    skip_llm: bool = False,
) -> str:
    """
    Analyze a HapRay report directory for empty frame root causes.

    Args:
        report_dir:     Path to the HapRay step report directory (contains summary.json,
                        trace_emptyFrame.json, etc.).
        output_path:    Destination path for the final Markdown report (e.g. .../root_cause.md).
        llm_config:     LLM and analysis configuration dict.
        index_dir:      Optional path to a source code index directory
                        (contains symbol_index.jsonl / ui_index.jsonl).
        source_dir:     Optional path to an application source tree (*.ts / *.ets / *.callgraph.json).
                        When provided, automatically uses with_source mode.
        llm_mode:       "analyze" (default) or "with_source".
                        Ignored when source_dir is provided (always with_source then).
        stream:         If True, stream LLM tokens to stdout while generating.
        skip_llm:       If True, skip LLM entirely and output the evidence report only.

    Returns:
        The final report content as a string (also written to output_path).
    """
    analysis_cfg = llm_config.get('analysis', {})
    language = analysis_cfg.get('language', 'zh')
    top_n = analysis_cfg.get('top_n_hotspots', 10)

    # 1. Build performance context summary
    builder = ContextBuilder(report_dir, top_n=top_n)
    ctx = builder.build()
    context_text = builder.to_prompt_text(ctx)

    # 2. Extract raw evidence (facts only, no opinions)
    extractor = EmptyFrameEvidenceExtractor(report_dir, top_n=min(top_n, 5))
    evidence = extractor.build()

    # 3. Enrich /proc hints with source candidates from index
    if index_dir:
        lookup = CodeIndexLookup(index_dir)
        evidence['proc_source_hints'] = lookup.lookup_proc_sources(evidence.get('proc_source_hints', []))

    # 4. Optionally enrich with code snippets and call graphs
    code_snippets: list[dict[str, Any]] = []
    call_chains_text = ''
    module_attribution_text = ''
    effective_mode = llm_mode

    if source_dir and Path(source_dir).exists():
        source_path = Path(source_dir)
        evidence['source_stats'] = _load_source_stats(source_path, index_dir)
        call_chains_text, module_attribution_text = _enrich_with_code_and_callgraph(
            evidence, source_path, index_dir=index_dir
        )
        code_snippets = _collect_code_snippets_for_prompt(evidence)
        if evidence.get('ui_snapshot_snippets') and not evidence.get('proc_source_hints'):
            updated_caveats = []
            for caveat in evidence.get('caveats', []):
                if '未命中可用的 /proc 用户态源码符号' in caveat:
                    updated_caveats.append(
                        'perf 采样未命中 /proc 用户态符号，已通过 UI 运行态快照 + 源码索引'
                        '关联到具体 .ets 片段（见下方 UI 快照关联源码）。'
                    )
                else:
                    updated_caveats.append(caveat)
            evidence['caveats'] = updated_caveats
        # Include UI extra snippets
        ui_extra = evidence.get('ui_extra_snippets', [])
        main_keys = {f'{c.get("file")}:{c.get("line_start")}' for c in code_snippets}
        for extra in ui_extra:
            key = f'{extra.get("file")}:{extra.get("line_start")}'
            if key not in main_keys:
                code_snippets.append(extra)
                main_keys.add(key)
        effective_mode = 'with_source'
    elif llm_mode == 'with_source':
        logging.warning('llm_mode=with_source requested but --source-dir not provided; falling back to analyze mode.')
        effective_mode = 'analyze'

    # 5. Build structured evidence for LLM
    structured_evidence = {
        'overview': evidence.get('overview', {}),
        'dominant_threads': evidence.get('dominant_threads', []),
        'ui_snapshot_hints': evidence.get('ui_snapshot_hints', []),
        'proc_source_hints': evidence.get('proc_source_hints', []),
        'representative_frames': evidence.get('representative_frames', []),
        'caveats': evidence.get('caveats', []),
        'module_attributions': evidence.get('module_attributions', {}),
    }

    # 6. Always generate the evidence report (debug artifact)
    renderer = EvidenceReportRenderer()
    evidence_report = renderer.render(evidence)

    # 7. Agent / LLM analysis
    final_report: str | None = None
    enriched_context = context_text
    if module_attribution_text:
        enriched_context = context_text + '\n\n' + module_attribution_text

    if not skip_llm:
        execution_mode = _root_cause_execution_mode(llm_config)

        # Default path: agent orchestration.  This matches symbol_recovery and
        # keeps Cursor/skills as the primary LLM execution surface.  The local
        # API path is opt-in via HAPRAY_ROOT_CAUSE_EXECUTION=api or config.
        if execution_mode == 'agent':
            logging.info('Root-cause execution mode: agent orchestration')
            final_report = _run_agent_fallback(
                output_path=Path(output_path),
                language=language,
                context_text=enriched_context,
                structured_evidence=structured_evidence,
                mode=effective_mode,
                code_snippets=code_snippets,
                call_chains_text=call_chains_text,
                evidence_report=evidence_report,
                llm_config=llm_config,
            )
        elif is_llm_configured(llm_config):
            logging.info('Root-cause execution mode: local OpenAI-compatible API')
            if effective_mode == 'with_source':
                final_report = _run_with_source_llm(
                    config=llm_config,
                    language=language,
                    context_text=enriched_context,
                    structured_evidence=structured_evidence,
                    code_snippets=code_snippets,
                    call_chains_text=call_chains_text,
                    evidence_report=evidence_report,
                    stream=stream,
                )
            else:
                final_report = _run_analyze_with_llm(
                    config=llm_config,
                    language=language,
                    context_text=enriched_context,
                    structured_evidence=structured_evidence,
                    stream=stream,
                    code_snippets=code_snippets if code_snippets else None,
                )
            if execution_mode == 'auto' and final_report is None:
                logging.info('Local API failed in auto mode; falling back to agent orchestration')
                final_report = _run_agent_fallback(
                    output_path=Path(output_path),
                    language=language,
                    context_text=enriched_context,
                    structured_evidence=structured_evidence,
                    mode=effective_mode,
                    code_snippets=code_snippets,
                    call_chains_text=call_chains_text,
                    evidence_report=evidence_report,
                    llm_config=llm_config,
                )
        else:
            logging.info(
                'No local LLM API key configured; exporting root-cause Agent task (symbol_recovery-style fallback).'
            )
            final_report = _run_agent_fallback(
                output_path=Path(output_path),
                language=language,
                context_text=enriched_context,
                structured_evidence=structured_evidence,
                mode=effective_mode,
                code_snippets=code_snippets,
                call_chains_text=call_chains_text,
                evidence_report=evidence_report,
                llm_config=llm_config,
            )

    if final_report is None:
        final_report = _render_skip_llm_report(
            context_text=enriched_context,
            sections={'empty-frame': {
                'category': 'empty-frame',
                'kind': 'suspect',
                'summary': evidence.get('overview', {}),
                'items': evidence.get('proc_source_hints', []),
            }},
            evidence_report=evidence_report,
            checker='empty-frame',
        )

    # 8. Write outputs
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    evidence_path = output.parent / (output.stem + '_evidence.md')
    evidence_path.write_text(evidence_report, encoding='utf-8')
    output.write_text(final_report, encoding='utf-8')

    # Write a structured pending marker when the report is pending agent inference.
    # This is more robust than string-matching the markdown content.
    pending_marker = output.parent / 'root_cause_pending.json'
    if 'Pending Agent Inference' in final_report:
        pending_marker.write_text(
            json.dumps({'pending': True, 'report': str(output), 'checker': 'empty-frame'}, ensure_ascii=False),
            encoding='utf-8',
        )
    elif pending_marker.is_file():
        pending_marker.unlink()

    logging.info('Root cause analysis complete: %s', output_path)
    return final_report


def _collect_comprehensive_snippets(
    sections: dict[str, Any],
    source_root: Path,
    *,
    max_snippets: int = 24,
) -> list[dict[str, Any]]:
    """从所有 section 的 items 中，对带 source_path+line 的条目抽取源码片段。"""
    extractor = CodeSnippetExtractor(source_root)
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, int]] = set()
    for sec in sections.values():
        for item in sec.get('items', []) or []:
            if not isinstance(item, dict):
                continue
            sp = item.get('source_path')
            line = item.get('line') or item.get('line_start')
            if not sp or not line:
                continue
            try:
                line_i = int(line)
            except (TypeError, ValueError):
                continue
            key = (sp, line_i)
            if key in seen:
                continue
            seen.add(key)
            snippet = extractor.extract(sp, max(1, line_i - 3), line_i + 8, annotate=True)
            if not snippet:
                continue
            out.append(
                {
                    'file': sp,
                    'line_start': line_i,
                    'line_end': line_i,
                    'owner_name': item.get('owner_name', ''),
                    'symbol_name': item.get('symbol_name', ''),
                    'code_snippet': snippet,
                    'category': sec.get('category', ''),
                }
            )
            if len(out) >= max_snippets:
                return out
    return out


def _render_comprehensive_evidence(
    sections: dict[str, Any],
    context_text: str,
    code_snippets: list[dict[str, Any]],
) -> str:
    """渲染多信号证据报告（debug 产物，也是 --skip-llm 时的最终输出）。"""
    lines: list[str] = ['# Root Cause Evidence (Comprehensive · multi-signal)', '']
    lines.append('## 性能摘要')
    lines.append(context_text)
    lines.append('')
    for cat, sec in sections.items():
        label = CATEGORY_LABELS.get(cat, cat)
        kind = sec.get('kind', '')
        lines.append(f'## [{kind}] {label}  ({cat})')
        summary = sec.get('summary') or {}
        if summary:
            lines.append('```json')
            lines.append(json.dumps(summary, ensure_ascii=False, indent=2))
            lines.append('```')
        items = sec.get('items') or []
        if items:
            lines.append(f'- 明细条目数: {len(items)}')
            lines.append('```json')
            lines.append(json.dumps(items[:15], ensure_ascii=False, indent=2))
            lines.append('```')
        lines.append('')
    if code_snippets:
        lines.append('## 关联源码片段')
        lines.append('')
        for c in code_snippets:
            lines.append(
                f"### {c.get('owner_name', '')}.{c.get('symbol_name', '')} "
                f"({c.get('file', '')}:{c.get('line_start', 0)})  [{c.get('category', '')}]"
            )
            lines.append('```typescript')
            lines.append((c.get('code_snippet') or '').rstrip())
            lines.append('```')
            lines.append('')
    return '\n'.join(lines).strip() + '\n'


def run_comprehensive_analysis(
    report_dir: str,
    output_path: str,
    llm_config: dict,
    index_dir: str | None = None,
    source_dir: str | None = None,
    llm_mode: str = 'analyze',
    stream: bool = False,
    skip_llm: bool = False,
    enabled_categories: list[str] | None = None,
) -> str:
    """多信号全面根因分析（不限空刷）。

    聚合 CPU 高负载、帧负载、组件复用、线程、IPC、SO 负载、内存（suspect）
    与帧率/UI/故障树（observation）等信号，按 category 分章喂给 LLM/Agent。
    空刷为可选信号：无 trace_emptyFrame.json 也能跑。
    """
    cfg = llm_config or {}
    analysis_cfg = cfg.get('analysis', {}) if isinstance(cfg, dict) else {}
    language = analysis_cfg.get('language', 'zh')
    top_n = analysis_cfg.get('top_n_hotspots', 10)

    def enabled(cat: str) -> bool:
        return enabled_categories is None or cat in enabled_categories

    # 1. 性能上下文摘要
    builder = ContextBuilder(report_dir, top_n=top_n)
    ctx = builder.build()
    context_text = builder.to_prompt_text(ctx)

    sections: dict[str, Any] = {}

    # 2. 空刷（可选，不再硬依赖）
    if enabled('empty-frame'):
        try:
            ef = EmptyFrameEvidenceExtractor(report_dir, top_n=min(top_n, 5)).build()
            proc_hints = ef.get('proc_source_hints', [])
            if index_dir:
                proc_hints = CodeIndexLookup(index_dir).lookup_proc_sources(proc_hints)
            sections['empty-frame'] = {
                'category': 'empty-frame',
                'kind': 'suspect',
                'summary': ef.get('overview', {}),
                'items': proc_hints,
                'dominant_threads': ef.get('dominant_threads', []),
                'representative_frames': (ef.get('representative_frames', []) or [])[:3],
                'caveats': ef.get('caveats', []),
            }
        except FileNotFoundError:
            logging.info('Comprehensive: 无 trace_emptyFrame.json，空刷章跳过（非必需）。')
        except Exception as exc:
            logging.warning('Empty-frame section failed: %s', exc)

    # 3. 其余信号 extractor
    for cls in [*SUSPECT_EXTRACTORS, *OBSERVATION_EXTRACTORS]:
        if not enabled(cls.category):
            continue
        try:
            ext = cls(report_dir, top_n=top_n)
            if not ext.is_available():
                continue
            sec = ext.build()
        except Exception as exc:
            logging.warning('Extractor %s failed: %s', cls.__name__, exc)
            continue
        if sec:
            sections[cls.category] = sec

    if not sections:
        msg = (
            '# Root Cause Analysis\n\n'
            '未发现可用的性能信号产物（report/ 下缺少 trace_*.json / perf.db / so_file_load.json 等）。\n'
        )
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(msg, encoding='utf-8')
        return msg

    logging.info('Comprehensive root-cause signals: %s', ', '.join(sections.keys()))

    # 4. 源码片段（with_source）
    code_snippets: list[dict[str, Any]] = []
    if source_dir and Path(source_dir).exists():
        code_snippets = _collect_comprehensive_snippets(sections, Path(source_dir))

    structured_evidence = {'mode': 'comprehensive', 'sections': sections}
    evidence_report = _render_comprehensive_evidence(sections, context_text, code_snippets)

    # 5. Agent / LLM 分析
    final_report: str | None = None
    if not skip_llm:
        execution_mode = _root_cause_execution_mode(cfg)
        effective_mode = 'with_source' if (source_dir and code_snippets) else 'analyze'
        if execution_mode == 'agent':
            logging.info('Comprehensive root-cause execution mode: agent orchestration')
            final_report = _run_agent_fallback(
                output_path=Path(output_path),
                language=language,
                context_text=context_text,
                structured_evidence=structured_evidence,
                mode=effective_mode,
                code_snippets=code_snippets,
                call_chains_text='',
                evidence_report=evidence_report,
                llm_config=cfg,
                checker='comprehensive',
            )
        elif is_llm_configured(cfg):
            if effective_mode == 'with_source':
                final_report = _run_with_source_llm(
                    config=cfg,
                    language=language,
                    context_text=context_text,
                    structured_evidence=structured_evidence,
                    code_snippets=code_snippets,
                    call_chains_text='',
                    evidence_report=evidence_report,
                    stream=stream,
                    checker='comprehensive',
                )
            else:
                final_report = _run_analyze_with_llm(
                    config=cfg,
                    language=language,
                    context_text=context_text,
                    structured_evidence=structured_evidence,
                    stream=stream,
                    code_snippets=code_snippets or None,
                    checker='comprehensive',
                )
            if execution_mode == 'auto' and final_report is None:
                final_report = _run_agent_fallback(
                    output_path=Path(output_path),
                    language=language,
                    context_text=context_text,
                    structured_evidence=structured_evidence,
                    mode=effective_mode,
                    code_snippets=code_snippets,
                    call_chains_text='',
                    evidence_report=evidence_report,
                    llm_config=cfg,
                    checker='comprehensive',
                )
        else:
            final_report = _run_agent_fallback(
                output_path=Path(output_path),
                language=language,
                context_text=context_text,
                structured_evidence=structured_evidence,
                mode=effective_mode,
                code_snippets=code_snippets,
                call_chains_text='',
                evidence_report=evidence_report,
                llm_config=cfg,
                checker='comprehensive',
            )

    if final_report is None:
        final_report = _render_skip_llm_report(
            context_text=context_text,
            sections=sections,
            evidence_report=evidence_report,
            checker='comprehensive',
        )

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    (output.parent / (output.stem + '_evidence.md')).write_text(evidence_report, encoding='utf-8')
    output.write_text(final_report, encoding='utf-8')

    # Write / clear structured pending marker
    pending_marker = output.parent / 'root_cause_pending.json'
    if 'Pending Agent Inference' in final_report:
        pending_marker.write_text(
            json.dumps({'pending': True, 'report': str(output), 'checker': 'comprehensive'}, ensure_ascii=False),
            encoding='utf-8',
        )
    elif pending_marker.is_file():
        pending_marker.unlink()

    logging.info('Comprehensive root cause analysis complete: %s', output_path)
    return final_report


def apply_agent_result_to_report(report_dir: str | Path) -> bool:
    """若已有 ``root_cause_agent_result.json``，渲染并覆盖 ``root_cause.md``。

    Also clears the pending marker file if present.
    """
    report_sub = Path(report_dir)
    output_md = report_sub / 'root_cause.md'
    result_path = report_sub / 'root_cause_agent_result.json'
    if not result_path.is_file():
        return False
    rendered = _render_agent_result(result_path, {}, [])
    if not rendered:
        return False
    output_md.write_text(rendered, encoding='utf-8')
    # Clear pending marker since agent result has been applied
    pending_marker = report_sub / 'root_cause_pending.json'
    if pending_marker.is_file():
        try:
            pending_marker.unlink()
        except OSError:
            pass
    logging.info('Root-cause report refreshed from agent result: %s', output_md)
    return True


def load_llm_config(config_path: str | Path) -> dict:
    """Load an LLM config YAML file."""
    with open(config_path, encoding='utf-8') as f:
        return yaml.safe_load(f)
