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
    Available whenever a HapRay report exists — no decompiled source required.

with_source (enhanced)
    LLM additionally receives decompiled code snippets and call graphs.
    Produces line-level fix recommendations referencing actual code.
    Requires --decompiled-dir; automatically selected when decompiled_dir is provided.
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

from .code_index_lookup import CodeIndexLookup
from .context_builder import ContextBuilder
from .empty_frame_evidence import EmptyFrameEvidenceExtractor
from .knowledge_loader import load_knowledge
from .llm_client import is_llm_configured, load_client_from_config
from .prompts import build_user_prompt, get_system_prompt
from .proc_source_match import pick_aligned_candidates, source_path_aligned
from .report_renderer import EvidenceReportRenderer
from .structured_output import OUTPUT_SCHEMA_STR


_KNOWLEDGE_DIR = Path(__file__).parent / "knowledge"


def _enrich_with_code_and_callgraph(
    evidence: dict[str, Any],
    decompiled_root: Path,
    index_dir: str | None = None,
) -> tuple[str, str]:
    """
    Enrich proc_source_hints with code snippets and call graph info.

    Returns:
        (call_chains_text, module_attribution_text)
    """
    from .code_snippet_extractor import CodeSnippetExtractor
    from .callgraph_traverser import CallgraphTraverser
    from .code_index_lookup import get_module_attributions, format_module_attribution_text

    extractor = CodeSnippetExtractor(decompiled_root)
    proc_hints = evidence.get("proc_source_hints", [])
    proc_hints = extractor.enrich_proc_source_hints(proc_hints)
    evidence["proc_source_hints"] = proc_hints

    if index_dir:
        ui_index_path = Path(index_dir) / "ui_index.jsonl"
        if ui_index_path.exists():
            existing_owners = list({
                c.get("owner_name", "")
                for h in proc_hints
                for c in (h.get("decompiled_candidates") or [])
                if c.get("owner_name")
            })
            if existing_owners:
                ui_extra = extractor.enrich_with_ui_index(
                    owner_names=existing_owners,
                    ui_index_path=ui_index_path,
                    max_extra_snippets=4,
                )
                evidence["ui_extra_snippets"] = ui_extra

    traverser = CallgraphTraverser(decompiled_root)
    proc_hints = traverser.enrich_proc_source_hints(proc_hints)
    call_chains_text = traverser.format_chains_for_prompt(proc_hints)

    module_attribution_text = ""
    if index_dir:
        all_owners = list({
            c.get("owner_name", "")
            for h in proc_hints
            for c in (h.get("decompiled_candidates") or [])
            if c.get("owner_name")
        })
        if all_owners:
            attributions = get_module_attributions(index_dir, all_owners)
            evidence["module_attributions"] = attributions
            module_attribution_text = format_module_attribution_text(attributions)

    return call_chains_text, module_attribution_text


def _load_decompiled_stats(decompiled_dir: Path, index_dir: str | None) -> dict[str, Any]:
    """Load index/stats.json plus shallow dir listing for evidence scope notices."""
    stats_path = Path(index_dir or decompiled_dir / "index") / "stats.json"
    stats: dict[str, Any] = {}
    if stats_path.is_file():
        try:
            stats = json.loads(stats_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            stats = {}
    top_dirs = sorted(
        p.name
        for p in decompiled_dir.iterdir()
        if p.is_dir() and p.name != "index"
    )
    stats.setdefault("input_root", str(decompiled_dir))
    stats["top_level_dirs"] = top_dirs
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
                key=lambda c: (0 if source_path_aligned(c.get('file', ''), hint.get('source_path', '')) else 1),
            )
        for c in ordered:
            if not c.get('code_snippet'):
                continue
            key = f"{c.get('file')}:{c.get('line_start')}"
            if key in seen:
                continue
            seen.add(key)
            entry = dict(c)
            entry['evidence_hits'] = hits
            if hint is not None:
                entry['owner_name'] = entry.get('owner_name') or hint.get('owner_name', '')
                entry['symbol_name'] = entry.get('symbol_name') or (
                    (hint.get('symbols') or [''])[0]
                )
            result.append(entry)

    for hint in evidence.get('proc_source_hints', []):
        direct = hint.get('direct_decompiled_snippet')
        if isinstance(direct, dict) and direct.get('code_snippet'):
            _add_candidates([direct], hint.get('hit_count', 1), hint=hint)
        _add_candidates(
            pick_aligned_candidates(hint, hint.get('decompiled_candidates') or []),
            hint.get('hit_count', 1),
            hint=hint,
        )

    result.sort(
        key=lambda c: (c.get('evidence_hits', 0), 1 if c.get('owner_name') else 0),
        reverse=True,
    )
    return result[:5]


