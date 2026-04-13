from __future__ import annotations

import json
import re
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


_UI_NAME_RE = re.compile(r"\b[A-Z][A-Za-z0-9_]*(?:Page|View|Component|WebView|Container|Wrapper)\b")
_CAMEL_TOKEN_RE = re.compile(r"[A-Z]+(?=[A-Z][a-z]|\d|$)|[A-Z]?[a-z]+|\d+")
_SOURCE_LOC_RE = re.compile(
    r"^(?P<symbol_name>.+?):\[url:(?P<meta>.*)\|(?P<source>src/main/(?:ets|js)/.+?):(?P<line>\d+):(?P<column>\d+)\]$"
)

_GENERIC_UI_NAMES = {
    "ArrayList",
    "BatteryComponent",
    "ClockStatusView",
    "GetDrawCmdList",
    "JsView",
    "PixelMap",
    "SignalComponent",
    "StatusBarBridgeView",
    "StatusBarIconItemRingModeComponent",
    "StatusBarView",
    "StatusBarView_LiveCapsuleList",
    "SymbolColorList",
}

_SYSTEM_UI_PREFIXES = (
    "StatusBar",
    "Battery",
    "Clock",
    "Signal",
)

_VSYNC_SYMBOL_HINTS = (
    "OH_NativeVSync_RequestFrame",
    "RequestNextVSync",
    "VSyncCallBackListener::OnReadable",
    "VsyncCallbackInner",
)

_JS_LOOP_SYMBOL_HINTS = (
    "uv_run",
    "libuv",
)

_PAGE_NAME_RE = re.compile(r'"pageName":"([^"]+)"')
_UI_RUNTIME_ANCHOR_NAMES = (
    "JdHome",
    "TopTabContainer",
    "MainTabContainer",
    "TnFloorView",
    "HomeTnViewWrapper",
    "RecommendProductListView",
    "SecondFloorH5Container",
    "WaterFlow",
    "JDHybridPage",
)

_UI_RUNTIME_PRIORITY = {
    "JdHome": 120,
    "HomeTnViewWrapper": 110,
    "TnFloorView": 108,
    "RecommendProductListView": 106,
    "TopTabContainer": 104,
    "MainTabContainer": 102,
    "SecondFloorH5Container": 100,
    "WaterFlow": 70,
    "JDHybridPage": 70,
}

_UI_NOISY_RUNTIME_NAMES = {
    "unknown",
    "SearchTnContainerView",
}


