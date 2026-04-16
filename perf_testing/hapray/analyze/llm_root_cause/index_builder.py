from __future__ import annotations

"""
基于规则的 HAP 反编译结果索引构建脚本。

输入：反编译输出目录（递归扫描 *.ts）
输出：
  - symbol_index.jsonl  每个函数/方法一个索引项
  - ui_index.jsonl      每个 symbol 内命中的 UI 关键字摘要
  - file_index.json     每个文件的聚合摘要
  - stats.json          全局统计信息

示例：
  python index_builder.py \
    --input standalone_tools/llm_root_cause/binary_insight_framework-main-tools-hap_decompiler/decompiled_jd_hap_sdk20
"""

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Iterable, TextIO


RECOVERED_RE = re.compile(r"^\s*//\s*recovered from:\s*(.+?)\s*$")
CLASS_RE = re.compile(r"^\s*class\s+([A-Za-z_][A-Za-z0-9_]*)\s*\{")
FUNCTION_RE = re.compile(r"^\s*(async\s+function\*|async\s+function|function)\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(")
CONFIDENCE_RE = re.compile(r"confidence:\s*(\d+)%")
VERSION_SEGMENT_RE = re.compile(r"&\d+(?:\.\d+)+")
SYNTHETIC_SEGMENT_RE = re.compile(r"\.?#~@\d+>#")

LIFECYCLE_METHODS = {
    "aboutToAppear",
    "aboutToDisappear",
    "aboutToBeDeleted",
    "onPageShow",
    "onPageHide",
    "initialRender",
    "build",
    "rerender",
}

OWNER_SUFFIXES = (
    "Page",
    "View",
    "Component",
    "Panel",
    "Dialog",
    "Manager",
    "Model",
    "Controller",
    "Proxy",
    "Popup",
    "Card",
    "Item",
)

UI_RULES = [
    {"name": "ForEach", "category": "list", "pattern": re.compile(r"\bForEach(?:\.create)?\b")},
    {"name": "LazyForEach", "category": "list", "pattern": re.compile(r"\bLazyForEach\b")},
    {"name": "WaterFlow", "category": "list", "pattern": re.compile(r"\bWaterFlow\b")},
    {"name": "List", "category": "container", "pattern": re.compile(r"\bList\b")},
    {"name": "Grid", "category": "container", "pattern": re.compile(r"\bGrid(?:Item)?\b")},
    {"name": "Column", "category": "container", "pattern": re.compile(r"\bColumn\b")},
    {"name": "Row", "category": "container", "pattern": re.compile(r"\bRow\b")},
    {"name": "Tabs", "category": "container", "pattern": re.compile(r"\bTabs\b")},
    {"name": "Swiper", "category": "container", "pattern": re.compile(r"\bSwiper\b")},
    {"name": "Scroll", "category": "container", "pattern": re.compile(r"\bScroll\b")},
    {"name": "If", "category": "control", "pattern": re.compile(r"\bIf\b")},
    {"name": "XComponent", "category": "native", "pattern": re.compile(r"\bXComponent\b")},
    {
        "name": "observeComponentCreation2",
        "category": "framework",
        "pattern": re.compile(r"\bobserveComponentCreation2\b"),
    },
    {"name": "AppStorage", "category": "state", "pattern": re.compile(r"\bAppStorage\b")},
    {"name": "LocalStorage", "category": "state", "pattern": re.compile(r"\bLocalStorage\b")},
]

OWNER_TYPE_PATTERNS = [
    (".ets.pages.", "page"),
    (".ets.components.", "component"),
    (".ets.view.", "view"),
    (".ets.entry.", "entry"),
    (".service.", "service"),
    (".manager.", "manager"),
    (".model.", "model"),
    (".store.", "store"),
    (".controller.", "controller"),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="构建反编译 TS 的规则索引")
    parser.add_argument("--input", required=True, help="反编译输出目录，递归扫描其中的 *.ts 文件")
    parser.add_argument("--output-dir", default=None, help="索引输出目录，默认写到 <input>/index")
    return parser.parse_args()


def brace_delta(line: str) -> int:
    return line.count("{") - line.count("}")


