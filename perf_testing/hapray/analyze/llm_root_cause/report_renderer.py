"""
report_renderer.py

生成 root_cause_evidence.md：规则引擎提取的采样事实 +（有反编译树时）路径对齐的代码片段。
不含 LLM 推断；根因结论见 root_cause.md。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .formatting import thread_label, wakeup_chain_labels
from .proc_source_match import pick_aligned_candidates, source_path_aligned


class EvidenceReportRenderer:
    """将规则引擎提取的原始证据渲染为可读 Markdown，不含任何推断或观点。"""

    def render(self, evidence: dict[str, Any]) -> str:
        lines: list[str] = []
        overview = evidence.get("overview", {})
        dominant_threads = evidence.get("dominant_threads", [])
        representative_frames = evidence.get("representative_frames", [])
        proc_source_hints = evidence.get("proc_source_hints", [])
        ui_snapshot_hints = evidence.get("ui_snapshot_hints", [])
        caveats = evidence.get("caveats", [])

        lines.append("# Empty Frame Evidence Report")
        lines.append("")
        lines.append("> 本文件由规则引擎生成：采样事实 + 反编译代码片段（路径与 /proc 命中对齐时）。")
        lines.append("> 不含 LLM 根因推断；结论见同目录 `root_cause.md`。")
        lines.append("")

        # Overview
        total = overview.get("total_empty_frames", 0)
        rate = overview.get("empty_frame_percentage", 0)
        severity = overview.get("severity_level", "unknown")
        main_pct = overview.get("main_thread_percentage_in_empty_frame", 0)
        breakdown = overview.get("detection_breakdown", {})
        lines.append("## 概览")
        lines.append(f"- 空刷总量: **{total}** 帧 | 占比: **{rate}%** | 严重度: **{severity}**")
        lines.append(f"- 主线程空刷占比: {main_pct}%")
        lines.append(
            f"- 检测拆分: direct_only={breakdown.get('direct_only', 0)}, "
            f"rs_traced_only={breakdown.get('rs_traced_only', 0)}, "
            f"both={breakdown.get('both', 0)}"
        )
        lines.append("")

        # Dominant threads
        if dominant_threads:
            lines.append("## 主要线程")
            for t in dominant_threads[:5]:
                lines.append(
                    f"- `{thread_label(t.get('thread_name'))}` "
                    f"[{t.get('role', 'unknown')}] "
                    f"空刷负载占比 {t.get('percentage', 0)}%"
                )
            lines.append("")

        # /proc source hints
        if proc_source_hints:
            lines.append("## /proc 用户态源码命中")
            for i, item in enumerate(proc_source_hints[:8], 1):
                path_obj = Path(item.get("source_path", ""))
                short = (
                    "/".join(path_obj.parts[-2:])
                    if path_obj.name.lower() == "index.ts" and len(path_obj.parts) >= 2
                    else path_obj.name
                )
                lines_str = "/".join(str(ln) for ln in item.get("lines", [])[:4])
                loc = f"{short}:{lines_str}" if lines_str else short
                syms = ", ".join(item.get("symbols", [])[:4])
                lines.append(
                    f"{i}. `{loc}` — hits={item.get('hit_count', 0)} "
                    f"(direct={item.get('direct_hit_count', 0)}, perf={item.get('perf_hit_count', 0)})"
                )
                if syms:
                    lines.append(f"   symbols: {syms}")
            lines.append("")

        self._append_decompiled_scope_notice(lines, evidence)
        self._append_decompiled_snippets(lines, proc_source_hints)
        self._append_ui_snapshot_snippets(lines, evidence.get("ui_snapshot_snippets", []))

        # UI snapshot
        if ui_snapshot_hints:
            lines.append("## UI 运行态快照")
            for item in ui_snapshot_hints[:8]:
                lines.append(
                    f"- `{item.get('name', 'unknown')}` "
                    f"[{item.get('kind', 'unknown')}] "
                    f"count={item.get('count', 0)}"
                )
            lines.append("")

        # Representative frames
        if representative_frames:
            lines.append("## 代表帧（Top Evidence）")
            for i, frame in enumerate(representative_frames[:3], 1):
                lines.append(
                    f"### Frame {i}: VSync#{frame.get('vsync')} | "
                    f"thread={thread_label(frame.get('thread_name'))} | "
                    f"dur={frame.get('dur_ms', 0)}ms"
                )
                wakeup = ' → '.join(wakeup_chain_labels(frame.get('wakeup_threads')))
                if wakeup:
                    lines.append(f"- 唤醒链: {wakeup}")
                syms = frame.get("symbol_hints", [])
                if syms:
                    lines.append(f"- 关键符号: {', '.join(syms[:5])}")
                proc_hits = frame.get("all_proc_source_hits") or frame.get("proc_source_hits") or []
                if proc_hits:
                    hit_strs = []
                    for h in proc_hits[:5]:
                        p = Path(h.get("source_path", ""))
                        short = (
                            "/".join(p.parts[-2:])
                            if p.name.lower() == "index.ts" and len(p.parts) >= 2
                            else p.name
                        )
                        hit_strs.append(
                            f"{short}:{h.get('line')}::{h.get('symbol_name', '?')} [{h.get('via', '?')}]"
                        )
                    lines.append(f"- /proc hits: {' | '.join(hit_strs)}")
            lines.append("")

        # Caveats
        if caveats:
            lines.append("## 注意事项")
            for c in caveats:
                lines.append(f"- {c}")

        return "\n".join(lines).strip() + "\n"

    def _append_decompiled_scope_notice(
        self,
        lines: list[str],
        evidence: dict[str, Any],
    ) -> None:
        """Explain when user-provided decompiled tree is a small subset vs /proc runtime paths."""
        proc_hints = evidence.get("proc_source_hints") or []
        if not proc_hints:
            return

        stats = evidence.get("decompiled_stats") or {}
        file_count = int(stats.get("file_count") or 0)
        input_root = str(stats.get("input_root") or "")
        top_dirs = stats.get("top_level_dirs") or []

        proc_samples = [
            str(h.get("source_path") or "")
            for h in proc_hints[:5]
            if h.get("source_path")
        ]
        if not proc_samples:
            return

        # Heuristic: /proc under src/main/ets/... but decompiled tree is a tiny taobao_main-only pack
        only_taobao_main = (
            file_count > 0
            and file_count < 200
            and (not top_dirs or top_dirs == ["taobao_main"] or top_dirs == ["index", "taobao_main"])
        )
        if not only_taobao_main and file_count >= 200:
            return

        lines.append("## 反编译输入范围说明（重要）")
        lines.append("")
        if file_count:
            lines.append(
                f'- 当前源码树约 **{file_count}** 个 `.ts/.ets` 文件'
                + (f"（根目录: `{input_root}`）" if input_root else "")
                + (f"，顶层模块: `{', '.join(top_dirs)}`" if top_dirs else "")
            )
        else:
            lines.append("- 已配置反编译目录，但未读取到 `index/stats.json` 统计")
        lines.append("- 运行时 `/proc` 命中路径来自**正在运行的完整应用**，例如：")
        for p in proc_samples[:4]:
            lines.append(f"  - `{p}`")
        lines.append(
            "- 若反编译树只有 `taobao_main/` 等子包，**不包含**上述路径对应文件，"
            "则「有源码目录」仍会出现**无匹配片段**——不是工具未搜索，而是**离线树未覆盖运行时模块**。"
        )
        lines.append(
            "- 解决办法：提供**完整主模块**反编译/源码（含 `infoflow/`、`Util.ts` 等），"
            "或对完整 entry.hap / 全部 bundle 重新跑反编译后再 `update`。"
        )
        lines.append("")

    def _append_decompiled_snippets(
        self,
        lines: list[str],
        proc_source_hints: list[dict[str, Any]],
    ) -> None:
        if not proc_source_hints:
            return

        has_any_snippet = False
        blocks: list[str] = []

        for hint in proc_source_hints[:8]:
            source_path = hint.get("source_path", "")
            lines_nums = hint.get("lines", [])[:4]
            loc = f"`{source_path}`" + (f":{lines_nums[0]}" if lines_nums else "")

            direct = hint.get("direct_decompiled_snippet")
            if isinstance(direct, dict) and direct.get("code_snippet"):
                has_any_snippet = True
                blocks.extend(self._format_snippet_block(
                    title=f"直接命中 {loc}",
                    candidate=direct,
                    match_note="按 /proc 路径在反编译树定位",
                ))
                continue

            aligned = [
                c for c in pick_aligned_candidates(hint, hint.get("decompiled_candidates") or [])
                if c.get("code_snippet")
            ]
            if aligned:
                has_any_snippet = True
                blocks.extend(self._format_snippet_block(
                    title=f"索引关联 {loc}",
                    candidate=aligned[0],
                    match_note="索引候选与 /proc 路径后缀一致",
                ))
                continue

            blocks.append(
                f"- {loc} — **无匹配反编译片段**（反编译索引/树中未包含该路径，"
                f"hits={hint.get('hit_count', 0)}）"
            )

        if not has_any_snippet and not blocks:
            return

        lines.append("## 反编译代码片段（与 /proc 命中关联）")
        lines.append("")
        if not has_any_snippet:
            lines.append(
                "> 已配置反编译目录，但当前 Top 命中路径（如 infoflow 动态模块）"
                "未落入离线反编译范围；以下仅列出未命中项。"
            )
            lines.append("")
        lines.extend(blocks)
        lines.append("")

    def _append_ui_snapshot_snippets(
        self,
        lines: list[str],
        ui_snapshot_snippets: list[dict[str, Any]],
    ) -> None:
        if not ui_snapshot_snippets:
            return

        lines.append("## UI 快照关联源码（symbol index / 定时器扫描）")
        lines.append("")
        lines.append(
            "> perf 采样未出现 /proc 用户态符号时，由 UI 运行态组件名在源码索引中定位"
            "（生命周期入口 + setInterval/requestAnimationFrame 扫描）。"
        )
        lines.append("")
        for item in ui_snapshot_snippets[:8]:
            lines.extend(
                self._format_snippet_block(
                    title=(
                        f"{item.get('owner_name', 'unknown')}.{item.get('symbol_name', 'unknown')} "
                        f"(UI count={item.get('ui_snapshot_count', 0)})"
                    ),
                    candidate=item,
                    match_note=str(item.get("match_kind") or item.get("confidence_hint") or "ui_snapshot"),
                )
            )
        lines.append("")

    @staticmethod
    def _format_snippet_block(
        title: str,
        candidate: dict[str, Any],
        match_note: str,
    ) -> list[str]:
        file_name = candidate.get("file", "unknown")
        line_start = candidate.get("line_start", 0)
        line_end = candidate.get("line_end", line_start)
        owner = candidate.get("owner_name", "")
        symbol = candidate.get("symbol_name", "")
        snippet = (candidate.get("code_snippet") or "").rstrip()
        out = [
            f"### {title}",
            f"- 文件: `{file_name}:{line_start}-{line_end}` | {owner}.{symbol}",
            f"- 关联方式: {match_note}",
        ]
        if snippet:
            out.append("```typescript")
            out.append(snippet)
            out.append("```")
        out.append("")
        return out


# Keep old name as alias for backward compatibility with any external callers
EmptyFrameReportRenderer = EvidenceReportRenderer
