"""
code_snippet_extractor.py

从反编译 .ts 文件中按行号提取代码片段，注入到 LLM 分析上下文。

设计要点：
- 大文件（>200K 行，如 0_entry.hap.ts 有 516 万行）使用稀疏字节偏移索引，
  一次 O(N) 扫描建索引，后续每次查询只需顺序读 STRIDE 行。
- 小文件全量缓存到内存（通常几十到几百 KB）。
- 单文件索引构建是懒加载（首次查询时触发）。
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any


_LIFECYCLE_RE = re.compile(
    r"\b(aboutToAppear|aboutToDisappear|onPageShow|onPageHide|"
    r"initialRender|build|rerender|aboutToBeDeleted)\b"
)
_VSYNC_HINT_RE = re.compile(
    r"\b(requestAnimationFrame|setInterval|setTimeout|"
    r"OH_NativeVSync_RequestFrame|RequestNextVSync)\b"
)
_STATE_WRITE_RE = re.compile(
    r"\bthis\.\w+\s*=\s*(?!.*\bif\b)",
)

# 超过此行数的文件使用稀疏索引而非全量缓存
_LARGE_FILE_THRESHOLD = 200_000
# 稀疏索引步长：每隔多少行存一个字节偏移
_STRIDE = 2_000


class _SparseLineIndex:
    """
    对超大文件建立稀疏字节偏移索引。
    _offsets[i] = 第 i*STRIDE+1 行在文件中的字节起始偏移。
    """

    def __init__(self, path: Path):
        self.path = path
        self._offsets: list[int] = []
        self._built = False

    def _build(self) -> None:
        offsets = [0]
        with open(self.path, "rb") as fh:
            line_num = 0
            while True:
                line = fh.readline()
                if not line:
                    break
                line_num += 1
                if line_num % _STRIDE == 0:
                    offsets.append(fh.tell())
        self._offsets = offsets
        self._built = True

    def read_lines(self, start: int, end: int) -> list[str]:
        if not self._built:
            self._build()
        stride_idx = max(0, (start - 1) // _STRIDE)
        byte_offset = self._offsets[min(stride_idx, len(self._offsets) - 1)]
        base_line = stride_idx * _STRIDE + 1

        result: list[str] = []
        with open(self.path, "r", encoding="utf-8", errors="replace") as fh:
            fh.seek(byte_offset)
            current = base_line
            for raw in fh:
                if current > end:
                    break
                if current >= start:
                    result.append(raw.rstrip("\n"))
                current += 1
        return result


class _SmallFileCache:
    """小文件：全量加载到内存，O(1) 随机访问。"""

    def __init__(self, path: Path):
        self._lines = path.read_text(encoding="utf-8", errors="replace").splitlines()

    def read_lines(self, start: int, end: int) -> list[str]:
        s = max(0, start - 1)
        e = min(end, len(self._lines))
        return self._lines[s:e]


class CodeSnippetExtractor:
    """
    从反编译输出目录按行号提取代码片段。

    Usage:
        extractor = CodeSnippetExtractor(index_dir.parent)
        # 给 hypotheses 的 decompiled_candidates 注入 code_snippet
        hypotheses = extractor.enrich_hypotheses(hypotheses)
        # 给 proc_source_hints 的 decompiled_candidates 注入 code_snippet
        hints = extractor.enrich_proc_source_hints(hints)
    """

    def __init__(
        self,
        decompiled_root: str | Path,
        context_lines: int = 6,
        max_snippet_lines: int = 50,
    ):
        self.root = Path(decompiled_root)
        self.context_lines = context_lines
        self.max_snippet_lines = max_snippet_lines
        self._cache: dict[str, _SparseLineIndex | _SmallFileCache] = {}

    # ── 公开接口 ────────────────────────────────────────────────────────

    def extract(
        self,
        file_name: str,
        line_start: int,
        line_end: int,
        annotate: bool = True,
    ) -> str | None:
        """
        提取 file_name 中 line_start~line_end 的代码片段（含前后 context_lines 行上下文）。
        annotate=True 时在关键行旁添加 ← 标注。
        返回带行号前缀的代码字符串，失败返回 None。
        """
        reader = self._get_reader(file_name)
        if reader is None:
            return None

        ctx = self.context_lines
        fetch_start = max(1, line_start - ctx)
        raw_end = line_end + ctx

        # 限制最大行数，防止超大函数撑爆 token
        capped_end = min(raw_end, fetch_start + self.max_snippet_lines - 1)

        lines = reader.read_lines(fetch_start, capped_end)
        if not lines:
            return None

        result_lines: list[str] = []
        for i, text in enumerate(lines):
            lineno = fetch_start + i
            in_body = line_start <= lineno <= line_end
            prefix = ">" if in_body else " "
            annotation = self._annotate(text) if (annotate and in_body) else ""
            result_lines.append(f"{prefix} {lineno:>7} | {text}{annotation}")

        return "\n".join(result_lines)

    def enrich_candidates(self, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        给 decompiled_candidates 列表的每一项注入 code_snippet 字段。
        原地修改并返回。
        """
        for c in candidates:
            if c.get("code_snippet"):
                continue
            snippet = self.extract(
                c.get("file", ""),
                int(c.get("line_start") or 0),
                int(c.get("line_end") or 0),
            )
            c["code_snippet"] = snippet
        return candidates

    def enrich_hypotheses(self, hypotheses: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """给 hypotheses 列表中每个假设的 candidate_code_scope 注入代码片段。"""
        for hyp in hypotheses:
            scope = hyp.get("candidate_code_scope") or []
            self.enrich_candidates(scope)
            for cand in hyp.get("decompiled_candidates") or []:
                self.enrich_candidates([cand])
        return hypotheses

    def enrich_proc_source_hints(
        self, hints: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """给 proc_source_hints 中每个 hint 的 decompiled_candidates 注入代码片段。"""
        for hint in hints:
            candidates = hint.get("decompiled_candidates") or []
            self.enrich_candidates(candidates)
        return hints

    def summarize_snippet_quality(self, snippet: str | None) -> dict[str, Any]:
        """
        分析代码片段，返回质量指标（是否命中生命周期、状态写入、VSync 等）。
        用于在确定性报告中标注代码质量信号。
        """
        if not snippet:
            return {"available": False}
        has_lifecycle = bool(_LIFECYCLE_RE.search(snippet))
        has_vsync = bool(_VSYNC_HINT_RE.search(snippet))
        state_writes = len(_STATE_WRITE_RE.findall(snippet))
        line_count = snippet.count("\n") + 1
        return {
            "available": True,
            "line_count": line_count,
            "has_lifecycle_entry": has_lifecycle,
            "has_vsync_hint": has_vsync,
            "state_write_count": state_writes,
        }

    # ── 内部实现 ────────────────────────────────────────────────────────

    def _get_reader(self, file_name: str) -> _SparseLineIndex | _SmallFileCache | None:
        if not file_name:
            return None
        if file_name in self._cache:
            return self._cache[file_name]

        path = self.root / file_name
        if not path.exists():
            self._cache[file_name] = None  # type: ignore[assignment]
            return None

        try:
            size = path.stat().st_size
            # 粗估行数：平均 40 字节/行
            estimated_lines = size // 40
            if estimated_lines > _LARGE_FILE_THRESHOLD:
                reader: _SparseLineIndex | _SmallFileCache = _SparseLineIndex(path)
            else:
                reader = _SmallFileCache(path)
        except OSError:
            self._cache[file_name] = None  # type: ignore[assignment]
            return None

        self._cache[file_name] = reader
        return reader

    def enrich_with_ui_index(
        self,
        owner_names: list[str],
        ui_index_path: "str | Path",
        priority_apis: tuple[str, ...] = ("ForEach", "LazyForEach", "Tabs", "List", "WaterFlow", "Grid"),
        max_extra_snippets: int = 4,
    ) -> list[dict[str, Any]]:
        """
        方向一：从 ui_index.jsonl 为嫌疑组件找到使用了高风险 UI API（ForEach/Tabs 等）
        的方法，提取其代码片段，作为额外的 LLM 分析材料。

        重点提取：
        - ForEach / LazyForEach 的 item builder 方法（getSingleItem、renderItem 等）
        - Tabs/TabContent 相关渲染方法
        - 不重复已在 proc_source_hints 中出现的 (file, line_start)

        Returns list of enriched candidate dicts (含 code_snippet 字段)。
        """
        import json as _json
        ui_index_path = Path(ui_index_path)
        if not ui_index_path.exists():
            return []

        target_set = set(owner_names)
        priority_set = set(a.lower() for a in priority_apis)

        # 按 (file, line_start) 去重，优先高风险 API
        candidates_by_key: dict[tuple[str, int], dict[str, Any]] = {}

        with open(ui_index_path, encoding="utf-8", errors="replace") as fh:
            for raw in fh:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    rec = _json.loads(raw)
                except Exception:
                    continue
                if rec.get("owner_name") not in target_set:
                    continue
                api = (rec.get("ui_api") or "").lower()
                if api not in priority_set:
                    continue
                key = (rec.get("file", ""), int(rec.get("line_start") or 0))
                existing = candidates_by_key.get(key)
                # 用 priority_apis 里的顺序作为优先级
                new_prio = next(
                    (i for i, a in enumerate(priority_apis) if a.lower() == api),
                    len(priority_apis),
                )
                if existing is None or new_prio < existing.get("_prio", 999):
                    candidates_by_key[key] = {
                        "file": rec.get("file", ""),
                        "line_start": int(rec.get("line_start") or 0),
                        "line_end": int(rec.get("line_end") or 0),
                        "owner_name": rec.get("owner_name", ""),
                        "symbol_name": rec.get("symbol_name", ""),
                        "ui_api": rec.get("ui_api", ""),
                        "confidence_hint": f"包含高风险 UI API: {rec.get('ui_api')}",
                        "_prio": new_prio,
                    }

        # 按优先级排序，取 top N
        sorted_cands = sorted(candidates_by_key.values(), key=lambda c: c["_prio"])
        result: list[dict[str, Any]] = []
        for cand in sorted_cands[:max_extra_snippets]:
            cand.pop("_prio", None)
            snippet = self.extract(
                cand["file"],
                cand["line_start"],
                cand["line_end"],
                annotate=True,
            )
            cand["code_snippet"] = snippet
            cand["evidence_hits"] = 0
            result.append(cand)

        return result

    @staticmethod
    def _annotate(line: str) -> str:
        """在含关键操作的行末添加简短注释。"""
        stripped = line.strip()
        if _STATE_WRITE_RE.search(stripped) and "return" not in stripped:
            return "  // ← 状态写入"
        if _VSYNC_HINT_RE.search(stripped):
            return "  // ← VSync/定时器"
        if _LIFECYCLE_RE.search(stripped) and "function" in stripped:
            return "  // ← 生命周期入口"
        return ""
