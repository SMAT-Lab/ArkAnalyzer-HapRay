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

# Generic system-UI names to filter out (not app-specific)
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

# Generic lifecycle / rendering entry points that are high-signal for empty frames
_LIFECYCLE_SYMBOLS = (
    "abouttoappear",
    "initialrender",
    "onpageshow",
    "build",
    "oncreate",
)

# Generic penalty: known non-UI libraries unlikely to be the rendering root cause
_PENALTY_KEYWORDS = (
    "base-network",
    "interceptor",
    "requesttask",
    "mobile_config",
    "biometric",
    "lottie",
    "animationmanager",
    "animationitem",
)


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

        for path in sorted(ui_root.glob("element_tree_*.txt")) + sorted(ui_root.glob("inspector_*.json")):
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue

            for page_name in _PAGE_NAME_RE.findall(text):
                page_name = page_name.strip()
                if not page_name or page_name == "unknown":
                    continue
                page_names[page_name] += 1
                sources[page_name].add(path.name)

            for name in self._extract_ui_names(text):
                counts[name] += 1
                sources[name].add(path.name)

        hints: list[dict[str, Any]] = []
        for name, count in page_names.most_common(5):
            hints.append({
                "name": name,
                "kind": "page_runtime",
                "count": count,
                "tokens": self._camel_tokens(name),
                "sources": sorted(sources[name]),
            })

        min_count = 4
        for name, count in counts.most_common(20):
            if count < min_count:
                continue
            hints.append({
                "name": name,
                "kind": self._classify_ui_name(name),
                "count": count,
                "tokens": self._camel_tokens(name),
                "sources": sorted(sources[name]),
            })
            if len(hints) >= 16:
                break

        return self._merge_ui_hints(hints)[:12]

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
                }
                order.append(name)
            else:
                merged[name]["count"] = max(merged[name]["count"], int(item.get("count", 0) or 0))
                merged[name]["sources"] = sorted(set(merged[name]["sources"]) | set(item.get("sources", [])))
                if merged[name].get("kind") in {"unknown", "view", "component"} and item.get("kind"):
                    merged[name]["kind"] = item["kind"]

        ordered = [merged[n] for n in order]
        ordered.sort(key=lambda x: (
            0 if x.get("kind") == "page_runtime" else 1,
            -int(x.get("count", 0) or 0),
            x.get("name", ""),
        ))
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
                symbols=symbols,
                direct_hit_count=item["direct_hit_count"],
                perf_hit_count=item["perf_hit_count"],
                hit_count=item["hit_count"],
                frame_vsync_count=len(item["frame_vsyncs"]),
            )
            hints.append({
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
            })

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
                            frame_hits.append({
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
                            })
                frame["perf_proc_source_hits"] = frame_hits[:20]
        finally:
            conn.close()

    @staticmethod
    def _score_proc_source_hint(
        source_path: str,
        owner_name: str,
        symbols: list[str],
        direct_hit_count: int,
        perf_hit_count: int,
        hit_count: int,
        frame_vsync_count: int,
    ) -> int:
        score = direct_hit_count * 12 + perf_hit_count * 4 + hit_count * 2 + frame_vsync_count * 3

        # Boost generic lifecycle/rendering entry points (high signal for empty frames)
        symbols_lower = " ".join(symbols).lower()
        if any(kw in symbols_lower for kw in _LIFECYCLE_SYMBOLS):
            score += 10

        # Penalty: known non-UI libraries
        haystack = " ".join([source_path, owner_name, symbols_lower]).lower()
        if any(kw in haystack for kw in _PENALTY_KEYWORDS):
            score -= 12

        # Slight penalty for pure JS files (lower signal than ArkTS)
        if source_path.endswith(".js"):
            score -= 2

        return score

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
            caveats.append("当前样本未命中可用的 /proc 用户态源码符号，无法直接缩到具体 ArkTS/JS 源码行，只能依赖 UI 快照和索引规则。")
        rs_accuracy = self._safe_float(summary.get("rs_trace_stats", {}).get("trace_accuracy"))
        if rs_accuracy and rs_accuracy < 80:
            caveats.append("RS 反向追溯精度不高，涉及 RS skip 的结论应视为补充证据而非唯一依据。")
        caveats.append("候选代码范围表示优先排查区域，不代表已确认唯一根因。")
        return caveats

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