def iter_ui_hits(line: str) -> Iterable[tuple[str, str]]:
    seen = set()
    for rule in UI_RULES:
        if rule["pattern"].search(line):
            key = (rule["name"], rule["category"])
            if key not in seen:
                seen.add(key)
                yield key


def parse_confidence(raw_recovered: str) -> float | None:
    match = CONFIDENCE_RE.search(raw_recovered)
    if not match:
        return None
    return int(match.group(1)) / 100.0


def normalize_recovered_path(raw_recovered: str) -> str:
    path = raw_recovered.split(" | ", 1)[0].strip()
    if path.startswith("&@"):
        path = path[2:]
    elif path.startswith("@"):
        path = path[1:]
    path = VERSION_SEGMENT_RE.sub("", path)
    path = SYNTHETIC_SEGMENT_RE.sub(".", path)
    path = path.replace("&", "")
    path = path.strip(".")
    return path


def infer_owner_type(module_path: str, owner_name: str) -> str:
    lowered = f".{module_path.lower()}."
    for marker, owner_type in OWNER_TYPE_PATTERNS:
        if marker in lowered:
            return owner_type

    if owner_name.endswith("Page"):
        return "page"
    if owner_name.endswith(("Component", "Dialog", "Popup", "Card", "Item")):
        return "component"
    if owner_name.endswith(("View", "Panel")):
        return "view"
    if owner_name.endswith("Manager"):
        return "manager"
    if owner_name.endswith("Model"):
        return "model"
    if owner_name.endswith("Controller"):
        return "controller"
    if owner_name.endswith("Proxy"):
        return "proxy"
    return "unknown"


def split_meaningful_tokens(module_path: str) -> list[str]:
    tokens = [token for token in module_path.split(".") if token]
    return [token for token in tokens if not token.startswith("#")]


def looks_like_symbol_token(token: str) -> bool:
    if not token:
        return False
    if token in LIFECYCLE_METHODS:
        return True
    if token.startswith("_"):
        return True
    if token[0].islower():
        return True
    return False


def trim_module_tokens(tokens: list[str], symbol_name: str) -> list[str]:
    trimmed = list(tokens)
    while trimmed and trimmed[-1].startswith("#"):
        trimmed.pop()
    if trimmed and trimmed[-1] == symbol_name:
        trimmed.pop()
    elif trimmed and looks_like_symbol_token(trimmed[-1]):
        trimmed.pop()
    return trimmed


def derive_symbol_identity(raw_recovered: str | None, symbol_name: str, current_class: str | None) -> dict:
    if not raw_recovered:
        owner_name = current_class or ""
        return {
            "recovered_from": None,
            "normalized_recovered_from": None,
            "module_path": current_class or "",
            "owner_name": owner_name,
            "owner_type": infer_owner_type(current_class or "", owner_name),
            "confidence": None,
        }

    normalized = normalize_recovered_path(raw_recovered)
    confidence = parse_confidence(raw_recovered)
    tokens = trim_module_tokens(split_meaningful_tokens(normalized), symbol_name)

    module_path = ".".join(tokens)
    owner_name = tokens[-1] if tokens else (current_class or "")
    owner_type = infer_owner_type(module_path, owner_name)

    return {
        "recovered_from": raw_recovered.strip(),
        "normalized_recovered_from": normalized,
        "module_path": module_path,
        "owner_name": owner_name,
        "owner_type": owner_type,
        "confidence": confidence,
    }


def make_symbol_record(
    relative_file: str,
    line_no: int,
    function_kind: str,
    symbol_name: str,
    raw_recovered: str | None,
    current_class: str | None,
) -> dict:
    identity = derive_symbol_identity(raw_recovered, symbol_name, current_class)
    return {
        "id": f"{relative_file}:{line_no}",
        "file": relative_file,
        "line_start": line_no,
        "line_end": line_no,
        "class_name": current_class,
        "symbol_name": symbol_name,
        "symbol_kind": function_kind,
        "symbol_type": "method",
        "is_lifecycle": symbol_name in LIFECYCLE_METHODS,
        "recovered_from": identity["recovered_from"],
        "normalized_recovered_from": identity["normalized_recovered_from"],
        "module_path": identity["module_path"],
        "owner_name": identity["owner_name"],
        "owner_type": identity["owner_type"],
        "confidence": identity["confidence"],
        "ui_keywords": [],
        "ui_hits": {},
        "brace_depth": 0,
    }


