"""
report_renderer.py

生成 _evidence.md（原始证据事实报告，无 LLM 参与）。
仅用于调试和对照，最终给用户看的报告由 LLM 生成（root_cause.md）。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any


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
        lines.append("> 本文件由规则引擎生成，记录原始采样证据，不含 LLM 推断。")
        lines.append("> 根因分析报告请查看同目录下的 `root_cause.md`。")
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
                    f"- `{t.get('thread_name', 'unknown')}` "
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
                    f"thread={frame.get('thread_name', 'unknown')} | "
                    f"dur={frame.get('dur_ms', 0)}ms"
                )
                wakeup = " → ".join(
                    w.get("thread_name", "?") for w in frame.get("wakeup_threads", [])[:5]
                )
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


# Keep old name as alias for backward compatibility with any external callers
EmptyFrameReportRenderer = EvidenceReportRenderer
