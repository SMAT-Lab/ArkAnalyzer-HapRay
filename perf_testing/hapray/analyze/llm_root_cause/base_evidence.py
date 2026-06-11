"""
base_evidence.py

多信号根因分析的证据提取器基类与共享工具。

每个性能信号（CPU 高负载、帧负载、冗余线程、IPC、组件复用、SO 负载、内存、
帧率/RS/Vsync、UI 动画、故障树/hilog、空刷）实现为一个 EvidenceExtractor 子类，
runner 聚合所有 is_available() 的子类输出，按 category 分章喂给 LLM/Agent。

证据段统一形状（build 返回）：
    {
        'category': str,           # 信号类别，见 structured_output.CATEGORY_LABELS
        'kind': 'suspect' | 'observation',
        'summary': dict,           # 该信号的标量摘要
        'items': list[dict],       # 明细条目（suspect 类尽量带 source_path/line/owner）
    }
不可用时 build 返回 None。
"""

from __future__ import annotations

import json
import re
import sqlite3
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

# ArkTS/JS 帧符号自带的「源码:行:列」格式，例如：
#   rerender:[url:entry|entry|1.0.0|src/main/ets/components/LyricsLineComponent.ts:1056:14]
SOURCE_LOC_RE = re.compile(
    r'^(?P<symbol_name>.+?):\[url:(?P<meta>.*)\|(?P<source>src/main/(?:ets|js)/.+?):(?P<line>\d+):(?P<column>\d+)\]$'
)


def safe_float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    if isinstance(value, str):
        text = value.strip().rstrip('%')
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


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return default


def parse_arkts_source_loc(symbol: str) -> dict[str, Any] | None:
    """从 ArkTS/JS 帧符号串解析出 {source_path, line, column, symbol_name, owner_name}。

    无法解析（非 ArkTS 帧、原生符号等）返回 None。
    """
    if not symbol:
        return None
    matched = SOURCE_LOC_RE.match(symbol.strip())
    if matched is None:
        return None
    source_path = matched.group('source')
    symbol_name = matched.group('symbol_name').strip()
    owner = Path(source_path).stem
    return {
        'source_path': source_path,
        'line': safe_int(matched.group('line')),
        'column': safe_int(matched.group('column')),
        'symbol_name': symbol_name,
        'owner_name': owner if owner and owner.lower() != 'index' else (symbol_name or 'unknown'),
        'raw_symbol': symbol,
    }


class EvidenceExtractor(ABC):
    """单个性能信号的证据提取器基类。

    子类须设置类属性 ``category`` 与 ``kind``，并实现 ``is_available`` / ``build``。
    """

    category: str = ''
    kind: str = 'suspect'  # 'suspect'（带源码定位的根因条目）| 'observation'（现象）

    def __init__(self, report_dir: str | Path, *, top_n: int = 10) -> None:
        # report_dir 指向 <用例>/report
        self.report_dir = Path(report_dir)
        self.top_n = top_n

    # ── 共享 IO 工具 ───────────────────────────────────────────────
    def read_json(self, filename: str) -> dict | list | None:
        path = self.report_dir / filename
        if not path.exists():
            return None
        try:
            with path.open(encoding='utf-8') as handle:
                return json.load(handle)
        except (OSError, json.JSONDecodeError):
            return None

    def report_file(self, filename: str) -> Path:
        return self.report_dir / filename

    def perf_db_path(self, step_id: str) -> Path:
        """<用例>/hiperf/<step>/perf.db （report_dir 的同级 hiperf 目录）。"""
        return self.report_dir.parent / 'hiperf' / step_id / 'perf.db'

    def list_perf_db_steps(self) -> list[tuple[str, Path]]:
        """枚举所有含 perf.db 的 step，返回 [(step_id, perf_db_path), ...]。"""
        hiperf_root = self.report_dir.parent / 'hiperf'
        if not hiperf_root.is_dir():
            return []
        out: list[tuple[str, Path]] = []
        for step_dir in sorted(hiperf_root.glob('step*')):
            db = step_dir / 'perf.db'
            if db.is_file():
                out.append((step_dir.name, db))
        return out

    @staticmethod
    def connect_ro(db_path: Path) -> sqlite3.Connection | None:
        try:
            return sqlite3.connect(str(db_path))
        except sqlite3.Error:
            return None

    @staticmethod
    def safe_float(value: Any, default: float = 0.0) -> float:
        return safe_float(value, default)

    @staticmethod
    def safe_int(value: Any, default: int = 0) -> int:
        return safe_int(value, default)

    # ── 子类实现 ───────────────────────────────────────────────────
    @abstractmethod
    def is_available(self) -> bool:
        """对应产物是否存在/可读。"""

    @abstractmethod
    def build(self) -> dict[str, Any] | None:
        """返回统一形状的证据段；不可用返回 None。"""

    def empty_section(self) -> dict[str, Any]:
        return {'category': self.category, 'kind': self.kind, 'summary': {}, 'items': []}