def register_ui_hit(symbol: dict, line_no: int, ui_name: str, category: str) -> None:
    hit = symbol["ui_hits"].get(ui_name)
    if hit is None:
        symbol["ui_hits"][ui_name] = {
            "ui_api": ui_name,
            "category": category,
            "count": 1,
            "first_line": line_no,
        }
        symbol["ui_keywords"].append(ui_name)
        return
    hit["count"] += 1


def finalize_symbol(
    symbol: dict,
    end_line: int,
    symbol_writer: TextIO,
    ui_writer: TextIO,
    file_summary: dict,
) -> None:
    symbol["line_end"] = max(symbol["line_start"], end_line)

    ui_hits = list(symbol.pop("ui_hits").values())
    symbol_writer.write(json.dumps(symbol, ensure_ascii=False) + "\n")

    file_summary["symbol_count"] += 1
    if symbol["is_lifecycle"]:
        file_summary["lifecycle_count"] += 1

    owner_name = symbol.get("owner_name") or ""
    owner_type = symbol.get("owner_type") or "unknown"
    if owner_name:
        if owner_type == "page":
            file_summary["pages"].add(owner_name)
        elif owner_type == "component":
            file_summary["components"].add(owner_name)
        elif owner_type == "view":
            file_summary["views"].add(owner_name)

    for hit in ui_hits:
        file_summary["ui_counts"][hit["ui_api"]] += hit["count"]
        ui_record = {
            "symbol_id": symbol["id"],
            "file": symbol["file"],
            "owner_name": symbol.get("owner_name"),
            "owner_type": symbol.get("owner_type"),
            "symbol_name": symbol.get("symbol_name"),
            "line_start": symbol.get("line_start"),
            "line_end": symbol.get("line_end"),
            **hit,
        }
        ui_writer.write(json.dumps(ui_record, ensure_ascii=False) + "\n")


def scan_file(file_path: Path, input_root: Path, symbol_writer: TextIO, ui_writer: TextIO) -> dict:
    relative_file = file_path.relative_to(input_root).as_posix()
    file_summary = {
        "file": relative_file,
        "line_count": 0,
        "symbol_count": 0,
        "lifecycle_count": 0,
        "pages": set(),
        "components": set(),
        "views": set(),
        "ui_counts": Counter(),
    }

    current_class: str | None = None
    pending_recovered: str | None = None
    current_symbol: dict | None = None

    with file_path.open("r", encoding="utf-8", errors="replace") as handle:
        for line_no, line in enumerate(handle, start=1):
            file_summary["line_count"] = line_no

            if current_symbol is not None:
                for ui_name, category in iter_ui_hits(line):
                    register_ui_hit(current_symbol, line_no, ui_name, category)
                current_symbol["brace_depth"] += brace_delta(line)
                if current_symbol["brace_depth"] <= 0:
                    finalize_symbol(current_symbol, line_no, symbol_writer, ui_writer, file_summary)
                    current_symbol = None
                continue

            recovered_match = RECOVERED_RE.match(line)
            if recovered_match:
                pending_recovered = recovered_match.group(1).strip()
                continue

            class_match = CLASS_RE.match(line)
            if class_match:
                current_class = class_match.group(1)
                continue

            function_match = FUNCTION_RE.match(line)
            if function_match:
                function_kind = function_match.group(1)
                symbol_name = function_match.group(2)
                current_symbol = make_symbol_record(
                    relative_file=relative_file,
                    line_no=line_no,
                    function_kind=function_kind,
                    symbol_name=symbol_name,
                    raw_recovered=pending_recovered,
                    current_class=current_class,
                )
                pending_recovered = None

                for ui_name, category in iter_ui_hits(line):
                    register_ui_hit(current_symbol, line_no, ui_name, category)

                current_symbol["brace_depth"] = brace_delta(line)
                if current_symbol["brace_depth"] <= 0:
                    finalize_symbol(current_symbol, line_no, symbol_writer, ui_writer, file_summary)
                    current_symbol = None
                continue

            if line.strip():
                pending_recovered = None

    if current_symbol is not None:
        finalize_symbol(current_symbol, file_summary["line_count"], symbol_writer, ui_writer, file_summary)

    return {
        "file": file_summary["file"],
        "line_count": file_summary["line_count"],
        "symbol_count": file_summary["symbol_count"],
        "lifecycle_count": file_summary["lifecycle_count"],
        "pages": sorted(file_summary["pages"]),
        "components": sorted(file_summary["components"]),
        "views": sorted(file_summary["views"]),
        "ui_keywords_top": [
            {"name": name, "count": count}
            for name, count in file_summary["ui_counts"].most_common(20)
        ],
    }