class EmptyFrameEvidenceExtractor:
    def __init__(self, report_dir: str | Path, top_n: int = 5):
        self.report_dir = Path(report_dir)
        self.top_n = top_n

    def build(self) -> dict[str, Any]:
        data = self._read_json("trace_emptyFrame.json")
        if not isinstance(data, dict) or not data:
            raise FileNotFoundError(f"未找到有效的 trace_emptyFrame.json: {self.report_dir}")

        step_id = sorted(data.keys())[0]
        step_data = data.get(step_id, {})
        if not isinstance(step_data, dict):
            raise ValueError(f"trace_emptyFrame.json 中的 step 数据格式异常: {step_id}")

        summary = step_data.get("summary", {}) if isinstance(step_data.get("summary"), dict) else {}
        threads = step_data.get("thread_statistics", {}).get("top_threads", [])
        frames = step_data.get("top_frames", [])

        dominant_threads = [self._normalize_thread(item) for item in threads[: self.top_n] if isinstance(item, dict)]
        representative_frames = [self._normalize_frame(item) for item in frames[: self.top_n] if isinstance(item, dict)]
        ui_snapshot_hints = self._extract_ui_snapshot_hints(step_id)
        proc_source_hints = self._collect_proc_source_hints(step_id, representative_frames)
        signals = self._derive_signals(summary, dominant_threads, representative_frames, ui_snapshot_hints, proc_source_hints)
        hypotheses = self._build_hypotheses(
            summary,
            dominant_threads,
            representative_frames,
            ui_snapshot_hints,
            proc_source_hints,
            signals,
        )
        caveats = self._build_caveats(summary, representative_frames, ui_snapshot_hints, proc_source_hints)

        return {
            "checker": "empty-frame",
            "step_id": step_id,
            "overview": {
                "total_empty_frames": self._safe_int(summary.get("total_empty_frames")),
                "empty_frame_percentage": round(self._safe_float(summary.get("empty_frame_percentage")), 2),
                "severity_level": summary.get("severity_level", "unknown"),
                "main_thread_load": self._safe_int(summary.get("main_thread_load")),
                "main_thread_percentage_in_empty_frame": round(
                    self._safe_float(summary.get("main_thread_percentage_in_empty_frame")), 2
                ),
                "background_thread_load": self._safe_int(summary.get("background_thread_load")),
                "background_thread_percentage_in_empty_frame": round(
                    self._safe_float(summary.get("background_thread_percentage_in_empty_frame")), 2
                ),
                "detection_breakdown": summary.get("detection_breakdown", {}),
                "rs_trace_stats": summary.get("rs_trace_stats", {}),
                "empty_frame_load": self._safe_int(summary.get("empty_frame_load")),
                "total_load": self._safe_int(summary.get("total_load")),
            },
            "dominant_threads": dominant_threads,
            "representative_frames": representative_frames,
            "ui_snapshot_hints": ui_snapshot_hints,
            "proc_source_hints": proc_source_hints,
            "signals": signals,
            "hypotheses": hypotheses,
            "caveats": caveats,
        }

    def _read_json(self, filename: str) -> dict | list | None:
        path = self.report_dir / filename
        if not path.exists():
            return None
        with path.open(encoding="utf-8") as handle:
            return json.load(handle)

    @staticmethod
    def _safe_float(value: Any, default: float = 0.0) -> float:
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

    @staticmethod
    def _safe_int(value: Any, default: int = 0) -> int:
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _camel_tokens(text: str) -> list[str]:
        return [token.lower() for token in _CAMEL_TOKEN_RE.findall(text or "") if token]

    def _classify_thread(self, thread_name: str, process_name: str) -> str:
        lowered = (thread_name or "").lower()
        if thread_name and process_name and thread_name == process_name:
            return "app_main"
        if "taro_js" in lowered or lowered.startswith("js") or lowered.endswith("_js"):
            return "js_runtime"
        if "vsync" in lowered:
            return "vsync"
        if lowered == "element":
            return "element_runtime"
        if "gc" in lowered:
            return "gc"
        if lowered.startswith("os_ffrt"):
            return "ffrt_worker"
        return "background"

    def _normalize_thread(self, thread: dict[str, Any]) -> dict[str, Any]:
        thread_name = str(thread.get("thread_name", "") or "")
        process_name = str(thread.get("process_name", "") or "")
        role = self._classify_thread(thread_name, process_name)
        notes: list[str] = []

        if role == "app_main":
            notes.append("应用主线程直接参与空刷负载")
        elif role == "js_runtime":
            notes.append("JS/Taro 运行线程参与空刷链路")
        elif role == "vsync":
            notes.append("VSync 调度线程参与唤醒链")
        elif role == "element_runtime":
            notes.append("ArkUI element 侧存在持续活动")

        return {
            "thread_name": thread_name,
            "process_name": process_name,
            "thread_id": self._safe_int(thread.get("thread_id") or thread.get("tid")),
            "total_load": self._safe_int(thread.get("total_load")),
            "percentage": round(self._safe_float(thread.get("percentage")), 2),
            "role": role,
            "notes": notes,
        }

    def _normalize_frame(self, frame: dict[str, Any]) -> dict[str, Any]:
        sample_callchains = frame.get("sample_callchains", []) if isinstance(frame.get("sample_callchains"), list) else []
        wakeup_threads = frame.get("wakeup_threads", []) if isinstance(frame.get("wakeup_threads"), list) else []
        normalized_callchains = self._normalize_callchains(sample_callchains)
        symbol_hints = self._collect_symbol_hints(normalized_callchains)
        proc_hits = self._collect_proc_hits_from_callchains(
            normalized_callchains,
            frame_vsync=frame.get("vsync"),
            frame_thread_name=frame.get("thread_name", "unknown"),
        )

        return {
            "vsync": frame.get("vsync"),
            "flag": frame.get("flag"),
            "thread_name": frame.get("thread_name", "unknown"),
            "process_name": frame.get("process_name", "unknown"),
            "frame_load": self._safe_int(frame.get("frame_load")),
            "dur_ms": round(self._safe_float(frame.get("dur")) / 1_000_000, 2),
            "is_main_thread": bool(frame.get("is_main_thread")),
            "sample_callchains": normalized_callchains,
            "sample_callchains_count": self._safe_int(frame.get("sample_callchains_count")),
            "wakeup_threads": [
                {
                    "thread_name": item.get("thread_name", "unknown"),
                    "process_name": item.get("process_name", "unknown"),
                    "wakeup_depth": self._safe_int(item.get("wakeup_depth")),
                    "is_system_thread": bool(item.get("is_system_thread")),
                }
                for item in wakeup_threads[:5]
                if isinstance(item, dict)
            ],
            "symbol_hints": symbol_hints,
            "proc_source_hits": proc_hits,
            "perf_proc_source_hits": [],
        }

    def _normalize_callchains(self, sample_callchains: list[dict[str, Any]]) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        for item in sample_callchains[:3]:
            if not isinstance(item, dict):
                continue
            callchain = item.get("callchain", []) if isinstance(item.get("callchain"), list) else []
            symbols = []
            proc_source_hits = []
            seen_proc_hits: set[tuple[str, int, int, str]] = set()
            for node in callchain:
                if not isinstance(node, dict):
                    continue
                symbol = str(node.get("symbol", "") or "")
                path = str(node.get("path", "") or "")
                if symbol and symbol != "unknown":
                    symbols.append(symbol)
                hit = self._parse_proc_source_hit(path, symbol)
                if hit is None:
                    continue
                key = (hit["source_path"], hit["line"], hit["column"], hit["symbol_name"])
                if key in seen_proc_hits:
                    continue
                seen_proc_hits.add(key)
                proc_source_hits.append(hit)

            deduped_symbols = []
            for symbol in symbols:
                if symbol not in deduped_symbols:
                    deduped_symbols.append(symbol)
            normalized.append(
                {
                    "thread_name": item.get("thread_name", "unknown"),
                    "thread_id": self._safe_int(item.get("thread_id")),
                    "timestamp": self._safe_int(item.get("timestamp")),
                    "event_count": self._safe_int(item.get("event_count")),
                    "load_percentage": round(self._safe_float(item.get("load_percentage")), 2),
                    "symbols": deduped_symbols[:8],
                    "proc_source_hits": proc_source_hits[:10],
                }
            )
        return normalized

    @staticmethod
    def _collect_symbol_hints(callchains: list[dict[str, Any]]) -> list[str]:
        ordered: list[str] = []
        for callchain in callchains:
            for symbol in callchain.get("symbols", []):
                if any(hint in symbol for hint in _VSYNC_SYMBOL_HINTS + _JS_LOOP_SYMBOL_HINTS):
                    if symbol not in ordered:
                        ordered.append(symbol)
        return ordered[:8]

    def _parse_proc_source_hit(self, path: str, symbol: str) -> dict[str, Any] | None:
        if not path or "/proc/" not in path:
            return None
        if not symbol or symbol == "unknown":
            return None
        matched = _SOURCE_LOC_RE.match(symbol.strip())
        if matched is None:
            return None
        source_path = matched.group("source")
        symbol_name = matched.group("symbol_name").strip()
        meta = matched.group("meta")
        return {
            "bundle_path": path,
            "source_path": source_path,
            "line": self._safe_int(matched.group("line")),
            "column": self._safe_int(matched.group("column")),
            "symbol_name": symbol_name,
            "owner_name": self._infer_owner_name(source_path, symbol_name),
            "package_name": self._extract_package_name(meta),
            "raw_symbol": symbol,
            "source_type": self._classify_source_type(source_path),
        }

    @staticmethod
    def _extract_package_name(meta: str) -> str:
        parts = [item for item in str(meta or "").split("|") if item]
        for item in parts:
            if item.startswith("@"):
                return item
        return parts[0] if parts else "unknown"

    @staticmethod
    def _classify_source_type(source_path: str) -> str:
        lowered = source_path.lower()
        if lowered.endswith(".ets") or lowered.endswith(".ts"):
            return "arkts"
        if lowered.endswith(".js"):
            return "js"
        return "unknown"

    @staticmethod
    def _infer_owner_name(source_path: str, symbol_name: str) -> str:
        path = Path(source_path)
        stem = path.stem
        if stem and stem.lower() != "index":
            return stem
        if path.parent.name:
            return path.parent.name
        return symbol_name or "unknown"

    def _collect_proc_hits_from_callchains(
        self,
        callchains: list[dict[str, Any]],
        frame_vsync: Any,
        frame_thread_name: str,
    ) -> list[dict[str, Any]]:
        collected: list[dict[str, Any]] = []
        seen: set[tuple[str, int, int, str, str]] = set()
        for callchain in callchains:
            for hit in callchain.get("proc_source_hits", []):
                enriched = {
                    **hit,
                    "via": "direct_callchain",
                    "thread_name": callchain.get("thread_name", "unknown"),
                    "thread_id": self._safe_int(callchain.get("thread_id")),
                    "sample_timestamp": self._safe_int(callchain.get("timestamp")),
                    "event_count": self._safe_int(callchain.get("event_count")),
                    "load_percentage": round(self._safe_float(callchain.get("load_percentage")), 2),
                    "frame_vsync": frame_vsync,
                    "frame_thread_name": frame_thread_name,
                }
                key = (
                    enriched["source_path"],
                    enriched["line"],
                    enriched["column"],
                    enriched["symbol_name"],
                    enriched["thread_name"],
                )
                if key in seen:
                    continue
                seen.add(key)
                collected.append(enriched)
        return collected[:16]

    def _extract_ui_snapshot_hints(self, step_id: str) -> list[dict[str, Any]]:
        ui_root = self.report_dir.parent / "ui" / step_id
        if not ui_root.exists():
            return []

        counts: Counter[str] = Counter()
        sources: dict[str, set[str]] = defaultdict(set)
        page_names: Counter[str] = Counter()
        runtime_anchors: Counter[str] = Counter()

        for path in sorted(ui_root.glob("element_tree_*.txt")) + sorted(ui_root.glob("inspector_*.json")):
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue

            for page_name in _PAGE_NAME_RE.findall(text):
                page_name = page_name.strip()
                if not page_name or page_name in _UI_NOISY_RUNTIME_NAMES:
                    continue
                page_names[page_name] += 1
                sources[page_name].add(path.name)
                if page_name in _UI_RUNTIME_ANCHOR_NAMES:
                    runtime_anchors[page_name] += 1

            for name in self._extract_ui_names(text):
                if name in _UI_NOISY_RUNTIME_NAMES:
                    continue
                counts[name] += 1
                sources[name].add(path.name)
                if name in _UI_RUNTIME_ANCHOR_NAMES:
                    runtime_anchors[name] += 1

        hints: list[dict[str, Any]] = []
        for name, count in page_names.most_common(5):
            hints.append(
                {
                    "name": name,
                    "kind": "page_runtime",
                    "count": count,
                    "tokens": self._camel_tokens(name),
                    "sources": sorted(sources[name]),
                    "runtime_anchor": name in _UI_RUNTIME_ANCHOR_NAMES,
                    "priority": _UI_RUNTIME_PRIORITY.get(name, 90),
                }
            )

        min_count = 4
        for name, count in counts.most_common(24):
            if count < min_count:
                continue
            hints.append(
                {
                    "name": name,
                    "kind": self._classify_ui_name(name),
                    "count": count,
                    "tokens": self._camel_tokens(name),
                    "sources": sorted(sources[name]),
                    "runtime_anchor": name in _UI_RUNTIME_ANCHOR_NAMES,
                    "priority": _UI_RUNTIME_PRIORITY.get(name, 0),
                }
            )
            if len(hints) >= 18:
                break

        if runtime_anchors:
            anchors = []
            for name, count in runtime_anchors.most_common(len(_UI_RUNTIME_ANCHOR_NAMES)):
                anchors.append(
                    {
                        "name": name,
                        "kind": "page_runtime" if name == "JdHome" else self._classify_ui_name(name),
                        "count": count,
                        "tokens": self._camel_tokens(name),
                        "sources": sorted(sources[name]),
                        "runtime_anchor": True,
                        "priority": _UI_RUNTIME_PRIORITY.get(name, 0),
                    }
                )
            hints = self._merge_ui_hints(hints + anchors)
        else:
            hints = self._merge_ui_hints(hints)

        return hints[:12]

    @staticmethod
    def _merge_ui_hints(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        merged: dict[str, dict[str, Any]] = {}
        order: list[str] = []
        for item in items:
            name = str(item.get("name", "") or "")
            if not name:
                continue
            if name not in merged:
                merged[name] = {
                    **item,
                    "count": int(item.get("count", 0) or 0),
                    "sources": list(item.get("sources", [])),
                    "runtime_anchor": bool(item.get("runtime_anchor")),
                    "priority": int(item.get("priority", 0) or 0),
                }
                order.append(name)
                continue

            merged[name]["count"] = max(int(merged[name].get("count", 0) or 0), int(item.get("count", 0) or 0))
            merged[name]["sources"] = sorted(set(merged[name].get("sources", [])) | set(item.get("sources", [])))
            merged[name]["runtime_anchor"] = bool(merged[name].get("runtime_anchor")) or bool(item.get("runtime_anchor"))
            merged[name]["priority"] = max(int(merged[name].get("priority", 0) or 0), int(item.get("priority", 0) or 0))
            if merged[name].get("kind") in {"unknown", "view", "component"} and item.get("kind"):
                merged[name]["kind"] = item.get("kind")

        ordered = [merged[name] for name in order]
        ordered.sort(
            key=lambda x: (
                -int(x.get("priority", 0) or 0),
                0 if x.get("kind") == "page_runtime" else 1 if x.get("runtime_anchor") else 2,
                -int(x.get("count", 0) or 0),
                x.get("name", ""),
            )
        )
        return ordered

    def _extract_ui_names(self, text: str) -> list[str]:
        results = []
        for name in _UI_NAME_RE.findall(text):
            if name in _GENERIC_UI_NAMES:
                continue
            if any(name.startswith(prefix) for prefix in _SYSTEM_UI_PREFIXES):
                continue
            if name.startswith("OHOS"):
                continue
            results.append(name)
        return results

    @staticmethod
    def _classify_ui_name(name: str) -> str:
        if name.endswith("Page"):
            return "page"
        if name.endswith("Container"):
            return "container"
        if name.endswith("Wrapper"):
            return "wrapper"
        if name.endswith("Component"):
            return "component"
        if name.endswith("View") or name.endswith("WebView"):
            return "view"
        return "unknown"

    def _perf_db_path(self, step_id: str) -> Path:
        return self.report_dir.parent / "hiperf" / step_id / "perf.db"

    def _collect_proc_source_hints(self, step_id: str, representative_frames: list[dict[str, Any]]) -> list[dict[str, Any]]:
        self._enrich_frames_with_perf_proc_hits(step_id, representative_frames)

        aggregated: dict[str, dict[str, Any]] = {}
        for frame in representative_frames:
            combined_hits = list(frame.get("proc_source_hits", [])) + list(frame.get("perf_proc_source_hits", []))
            merged_frame_hits: list[dict[str, Any]] = []
            frame_seen: set[tuple[str, int, int, str, str]] = set()

            for hit in combined_hits:
                frame_key = (
                    hit.get("source_path", ""),
                    self._safe_int(hit.get("line")),
                    self._safe_int(hit.get("column")),
                    hit.get("symbol_name", ""),
                    hit.get("thread_name", ""),
                )
                if frame_key not in frame_seen:
                    frame_seen.add(frame_key)
                    merged_frame_hits.append(hit)

                source_path = hit.get("source_path", "")
                if not source_path:
                    continue
                bucket = aggregated.setdefault(
                    source_path,
                    {
                        "owner_name": hit.get("owner_name", "unknown"),
                        "source_path": source_path,
                        "source_type": hit.get("source_type", "unknown"),
                        "packages": set(),
                        "symbols": set(),
                        "lines": set(),
                        "frame_vsyncs": set(),
                        "thread_names": set(),
                        "via": set(),
                        "bundle_paths": set(),
                        "hit_count": 0,
                        "direct_hit_count": 0,
                        "perf_hit_count": 0,
                        "min_delta_ns": None,
                    },
                )
                bucket["hit_count"] += 1
                if hit.get("via") == "direct_callchain":
                    bucket["direct_hit_count"] += 1
                if hit.get("via") == "perf_nearby":
                    bucket["perf_hit_count"] += 1
                if hit.get("package_name"):
                    bucket["packages"].add(hit["package_name"])
                if hit.get("symbol_name"):
                    bucket["symbols"].add(hit["symbol_name"])
                if hit.get("line"):
                    bucket["lines"].add(self._safe_int(hit.get("line")))
                if hit.get("frame_vsync") is not None:
                    bucket["frame_vsyncs"].add(str(hit.get("frame_vsync")))
                if hit.get("thread_name"):
                    bucket["thread_names"].add(hit["thread_name"])
                if hit.get("via"):
                    bucket["via"].add(hit["via"])
                if hit.get("bundle_path"):
                    bucket["bundle_paths"].add(hit["bundle_path"])
                delta_ns = hit.get("delta_ns")
                if delta_ns is not None:
                    delta_ns = self._safe_int(delta_ns)
                    if bucket["min_delta_ns"] is None or delta_ns < bucket["min_delta_ns"]:
                        bucket["min_delta_ns"] = delta_ns

            frame["all_proc_source_hits"] = merged_frame_hits[:20]

        hints: list[dict[str, Any]] = []
        for item in aggregated.values():
            packages = sorted(item["packages"])
            symbols = sorted(item["symbols"])
            source_path = item["source_path"]
            score = self._score_proc_source_hint(
                source_path=source_path,
                owner_name=item["owner_name"],
                packages=packages,
                symbols=symbols,
                direct_hit_count=item["direct_hit_count"],
                perf_hit_count=item["perf_hit_count"],
                hit_count=item["hit_count"],
                frame_vsync_count=len(item["frame_vsyncs"]),
            )
            hints.append(
                {
                    "owner_name": item["owner_name"],
                    "source_path": source_path,
                    "source_type": item["source_type"],
                    "packages": packages,
                    "symbols": symbols,
                    "lines": sorted(item["lines"]),
                    "frame_vsyncs": sorted(item["frame_vsyncs"]),
                    "thread_names": sorted(item["thread_names"]),
                    "via": sorted(item["via"]),
                    "bundle_paths": sorted(item["bundle_paths"]),
                    "hit_count": item["hit_count"],
                    "direct_hit_count": item["direct_hit_count"],
                    "perf_hit_count": item["perf_hit_count"],
                    "min_delta_ns": item["min_delta_ns"],
                    "score": score,
                }
            )

        return sorted(
            hints,
            key=lambda x: (
                -self._safe_int(x.get("score")),
                -self._safe_int(x.get("direct_hit_count")),
                -self._safe_int(x.get("hit_count")),
                x.get("source_path", ""),
            ),
        )[:12]

    def _enrich_frames_with_perf_proc_hits(self, step_id: str, representative_frames: list[dict[str, Any]]) -> None:
        perf_db = self._perf_db_path(step_id)
        if not perf_db.exists():
            return

        try:
            conn = sqlite3.connect(perf_db)
        except sqlite3.Error:
            return

        try:
            for frame in representative_frames:
                frame_hits: list[dict[str, Any]] = []
                seen: set[tuple[int, str, int, int, str, str]] = set()
                for callchain in frame.get("sample_callchains", [])[:3]:
                    thread_id = self._safe_int(callchain.get("thread_id"))
                    timestamp = self._safe_int(callchain.get("timestamp"))
                    if not thread_id or not timestamp:
                        continue

                    sample_rows = conn.execute(
                        """
                        select callchain_id, abs(timeStamp - ?) as delta_ns, event_count
                        from perf_sample
                        where thread_id = ?
                        order by abs(timeStamp - ?) asc
                        limit 6
                        """,
                        (timestamp, thread_id, timestamp),
                    ).fetchall()

                    for callchain_id, delta_ns, event_count in sample_rows:
                        delta_ns = self._safe_int(delta_ns)
                        if delta_ns > 5_000_000:
                            continue
                        call_rows = conn.execute(
                            """
                            select c.depth, c.line_number, f.path, f.symbol
                            from perf_callchain c
                            left join perf_files f on f.file_id = c.file_id and f.serial_id = c.symbol_id
                            where c.callchain_id = ?
                            order by c.depth asc
                            """,
                            (callchain_id,),
                        ).fetchall()
                        for depth, line_number, path, symbol in call_rows:
                            hit = self._parse_proc_source_hit(str(path or ""), str(symbol or ""))
                            if hit is None:
                                continue
                            key = (
                                self._safe_int(callchain_id),
                                hit["source_path"],
                                hit["line"],
                                hit["column"],
                                hit["symbol_name"],
                                str(callchain.get("thread_name", "unknown")),
                            )
                            if key in seen:
                                continue
                            seen.add(key)
                            frame_hits.append(
                                {
                                    **hit,
                                    "via": "perf_nearby",
                                    "thread_name": callchain.get("thread_name", "unknown"),
                                    "thread_id": thread_id,
                                    "sample_timestamp": timestamp,
                                    "event_count": self._safe_int(event_count),
                                    "delta_ns": delta_ns,
                                    "callchain_id": self._safe_int(callchain_id),
                                    "depth": self._safe_int(depth),
                                    "db_line_number": self._safe_int(line_number),
                                    "frame_vsync": frame.get("vsync"),
                                    "frame_thread_name": frame.get("thread_name", "unknown"),
                                }
                            )
                frame["perf_proc_source_hits"] = frame_hits[:20]
        finally:
            conn.close()

    def _derive_signals(
        self,
        summary: dict[str, Any],
        dominant_threads: list[dict[str, Any]],
        representative_frames: list[dict[str, Any]],
        ui_snapshot_hints: list[dict[str, Any]],
        proc_source_hints: list[dict[str, Any]],
    ) -> dict[str, Any]:
        wakeup_names = {
            item.get("thread_name", "")
            for frame in representative_frames
            for item in frame.get("wakeup_threads", [])
            if isinstance(item, dict)
        }
        symbol_hints = [symbol for frame in representative_frames for symbol in frame.get("symbol_hints", [])]
        ui_names = [item.get("name", "") for item in ui_snapshot_hints]
        ui_names_lower = [name.lower() for name in ui_names]
        proc_owner_names = [item.get("owner_name", "") for item in proc_source_hints]
        proc_haystacks = [
            " ".join(
                [
                    item.get("owner_name", ""),
                    item.get("source_path", ""),
                    " ".join(item.get("symbols", [])),
                    " ".join(item.get("packages", [])),
                ]
            ).lower()
            for item in proc_source_hints
        ]

        direct_only = self._safe_int(summary.get("detection_breakdown", {}).get("direct_only"))
        total_empty = max(self._safe_int(summary.get("total_empty_frames")), 1)

        return {
            "dominant_main_thread": self._safe_float(summary.get("main_thread_percentage_in_empty_frame")) >= 45,
            "has_taro_js": any(item.get("role") == "js_runtime" for item in dominant_threads),
            "has_element_thread": any(item.get("role") == "element_runtime" for item in dominant_threads),
            "has_vsync_loop": bool(
                "OS_VSyncThread" in wakeup_names or any(any(hint in symbol for hint in _VSYNC_SYMBOL_HINTS) for symbol in symbol_hints)
            ),
            "has_uv_loop": any(any(hint in symbol for hint in _JS_LOOP_SYMBOL_HINTS) for symbol in symbol_hints),
            "direct_detection_dominant": direct_only / total_empty >= 0.8,
            "ui_has_web_or_hybrid": any(any(token in name for token in ("web", "hybrid")) for name in ui_names_lower),
            "ui_has_list_or_product": any(any(token in name for token in ("list", "product", "search", "recommend")) for name in ui_names_lower),
            "ui_has_map": any("map" in name for name in ui_names_lower),
            "ui_has_home_runtime": any(name in ui_names for name in ("JdHome", "TopTabContainer", "MainTabContainer", "HomeTnViewWrapper", "TnFloorView", "RecommendProductListView")),
            "has_proc_user_sources": bool(proc_source_hints),
            "proc_owner_names": proc_owner_names,
            "proc_has_list_or_product": any(
                any(token in haystack for token in ("search", "list", "product", "skeleton", "card", "container", "recommend", "tn"))
                for haystack in proc_haystacks
            ),
            "proc_has_web_or_hybrid": any(any(token in haystack for token in ("web", "hybrid")) for haystack in proc_haystacks),
            "proc_has_animation": any(any(token in haystack for token in ("animation", "lottie", "skeleton")) for haystack in proc_haystacks),
            "ui_names": ui_names,
        }

    def _build_hypotheses(
        self,
        summary: dict[str, Any],
        dominant_threads: list[dict[str, Any]],
        representative_frames: list[dict[str, Any]],
        ui_snapshot_hints: list[dict[str, Any]],
        proc_source_hints: list[dict[str, Any]],
        signals: dict[str, Any],
    ) -> list[dict[str, Any]]:
        hypotheses: list[dict[str, Any]] = []
        total_empty = self._safe_int(summary.get("total_empty_frames"))
        empty_rate = round(self._safe_float(summary.get("empty_frame_percentage")), 2)
        main_pct = round(self._safe_float(summary.get("main_thread_percentage_in_empty_frame")), 2)
        breakdown = summary.get("detection_breakdown", {})
        rs_stats = summary.get("rs_trace_stats", {})
        top_ui_names = [item["name"] for item in ui_snapshot_hints[:8]]
        list_ui_names = [name for name in top_ui_names if any(token in name.lower() for token in ("list", "product", "search", "recommend", "tn", "container"))]
        web_ui_names = [name for name in top_ui_names if any(token in name.lower() for token in ("web", "hybrid"))]
        map_ui_names = [name for name in top_ui_names if "map" in name.lower()]
        home_ui_names = [
            name
            for name in top_ui_names
            if any(
                token in name.lower()
                for token in ("home", "recommend", "tn", "tabcontainer", "waterflow", "secondfloor", "jdhome")
            )
        ]

        proc_list_hits = self._select_proc_source_scope(
            proc_source_hints, ("search", "list", "product", "skeleton", "card", "container")
        )
        proc_web_hits = self._select_proc_source_scope(proc_source_hints, ("web", "hybrid"))
        proc_animation_hits = self._select_proc_source_scope(proc_source_hints, ("animation", "lottie", "skeleton"))
        proc_general_hits = proc_source_hints[:5]
        proc_owner_names = [item.get("owner_name", "") for item in proc_source_hints[:8] if item.get("owner_name")]
        owner_pool = list(
            dict.fromkeys(top_ui_names + proc_owner_names + ["WebviewPage", "CommodityListPage", "IndexHomePage", "MapPage"])
        )

        if signals.get("dominant_main_thread") or signals.get("has_taro_js") or signals.get("has_vsync_loop"):
            evidence = [
                f"空刷总数 {total_empty}，占比 {empty_rate}% ，严重度 {summary.get('severity_level', 'unknown')}。",
                f"空刷负载中主线程占比 {main_pct}% 。",
                f"检测拆分 direct_only={self._safe_int(breakdown.get('direct_only'))}、rs_traced_only={self._safe_int(breakdown.get('rs_traced_only'))}、both={self._safe_int(breakdown.get('both'))}。",
            ]
            if signals.get("has_taro_js"):
                taro = next((item for item in dominant_threads if item.get("role") == "js_runtime"), None)
                if taro:
                    evidence.append(
                        f"线程 {taro['thread_name']} 在空刷负载中占比 {taro['percentage']}%，说明 JS/Taro 事件循环持续参与。"
                    )
            if representative_frames:
                first_frame = representative_frames[0]
                chain_notes = [item.get("thread_name") for item in first_frame.get("wakeup_threads", []) if item.get("thread_name")]
                if chain_notes:
                    evidence.append(f"代表帧 VSync#{first_frame.get('vsync')} 的唤醒链包含 {' -> '.join(chain_notes)}。")
                if first_frame.get("symbol_hints"):
                    evidence.append(f"代表帧命中符号 {', '.join(first_frame['symbol_hints'][:4])}。")
            if proc_general_hits:
                evidence.append(
                    "代表帧/邻近 perf sample 命中 /proc 用户态源码 "
                    + "、".join(self._format_proc_hint_brief(item) for item in proc_general_hits[:3])
                    + "。"
                )

            candidate_sources = self._limit_preserving_order(proc_list_hits + proc_animation_hits + proc_web_hits + proc_general_hits, 6)
            if signals.get("ui_has_home_runtime") and home_ui_names:
                evidence.append("UI dump 明确落在 " + "、".join(home_ui_names[:6]) + " 等首页/TN/推荐流组件上。")
            hypotheses.append(
                {
                    "id": "js_vsync_loop",
                    "title": "JS/Taro 驱动的持续刷新链导致主线程反复空刷",
                    "priority": 1,
                    "confidence": "high" if signals.get("has_taro_js") and signals.get("has_vsync_loop") else "medium",
                    "evidence": evidence,
                    "inference": (
                        "空刷不是单次重计算，更像是 JS 事件循环与 VSync 请求链反复触发无效刷新；"
                        "结合 UI dump，当前更像发生在首页 TN 容器链或推荐流复用链，而不是只看源码命名就断言为独立搜索页。"
                    ),
                    "candidate_source_scope": candidate_sources,
                    "code_query": {
                        "owner_keywords": owner_pool,
                        "module_keywords": ["webview", "hybrid", "search", "product", "list", "commodity", "home", "map", "recommend", "tn"],
                        "ui_keywords": ["LazyForEach", "WaterFlow", "List", "Scroll"],
                        "symbol_keywords": ["aboutToAppear", "onPageShow", "initialRender", "build", "createContainer"],
                    },
                    "fix_direction": [
                        "优先检查 /proc 命中的源码入口，确认这些回调在页面静止时是否仍持续更新状态。",
                        "检查当前页面是否存在 timer/requestAnimationFrame/轮询任务在页面静止时仍持续触发。",
                        "检查 JS->ArkUI 桥接回调是否在没有视觉变化时仍更新状态。",
                    ],
                }
            )

        if signals.get("ui_has_list_or_product") or signals.get("proc_has_list_or_product"):
            evidence = [
                f"UI 快照中出现 {', '.join(list_ui_names[:5]) or '列表/商品页组件'} 等列表相关页面/组件名。",
                f"空刷样本中主线程空刷负载占比 {main_pct}%，说明渲染树侧持续被业务页面驱动。",
            ]
            if signals.get("ui_has_home_runtime") and home_ui_names:
                evidence.append("当前 UI dump 同时出现 " + "、".join(home_ui_names[:6]) + "，说明这些列表/商品能力更可能挂在首页推荐流/TN 区域中。")
            if signals.get("direct_detection_dominant"):
                evidence.append("direct_only 占主导，说明多数空刷是直接观测到的无效刷新，而非仅靠 RS 反向追溯。")
            if proc_list_hits:
                evidence.append(
                    "`/proc` 用户态源码命中 " + "、".join(self._format_proc_hint_brief(item) for item in proc_list_hits[:4]) + "。"
                )
            hypotheses.append(
                {
                    "id": "list_rebuild",
                    "title": "列表页/瀑布流区域存在持续重建或数据抖动",
                    "priority": 2,
                    "confidence": "high" if proc_list_hits else "medium",
                    "evidence": evidence,
                    "inference": (
                        "若 `SearchTnContainerView`、`ProductListView`、`SkeletonScreenView` 等源码在空刷代表帧附近反复出现，"
                        "结合当前 UI dump，更像是首页推荐流、TN 容器或复用商品流里的容器创建、卡片构建、骨架屏动画或无差异数据写回导致的持续刷新。"
                    ),
                    "candidate_source_scope": proc_list_hits[:6],
                    "code_query": {
                        "owner_keywords": list(
                            dict.fromkeys(
                                list_ui_names
                                + home_ui_names
                                + [item.get("owner_name", "") for item in proc_list_hits]
                                + ["CommodityListPage", "WaterFlowComponent", "SearchProductListPage", "RecommendProductListView", "HomeTnViewWrapper", "TnFloorView"]
                            )
                        ),
                        "module_keywords": ["commodity", "product", "search", "list", "feed", "recommend", "skeleton", "home", "tn"],
                        "ui_keywords": ["WaterFlow", "LazyForEach", "List", "Scroll", "ForEach"],
                        "symbol_keywords": ["initialRender", "build", "aboutToAppear", "createContainer", "handleTnData"],
                    },
                    "fix_direction": [
                        "检查列表数据源是否在无差异时重复赋值。",
                        "检查瀑布流/懒加载列表 item、卡片容器、骨架屏是否因外层状态变化被整段重建。",
                        "检查曝光、滚动、埋点回调是否把高频事件直接写回 UI 状态。",
                    ],
                }
            )

        if signals.get("ui_has_web_or_hybrid") or signals.get("has_uv_loop") or signals.get("proc_has_web_or_hybrid"):
            evidence = [
                f"UI 快照中出现 {', '.join(web_ui_names[:5]) or 'Web/Hybrid 组件'}。",
                f"RS 反向追溯成功 {self._safe_int(rs_stats.get('traced_success_count'))}/{self._safe_int(rs_stats.get('total_skip_frames'))}，trace_accuracy={round(self._safe_float(rs_stats.get('trace_accuracy')), 2)}%。",
            ]
            if signals.get("has_uv_loop"):
                evidence.append("代表帧 callchain 中出现 uv_run，表明页面中存在 libuv/JS 事件循环活动。")
            if proc_web_hits:
                evidence.append("`/proc` 用户态源码命中 " + "、".join(self._format_proc_hint_brief(item) for item in proc_web_hits[:3]) + "。")
            hypotheses.append(
                {
                    "id": "webview_hybrid_refresh",
                    "title": "Web/Hybrid 容器页面持续向 ArkUI 请求刷新",
                    "priority": 3,
                    "confidence": "medium",
                    "evidence": evidence,
                    "inference": (
                        "若当前场景是 Web/Hybrid 容器，空刷更可能来自 H5/JS bridge、前端动画或页面轮询，"
                        "而不是纯 ArkUI 静态页面。"
                    ),
                    "candidate_source_scope": proc_web_hits[:6],
                    "code_query": {
                        "owner_keywords": list(dict.fromkeys(web_ui_names + [item.get("owner_name", "") for item in proc_web_hits] + ["WebviewPage", "JDWebView", "JDHybridPage"])),
                        "module_keywords": ["webview", "hybrid", "web"],
                        "ui_keywords": [],
                        "symbol_keywords": ["aboutToAppear", "onPageShow", "initialRender"],
                    },
                    "fix_direction": [
                        "检查 WebView/Hybrid 页面进入后是否立即启动持续消息同步或轮询。",
                        "检查前端动画、进度条、倒计时是否在页面静止时仍驱动桥接刷新。",
                    ],
                }
            )

        if signals.get("ui_has_map"):
            hypotheses.append(
                {
                    "id": "map_refresh",
                    "title": "地图/XComponent 页面存在持续位置或视野刷新",
                    "priority": 4,
                    "confidence": "medium",
                    "evidence": [f"UI 快照中出现 {', '.join(map_ui_names[:5])} 等地图相关名称。"],
                    "inference": "地图类页面常见问题是定位、标点刷新或相机状态同步持续触发无效渲染。",
                    "candidate_source_scope": self._select_proc_source_scope(proc_source_hints, ("map", "location", "poi"))[:6],
                    "code_query": {
                        "owner_keywords": list(dict.fromkeys(map_ui_names + ["MapPage", "MapComponent"])),
                        "module_keywords": ["map", "poi", "location"],
                        "ui_keywords": ["XComponent"],
                        "symbol_keywords": ["aboutToAppear", "initialRender"],
                    },
                    "fix_direction": [
                        "检查地图 camera/marker 更新是否做了节流与 diff。",
                        "检查定位或视野监听在页面静止时是否仍持续写状态。",
                    ],
                }
            )

        return hypotheses

    def _select_proc_source_scope(
        self,
        proc_source_hints: list[dict[str, Any]],
        tokens: tuple[str, ...],
        limit: int = 6,
    ) -> list[dict[str, Any]]:
        matched = []
        for item in proc_source_hints:
            haystack = " ".join(
                [
                    item.get("owner_name", ""),
                    item.get("source_path", ""),
                    " ".join(item.get("symbols", [])),
                    " ".join(item.get("packages", [])),
                ]
            ).lower()
            if any(token in haystack for token in tokens):
                matched.append(item)
        return matched[:limit]

    def _score_proc_source_hint(
        self,
        source_path: str,
        owner_name: str,
        packages: list[str],
        symbols: list[str],
        direct_hit_count: int,
        perf_hit_count: int,
        hit_count: int,
        frame_vsync_count: int,
    ) -> int:
        haystack = " ".join([source_path, owner_name, " ".join(packages), " ".join(symbols)]).lower()
        score = direct_hit_count * 12 + perf_hit_count * 4 + hit_count * 2 + frame_vsync_count * 3

        if any(token in haystack for token in ("hm-search", "search", "productlist", "product", "list", "skeleton", "container", "card")):
            score += 20
        if any(token in haystack for token in ("createcontainer", "handletndata", "itemcomponent", "initialrender", "gradienthighlightanimation")):
            score += 10
        if any(token in haystack for token in ("lottie", "animationmanager", "animationitem")):
            score -= 14
        if any(token in haystack for token in ("base-network", "interceptor", "requesttask", "mobile_config", "biometric")):
            score -= 10
        if source_path.endswith(".js"):
            score -= 2
        return score

    @staticmethod
    def _limit_preserving_order(items: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
        ordered = []
        seen = set()
        for item in items:
            key = (item.get("source_path"), tuple(item.get("lines", [])), item.get("owner_name"))
            if key in seen:
                continue
            seen.add(key)
            ordered.append(item)
            if len(ordered) >= limit:
                break
        return ordered

    @staticmethod
    def _format_proc_hint_brief(item: dict[str, Any]) -> str:
        source_path = item.get("source_path", "")
        path_obj = Path(source_path) if source_path else None
        if path_obj and path_obj.name.lower() == "index.ts" and len(path_obj.parts) >= 2:
            short_name = "/".join(path_obj.parts[-2:])
        elif path_obj:
            short_name = path_obj.name
        else:
            short_name = item.get("owner_name", "unknown")
        lines = "/".join(str(line) for line in item.get("lines", [])[:3])
        return f"{short_name}:{lines}" if lines else short_name

    def _build_caveats(
        self,
        summary: dict[str, Any],
        representative_frames: list[dict[str, Any]],
        ui_snapshot_hints: list[dict[str, Any]],
        proc_source_hints: list[dict[str, Any]],
    ) -> list[str]:
        caveats = []
        if not representative_frames:
            caveats.append("当前样本缺少 top_frames 代表帧，部分推断只能基于 summary 和线程统计。")
        if not ui_snapshot_hints:
            caveats.append("当前样本没有可用的 UI snapshot/inspector 命名线索，代码定位会更依赖反编译索引模糊匹配。")
        if not proc_source_hints:
            caveats.append("当前样本未命中可用的 `/proc` 用户态源码符号，无法直接缩到具体 ArkTS/JS 源码行，只能依赖 UI 快照和索引规则。")
        rs_accuracy = self._safe_float(summary.get("rs_trace_stats", {}).get("trace_accuracy"))
        if rs_accuracy and rs_accuracy < 80:
            caveats.append("RS 反向追溯精度不高，涉及 RS skip 的结论应视为补充证据而非唯一依据。")
        caveats.append("候选代码范围表示优先排查区域，不代表已确认唯一根因。")
        return caveats