def _run_analyze_with_llm(
    config: dict,
    language: str,
    context_text: str,
    structured_evidence: dict,
    stream: bool,
    code_snippets: list[dict[str, Any]] | None = None,
) -> str | None:
    """
    analyze mode: LLM receives raw evidence (+ optional decompiled snippets) and reasons independently.
    Returns the rendered Markdown report, or None on failure.
    """
    from .structured_output import parse_llm_output, render_to_markdown, render_fallback_markdown

    domain_knowledge = load_knowledge(_KNOWLEDGE_DIR, checker="empty-frame", context_signals=[])
    system_prompt = get_system_prompt(
        language=language, checker="empty-frame", mode="analyze",
        domain_knowledge=domain_knowledge,
    )
    user_prompt = build_user_prompt(
        checker="empty-frame",
        context_text=context_text,
        structured_evidence=structured_evidence,
        code_snippets=code_snippets or [],
        mode="analyze",
    )
    try:
        client = load_client_from_config(config)
        if stream:
            parts: list[str] = []
            for token in client.chat_stream(system_prompt, user_prompt):
                parts.append(token)
            raw_output = "".join(parts)
        else:
            raw_output = client.chat(system_prompt, user_prompt)

        result = parse_llm_output(raw_output)
        if result.parse_success:
            if code_snippets:
                _attach_code_snippets(result.suspects, code_snippets)
            return render_to_markdown(result)
        return render_fallback_markdown(result)
    except Exception as exc:
        logging.warning("LLM analyze mode failed: %s", exc)
        return None


def _apply_module_attributions(suspects: list, structured_evidence: dict) -> None:
    attributions = structured_evidence.get("module_attributions", {}) or {}
    for s in suspects:
        attr = attributions.get(s.owner, {})
        if attr:
            s.module_package = attr.get("package", "")
            s.module_version = attr.get("version", "")
            s.business_domain = attr.get("business_domain", "")