def collect_ts_files(input_root: Path) -> list[Path]:
    return sorted(path for path in input_root.rglob("*.ts") if path.is_file())


def write_json(path: Path, data: object) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def build_index(input_root: Path, output_dir: Path) -> dict:
    ts_files = collect_ts_files(input_root)
    if not ts_files:
        raise FileNotFoundError(f"未在目录中找到 .ts 文件: {input_root}")

    output_dir.mkdir(parents=True, exist_ok=True)
    symbol_index_path = output_dir / "symbol_index.jsonl"
    ui_index_path = output_dir / "ui_index.jsonl"
    file_index_path = output_dir / "file_index.json"
    stats_path = output_dir / "stats.json"

    file_summaries = []
    total_lines = 0
    total_symbols = 0
    total_lifecycle = 0
    total_pages = set()
    total_components = set()
    total_views = set()

    with symbol_index_path.open("w", encoding="utf-8") as symbol_writer, ui_index_path.open("w", encoding="utf-8") as ui_writer:
        for file_path in ts_files:
            summary = scan_file(file_path, input_root, symbol_writer, ui_writer)
            file_summaries.append(summary)
            total_lines += summary["line_count"]
            total_symbols += summary["symbol_count"]
            total_lifecycle += summary["lifecycle_count"]
            total_pages.update(summary["pages"])
            total_components.update(summary["components"])
            total_views.update(summary["views"])
            print(
                f"[indexed] {summary['file']} | lines={summary['line_count']:,} | "
                f"symbols={summary['symbol_count']:,} | lifecycle={summary['lifecycle_count']:,}"
            )

    write_json(file_index_path, file_summaries)
    stats = {
        "input_root": str(input_root),
        "output_dir": str(output_dir),
        "file_count": len(ts_files),
        "total_lines": total_lines,
        "total_symbols": total_symbols,
        "total_lifecycle_symbols": total_lifecycle,
        "page_count": len(total_pages),
        "component_count": len(total_components),
        "view_count": len(total_views),
        "pages": sorted(total_pages),
        "components": sorted(total_components),
        "views": sorted(total_views),
        "outputs": {
            "symbol_index": str(symbol_index_path),
            "ui_index": str(ui_index_path),
            "file_index": str(file_index_path),
            "stats": str(stats_path),
        },
    }
    write_json(stats_path, stats)
    return stats


def main() -> None:
    args = parse_args()
    input_root = Path(args.input).resolve()
    if not input_root.exists():
        raise FileNotFoundError(f"输入目录不存在: {input_root}")

    output_dir = Path(args.output_dir).resolve() if args.output_dir else input_root / "index"
    stats = build_index(input_root, output_dir)

    print("\n索引完成：")
    print(f"- 文件数: {stats['file_count']}")
    print(f"- 总行数: {stats['total_lines']:,}")
    print(f"- Symbol 数: {stats['total_symbols']:,}")
    print(f"- 生命周期 Symbol 数: {stats['total_lifecycle_symbols']:,}")
    print(f"- Page 数: {stats['page_count']}")
    print(f"- Component 数: {stats['component_count']}")
    print(f"- View 数: {stats['view_count']}")
    print(f"- 输出目录: {stats['output_dir']}")


if __name__ == "__main__":
    main()
