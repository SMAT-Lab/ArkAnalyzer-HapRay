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

import logging
import os
import re
from pathlib import Path
from typing import Any

import yaml

from .code_index_lookup import CodeIndexLookup
from .context_builder import ContextBuilder
from .empty_frame_evidence import EmptyFrameEvidenceExtractor
from .knowledge_loader import load_knowledge
from .llm_client import load_client_from_config
from .prompts import build_user_prompt, get_system_prompt
from .report_renderer import EvidenceReportRenderer


_KNOWLEDGE_DIR = Path(__file__).parent / "knowledge"


def _llm_is_configured(config: dict) -> bool:
    llm_cfg = config.get("llm", {})
    api_key = llm_cfg.get("api_key", "")
    if not api_key:
        return False
    if isinstance(api_key, str) and api_key.startswith("${") and api_key.endswith("}"):
        env_name = api_key[2:-1]
        return bool(os.environ.get(env_name))
    return bool(str(api_key).strip())


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


def _collect_code_snippets_for_prompt(evidence: dict[str, Any]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    result: list[dict[str, Any]] = []

    def _add_candidates(cands: list[dict[str, Any]], hits: int = 0) -> None:
        for c in cands:
            if not c.get("code_snippet"):
                continue
            key = f"{c.get('file')}:{c.get('line_start')}"
            if key in seen:
                continue
            seen.add(key)
            c["evidence_hits"] = hits
            result.append(c)

    for hint in evidence.get("proc_source_hints", []):
        _add_candidates(hint.get("decompiled_candidates") or [], hint.get("hit_count", 1))

    result.sort(key=lambda c: c.get("evidence_hits", 0), reverse=True)
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
        call_chains_text, module_attribution_text = _enrich_with_code_and_callgraph(
            evidence, Path(decompiled_dir), index_dir=index_dir
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

    # 7. LLM analysis
    final_report: str | None = None
    if not skip_llm and _llm_is_configured(llm_config):
        enriched_context = context_text
        if module_attribution_text:
            enriched_context = context_text + "\n\n" + module_attribution_text

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

    if final_report is None:
        final_report = evidence_report  # fallback: show evidence if LLM skipped or failed

    # 8. Write outputs
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    evidence_path = output.parent / (output.stem + "_evidence.md")
    evidence_path.write_text(evidence_report, encoding="utf-8")
    output.write_text(final_report, encoding="utf-8")

    logging.info("Root cause analysis complete: %s", output_path)
    return final_report


def load_llm_config(config_path: str | Path) -> dict:
    """Load an LLM config YAML file."""
    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f)
