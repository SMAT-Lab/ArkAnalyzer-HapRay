"""
context_builder.py

将 HapRay 报告目录中的 JSON 文件压缩为 LLM 可用的结构化上下文。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class AnalysisContext:
    app_name: str = ""
    scene: str = ""
    step_id: str = ""
    total_frames: int = 0
    jank_frames: int = 0
    jank_rate: float = 0.0
    avg_fps: float = 0.0
    min_fps: float = 0.0
    empty_frame_count: int = 0
    empty_frame_rate: float = 0.0
    top_jank_frames: list = field(default_factory=list)
    top_redundant_threads: list = field(default_factory=list)
    fault_tree: dict = field(default_factory=dict)
    ipc_binder: list = field(default_factory=list)
    vsync_anomaly_count: int = 0
    empty_frame_summary: dict = field(default_factory=dict)
    empty_frame_top_threads: list = field(default_factory=list)
    empty_frame_top_frames: list = field(default_factory=list)


class ContextBuilder:
    def __init__(self, report_dir: str, top_n: int = 10):
        self.report_dir = Path(report_dir)
        self.top_n = top_n

    def build(self) -> AnalysisContext:
        ctx = AnalysisContext()
        self._load_summary(ctx)
        self._load_frames(ctx)
        self._load_threads(ctx)
        self._load_fault_tree(ctx)
        self._load_ipc(ctx)
        self._load_vsync(ctx)
        self._load_empty_frame_details(ctx)
        return ctx

    def _read_json(self, filename: str) -> dict | list | None:
        path = self.report_dir / filename
        if not path.exists():
            return None
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    @staticmethod
    def _first_dict_item(data: dict | list | None) -> dict:
        if isinstance(data, dict):
            return data
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    return item
        return {}

    @staticmethod
    def _safe_float(value, default: float = 0.0) -> float:
        if value is None:
            return default
        if isinstance(value, str):
            text = value.strip().rstrip("%")
            if not text:
                return default
            try:
                return float(text)
            except ValueError:
                return default
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def _load_summary(self, ctx: AnalysisContext):
        data = self._read_json("summary.json")
        if not data:
            return

        if isinstance(data, list):
            item = self._first_dict_item(data)
            ctx.step_id = item.get("step_id", "")
            if ctx.step_id:
                ctx.scene = ctx.step_id.rsplit("_step", 1)[0]
            if not ctx.app_name:
                ctx.app_name = item.get("app_name", "") or item.get("bundle_name", "")

            empty = item.get("empty_frame", {}) if isinstance(item.get("empty_frame"), dict) else {}
            ctx.empty_frame_count = int(empty.get("count", 0) or 0)
            ctx.empty_frame_rate = self._safe_float(empty.get("percentage", 0.0))
            return

        ctx.app_name = data.get("appName", "")
        ctx.avg_fps = self._safe_float(data.get("fps", {}).get("average", 0))
        ctx.min_fps = self._safe_float(data.get("fps", {}).get("min", 0))

        stutter = data.get("stutter", {})
        ctx.total_frames = int(stutter.get("totalFrames", 0) or 0)
        ctx.jank_frames = int(stutter.get("stutterFrames", 0) or 0)
        ctx.jank_rate = round(ctx.jank_frames / ctx.total_frames * 100, 2) if ctx.total_frames else 0.0

        empty = data.get("emptyFrame", {})
        ctx.empty_frame_count = int(empty.get("count", 0) or 0)
        rate = self._safe_float(empty.get("rate", 0))
        ctx.empty_frame_rate = round(rate * 100, 2) if rate <= 1 else round(rate, 2)

    def _load_frames(self, ctx: AnalysisContext):
        data = self._read_json("trace_frames.json")
        if not isinstance(data, dict):
            return
        stutters = data.get("stutterDetails", [])
        sorted_stutters = sorted(stutters, key=lambda x: x.get("exceedTime", 0), reverse=True)
        ctx.top_jank_frames = [
            {
                "vsync": s.get("vsyncId"),
                "duration_ms": round((s.get("exceedTime", 0) or 0) / 1_000_000, 2),
                "exceed_frames": s.get("exceedFrames", 0),
                "level": s.get("level", ""),
            }
            for s in sorted_stutters[: self.top_n]
        ]

    def _load_threads(self, ctx: AnalysisContext):
        data = self._read_json("redundant_thread_analysis.json")
        if not isinstance(data, dict):
            return
        threads = data.get("redundantThreads", [])
        sorted_threads = sorted(threads, key=lambda x: x.get("redundancyScore", 0), reverse=True)
        ctx.top_redundant_threads = [
            {
                "name": t.get("threadName", ""),
                "score": t.get("redundancyScore", 0),
                "wait_ratio": round((t.get("waitRatio", 0) or 0) * 100, 1),
                "wasted_instructions_m": round((t.get("redundantInstructions", 0) or 0) / 1_000_000, 1),
                "pattern": t.get("redundancyType", ""),
                "callstack_top": t.get("topCallstack", [])[:5],
            }
            for t in sorted_threads[: self.top_n]
        ]

    def _load_fault_tree(self, ctx: AnalysisContext):
        data = self._read_json("trace_fault_tree.json")
        if isinstance(data, dict):
            ctx.fault_tree = data

    def _load_ipc(self, ctx: AnalysisContext):
        data = self._read_json("trace_ipc_binder.json")
        if not data:
            return
        binder_calls = data.get("binderCalls", []) if isinstance(data, dict) else data
        sorted_calls = sorted(binder_calls, key=lambda x: x.get("count", 0), reverse=True)
        ctx.ipc_binder = sorted_calls[:5]

    def _load_vsync(self, ctx: AnalysisContext):
        data = self._read_json("trace_vsyncAnomaly.json")
        if not data:
            return
        anomalies = data.get("anomalies", []) if isinstance(data, dict) else data
        ctx.vsync_anomaly_count = len(anomalies)

    def _load_empty_frame_details(self, ctx: AnalysisContext):
        data = self._read_json("trace_emptyFrame.json")
        if not isinstance(data, dict) or not data:
            return

        first_step_key = sorted(data.keys())[0]
        step_data = data.get(first_step_key, {})
        if not isinstance(step_data, dict):
            return

        summary = step_data.get("summary", {}) if isinstance(step_data.get("summary"), dict) else {}
        threads = step_data.get("thread_statistics", {}).get("top_threads", [])
        frames = step_data.get("top_frames", [])

        ctx.empty_frame_summary = summary
        ctx.empty_frame_top_threads = threads[: self.top_n]
        ctx.empty_frame_top_frames = frames[: self.top_n]

        if not ctx.step_id:
            ctx.step_id = first_step_key
        if not ctx.empty_frame_count:
            ctx.empty_frame_count = int(summary.get("total_empty_frames", 0) or 0)
        if not ctx.empty_frame_rate:
            ctx.empty_frame_rate = round(self._safe_float(summary.get("empty_frame_percentage", 0.0)), 2)
        if not ctx.app_name:
            if ctx.empty_frame_top_threads:
                ctx.app_name = ctx.empty_frame_top_threads[0].get("process_name", "") or ""
            elif ctx.empty_frame_top_frames:
                ctx.app_name = ctx.empty_frame_top_frames[0].get("process_name", "") or ""

    def to_prompt_text(self, ctx: AnalysisContext) -> str:
        lines = []

        lines.append("## 性能概览")
        lines.append(f"- App: {ctx.app_name or '未知'}")
        if ctx.scene:
            lines.append(f"- 场景: {ctx.scene}")
        if ctx.avg_fps or ctx.min_fps:
            lines.append(f"- 平均 FPS: {ctx.avg_fps}，最低 FPS: {ctx.min_fps}")
        if ctx.total_frames or ctx.jank_frames:
            lines.append(f"- 总帧数: {ctx.total_frames}，卡顿帧: {ctx.jank_frames}（{ctx.jank_rate}%）")
        lines.append(f"- 空刷: {ctx.empty_frame_count}（{ctx.empty_frame_rate}%）")
        lines.append(f"- VSync 异常: {ctx.vsync_anomaly_count} 次")

        if ctx.empty_frame_summary:
            lines.append("\n## 空刷检测摘要")
            lines.append(
                f"- 空刷总数: {ctx.empty_frame_summary.get('total_empty_frames', 0)} | "
                f"空刷占比: {round(self._safe_float(ctx.empty_frame_summary.get('empty_frame_percentage', 0.0)), 2)}% | "
                f"严重程度: {ctx.empty_frame_summary.get('severity_level', 'unknown')}"
            )
            breakdown = ctx.empty_frame_summary.get("detection_breakdown", {})
            if breakdown:
                lines.append(
                    f"- 检测拆分: direct_only={breakdown.get('direct_only', 0)}, "
                    f"rs_traced_only={breakdown.get('rs_traced_only', 0)}, both={breakdown.get('both', 0)}"
                )
            rs_stats = ctx.empty_frame_summary.get("rs_trace_stats", {})
            if rs_stats:
                lines.append(
                    f"- RS追溯: traced={rs_stats.get('traced_success_count', 0)}/{rs_stats.get('total_skip_frames', 0)}, "
                    f"accuracy={round(self._safe_float(rs_stats.get('trace_accuracy', 0.0)), 2)}%"
                )

        if ctx.empty_frame_top_threads:
            lines.append("\n## 空刷高贡献线程")
            for thread in ctx.empty_frame_top_threads[:5]:
                lines.append(
                    f"- {thread.get('thread_name', 'unknown')} "
                    f"({thread.get('process_name', 'unknown')}) | "
                    f"占比={round(self._safe_float(thread.get('percentage', 0.0)), 2)}% | "
                    f"load={thread.get('total_load', 0)}"
                )

        if ctx.empty_frame_top_frames:
            lines.append("\n## Top 空刷帧")
            for frame in ctx.empty_frame_top_frames[:5]:
                lines.append(
                    f"- vsync={frame.get('vsync')} | thread={frame.get('thread_name', 'unknown')} | "
                    f"load={frame.get('frame_load', 0)} | dur={frame.get('dur', 0)} | "
                    f"callstack_id={frame.get('callstack_id', 'unknown')}"
                )

        if ctx.top_jank_frames:
            lines.append("\n## Top 卡顿帧")
            for i, frame in enumerate(ctx.top_jank_frames[:5], 1):
                lines.append(
                    f"{i}. VSync#{frame['vsync']} | 超时 {frame['duration_ms']}ms | "
                    f"占用 {frame['exceed_frames']} 帧 | 等级: {frame['level']}"
                )

        if ctx.top_redundant_threads:
            lines.append("\n## 冗余线程 Top")
            for i, thread in enumerate(ctx.top_redundant_threads[:5], 1):
                lines.append(
                    f"{i}. [{thread['name']}] 冗余分={thread['score']} | 等待率={thread['wait_ratio']}% | "
                    f"浪费指令={thread['wasted_instructions_m']}M | 类型={thread['pattern']}"
                )
                if thread["callstack_top"]:
                    lines.append(f"   调用栈: {' → '.join(thread['callstack_top'])}")

        if ctx.ipc_binder:
            lines.append("\n## IPC/Binder 高频调用")
            for call in ctx.ipc_binder:
                lines.append(f"- {call}")

        return "\n".join(lines)