def _build_agent_prompts(
    language: str,
    context_text: str,
    structured_evidence: dict,
    mode: str,
    code_snippets: list[dict[str, Any]],
    call_chains_text: str,
) -> tuple[str, str]:
    domain_knowledge = load_knowledge(_KNOWLEDGE_DIR, checker="empty-frame", context_signals=[])
    system_prompt = get_system_prompt(
        language=language,
        checker="empty-frame",
        mode=mode,
        domain_knowledge=domain_knowledge,
    )
    user_prompt = build_user_prompt(
        checker="empty-frame",
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
) -> Path:
    task_path = output_path.parent / f"{output_path.stem}_agent_task.json"
    task = {
        "task_type": "hapray_root_cause",
        "checker": "empty-frame",
        "mode": mode,
        "language": language,
        "instructions": [
            "Read system_prompt and user_prompt.",
            "Use the current Cursor/default agent model, not local API tokens.",
            "Return a JSON *data object* with summary and suspects (see system_prompt example), "
            "NOT a JSON Schema with type/properties.",
            "Write the JSON result to the requested agent result path if running through HAPRAY_ROOT_CAUSE_AGENT_CMD.",
        ],
        "expected_schema_json": json.loads(OUTPUT_SCHEMA_STR),
        "system_prompt": system_prompt,
        "user_prompt": user_prompt,
    }
    task_path.write_text(json.dumps(task, ensure_ascii=False, indent=2), encoding="utf-8")
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
            'In-process root-cause agent skipped: no LLM API key '
            '(set LLM_API_KEY or HAPRAY_ROOT_CAUSE_AGENT_CMD)'
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
    from .structured_output import parse_llm_output, result_has_content

    parsed = parse_llm_output(raw_output)
    if not parsed.parse_success or not result_has_content(parsed):
        preview = (raw_output or '').strip()[:500]
        logging.warning(
            'In-process root-cause agent: invalid or empty structured output '
            '(parse_success=%s, preview=%r)',
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
    env_cmd = (os.environ.get("HAPRAY_ROOT_CAUSE_AGENT_CMD") or "").strip()
    if not env_cmd:
        return False
    rendered = (
        env_cmd.replace("{task}", str(task_path))
        .replace("{tasks}", str(task_path))
        .replace("{output}", str(result_path))
        .replace("{result}", str(result_path))
        .replace("{report}", str(report_path))
        .replace("{out_dir}", str(report_path.parent))
    )
    logging.info("Running root-cause agent command: %s", rendered)
    try:
        cp = subprocess.run(
            rendered,
            cwd=str(report_path.parent),
            check=False,
            shell=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
        )
    except OSError as exc:
        logging.warning("Root-cause agent command failed to start: %s", exc)
        return False
    if cp.stdout:
        logging.info(cp.stdout[:8000])
    if cp.stderr:
        logging.info(cp.stderr[:8000])
    if cp.returncode != 0:
        logging.warning("Root-cause agent command exited with code %s", cp.returncode)
        return False
    return result_path.is_file()


def _render_agent_result(
    result_path: Path,
    structured_evidence: dict,
    code_snippets: list[dict[str, Any]],
) -> str | None:
    if not result_path.is_file():
        return None
    from .structured_output import parse_llm_output, render_fallback_markdown, render_to_markdown

    from .structured_output import result_has_content

    raw_output = result_path.read_text(encoding="utf-8", errors="ignore")
    result = parse_llm_output(raw_output)
    if result.parse_success and result_has_content(result):
        _attach_code_snippets(result.suspects, code_snippets)
        _apply_module_attributions(result.suspects, structured_evidence)
        return render_to_markdown(result)
    return render_fallback_markdown(result)


def _render_agent_pending_report(task_path: Path, result_path: Path, evidence_report: str) -> str:
    return (
        "# Root Cause Analysis Pending Agent Inference\n\n"
        "未检测到本地 LLM API Key，因此未走 OpenAI-compatible API。"
        "已按符号恢复的离线编排方式导出 Agent 任务，请使用当前 Cursor/default Agent 处理。\n\n"
        "## Agent Task\n\n"
        f"- 任务文件: `{task_path}`\n"
        f"- 期望结果文件: `{result_path}`\n\n"
        "## How To Use\n\n"
        "1. 让当前 Agent 读取任务文件中的 `system_prompt` 和 `user_prompt`。\n"
        "2. 按 `expected_schema_json` 输出合法 JSON。\n"
        "3. 将 JSON 写入期望结果文件。\n"
        "4. 重新运行 `hapray root-cause`，或配置 `HAPRAY_ROOT_CAUSE_AGENT_CMD` 自动生成结果。\n\n"
        "可选自动命令环境变量：\n\n"
        "```bash\n"
        "HAPRAY_ROOT_CAUSE_AGENT_CMD=\"<your-agent-command> --task {task} --output {output}\"\n"
        "```\n\n"
        "## Evidence Report\n\n"
        f"{evidence_report}"
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
) -> str:
    system_prompt, user_prompt = _build_agent_prompts(
        language=language,
        context_text=context_text,
        structured_evidence=structured_evidence,
        mode=mode,
        code_snippets=code_snippets,
        call_chains_text=call_chains_text,
    )
    task_path = _write_agent_task(output_path, language, mode, system_prompt, user_prompt)
    result_path = output_path.parent / f"{output_path.stem}_agent_result.json"
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
        os.environ.get("HAPRAY_ROOT_CAUSE_EXECUTION")
        or llm_config.get("analysis", {}).get("execution_mode")
        or "agent"
    )
    mode = str(raw).strip().lower()
    if mode not in {"agent", "api", "auto"}:
        logging.warning("Unknown root-cause execution mode %r; using agent", raw)
        return "agent"
    return mode


def _normalize_symbol(name: str) -> str:
    """Normalize decompiled symbol names for matching.
    e.g. '___0__aboutToAppear' → 'abouttoappear', 'AboutToAppear' → 'abouttoappear'
    """
    # strip ___N__ prefixes used in decompiled output
    name = re.sub(r"^___\d+__", "", name)
    return name.lower().replace("_", "")


def _attach_code_snippets(
    suspects: list,
    code_snippets: list[dict[str, Any]],
) -> None:
    """
    Attach decompiled code snippets to LLM-output suspects.

    Matching strategy (in priority order):
    1. Exact (file, line_start) — most reliable, decompiled line ranges are stable
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
        snippet = c.get("code_snippet", "")
        if not snippet:
            continue
        file_ = c.get("file", "")
        line_start = int(c.get("line_start", 0) or 0)
        owner = _normalize_symbol(c.get("owner_name", ""))
        symbol = _normalize_symbol(c.get("symbol_name", ""))

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
        loc_key = (s.file or "", int(s.line_start or 0))
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
) -> str | None:
    """
    with_source mode: LLM reads decompiled code snippets and produces line-level fix recommendations.
    Falls back to analyze mode if no code snippets are available.
    Returns the rendered Markdown report, or None on failure.
    """
    from .structured_output import parse_llm_output, render_to_markdown, render_fallback_markdown

    # Fall back to pure analyze only when there are neither code snippets nor
    # any meaningful /proc evidence hints to reason from.
    proc_hints = structured_evidence.get("proc_source_hints", [])
    if not code_snippets and not proc_hints:
        logging.info("No code snippets or evidence; falling back to analyze mode.")
        return _run_analyze_with_llm(config, language, context_text, structured_evidence, stream)

    if not code_snippets:
        logging.info(
            "No code snippets for with_source mode; will reason from evidence only "
            "(%d proc hints available).", len(proc_hints)
        )

    domain_knowledge = load_knowledge(_KNOWLEDGE_DIR, checker="empty-frame", context_signals=[])
    system_prompt = get_system_prompt(
        language=language, checker="empty-frame", mode="with_source",
        domain_knowledge=domain_knowledge,
    )
    user_prompt = build_user_prompt(
        checker="empty-frame",
        context_text=context_text,
        structured_evidence=structured_evidence,
        code_snippets=code_snippets,
        call_chains_text=call_chains_text,
        mode="with_source",
    )

    try:
        client = load_client_from_config(config)
        if stream:
            parts: list[str] = []
            for token in client.chat_stream(system_prompt, user_prompt):
                parts.append(token)
            raw_output = "".join(parts)
        else:
            raw_output = client.chat(system_prompt, user_prompt)

        result = parse_llm_output(raw_output)
        if result.parse_success:
            attributions = structured_evidence.get("module_attributions", {}) or {}
            _attach_code_snippets(result.suspects, code_snippets)
            for s in result.suspects:
                attr = attributions.get(s.owner, {})
                if attr:
                    s.module_package = attr.get("package", "")
                    s.module_version = attr.get("version", "")
                    s.business_domain = attr.get("business_domain", "")
            return render_to_markdown(result)
        return render_fallback_markdown(result)
    except Exception as exc:
        logging.warning("LLM with_source mode failed: %s", exc)
        return None


def run_empty_frame_analysis(
    report_dir: str,
    output_path: str,
    llm_config: dict,
    index_dir: str | None = None,
    decompiled_dir: str | None = None,
    llm_mode: str = "analyze",
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
        index_dir:      Optional path to a decompiled code index directory
                        (contains symbol_index.jsonl / ui_index.jsonl).
        decompiled_dir: Optional path to a decompiled source tree (*.ts / *.callgraph.json).
                        When provided, automatically uses with_source mode.
        llm_mode:       "analyze" (default) or "with_source".
                        Ignored when decompiled_dir is provided (always with_source then).
        stream:         If True, stream LLM tokens to stdout while generating.
        skip_llm:       If True, skip LLM entirely and output the evidence report only.

    Returns:
        The final report content as a string (also written to output_path).
    """
    analysis_cfg = llm_config.get("analysis", {})
    language = analysis_cfg.get("language", "zh")
    top_n = analysis_cfg.get("top_n_hotspots", 10)

    # 1. Build performance context summary
    builder = ContextBuilder(report_dir, top_n=top_n)
    ctx = builder.build()
    context_text = builder.to_prompt_text(ctx)

    # 2. Extract raw evidence (facts only, no opinions)
    extractor = EmptyFrameEvidenceExtractor(report_dir, top_n=min(top_n, 5))
    evidence = extractor.build()

    # 3. Enrich /proc hints with decompiled candidates from index
    if index_dir:
        lookup = CodeIndexLookup(index_dir)
        evidence["proc_source_hints"] = lookup.lookup_proc_sources(evidence.get("proc_source_hints", []))

    # 4. Optionally enrich with code snippets and call graphs
    code_snippets: list[dict[str, Any]] = []
    call_chains_text = ""
    module_attribution_text = ""
    effective_mode = llm_mode

    if decompiled_dir and Path(decompiled_dir).exists():
        decomp_path = Path(decompiled_dir)
        evidence["decompiled_stats"] = _load_decompiled_stats(decomp_path, index_dir)
        call_chains_text, module_attribution_text = _enrich_with_code_and_callgraph(
            evidence, decomp_path, index_dir=index_dir
        )
        code_snippets = _collect_code_snippets_for_prompt(evidence)
        # Include UI extra snippets
        ui_extra = evidence.get("ui_extra_snippets", [])
        main_keys = {f"{c.get('file')}:{c.get('line_start')}" for c in code_snippets}
        for extra in ui_extra:
            key = f"{extra.get('file')}:{extra.get('line_start')}"
            if key not in main_keys:
                code_snippets.append(extra)
                main_keys.add(key)
        effective_mode = "with_source"
    elif llm_mode == "with_source":
        logging.warning(
            "llm_mode=with_source requested but --decompiled-dir not provided; "
            "falling back to analyze mode."
        )
        effective_mode = "analyze"

    # 5. Build structured evidence for LLM
    structured_evidence = {
        "overview": evidence.get("overview", {}),
        "dominant_threads": evidence.get("dominant_threads", []),
        "ui_snapshot_hints": evidence.get("ui_snapshot_hints", []),
        "proc_source_hints": evidence.get("proc_source_hints", []),
        "representative_frames": evidence.get("representative_frames", []),
        "caveats": evidence.get("caveats", []),
        "module_attributions": evidence.get("module_attributions", {}),
    }

    # 6. Always generate the evidence report (debug artifact)
    renderer = EvidenceReportRenderer()
    evidence_report = renderer.render(evidence)

    # 7. Agent / LLM analysis
    final_report: str | None = None
    enriched_context = context_text
    if module_attribution_text:
        enriched_context = context_text + "\n\n" + module_attribution_text

    if not skip_llm:
        execution_mode = _root_cause_execution_mode(llm_config)

        # Default path: agent orchestration.  This matches symbol_recovery and
        # keeps Cursor/skills as the primary LLM execution surface.  The local
        # API path is opt-in via HAPRAY_ROOT_CAUSE_EXECUTION=api or config.
        if execution_mode == "agent":
            logging.info("Root-cause execution mode: agent orchestration")
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
            logging.info("Root-cause execution mode: local OpenAI-compatible API")
            if effective_mode == "with_source":
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
            if execution_mode == "auto" and final_report is None:
                logging.info("Local API failed in auto mode; falling back to agent orchestration")
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
                "No local LLM API key configured; exporting root-cause Agent task "
                "(symbol_recovery-style fallback)."
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
        final_report = evidence_report  # explicit --skip-llm or failed remote/API path

    # 8. Write outputs
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    evidence_path = output.parent / (output.stem + "_evidence.md")
    evidence_path.write_text(evidence_report, encoding="utf-8")
    output.write_text(final_report, encoding="utf-8")

    logging.info("Root cause analysis complete: %s", output_path)
    return final_report


def apply_agent_result_to_report(report_dir: str | Path) -> bool:
    """若已有 ``root_cause_agent_result.json``，渲染并覆盖 ``root_cause.md``。"""
    report_sub = Path(report_dir)
    output_md = report_sub / 'root_cause.md'
    result_path = report_sub / 'root_cause_agent_result.json'
    if not result_path.is_file():
        return False
    rendered = _render_agent_result(result_path, {}, [])
    if not rendered:
        return False
    output_md.write_text(rendered, encoding='utf-8')
    logging.info('Root-cause report refreshed from agent result: %s', output_md)
    return True


def load_llm_config(config_path: str | Path) -> dict:
    """Load an LLM config YAML file."""
    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f)
