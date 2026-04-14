from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


_CAMEL_TOKEN_RE = re.compile(r"[A-Z]+(?=[A-Z][a-z]|\d|$)|[A-Z]?[a-z]+|\d+")
_LIST_UI_KEYS = {"waterflow", "lazyforeach", "list", "scroll", "foreach"}
_GENERIC_SYMBOLS = {"_anonymous", "func_main_0", "value"}
_PROC_STOP_TOKENS = {
    "src",
    "main",
    "ets",
    "js",
    "ts",
    "index",
    "pages",
    "page",
    "view",
    "views",
    "component",
    "components",
    "layout",
    "module",
    "modules",
    "lib",
    "libs",
    "business",
    "common",
    "core",
    "base",
    "beta",
    "alpha",
    "release",
    "sdk",
    "jd",
    "oh",
    "hm",
    "v1",
    "v2",
    "v3",
    "v4",
    "v5",
    "to",
}


class CodeIndexLookup:
    def __init__(self, index_dir: str | Path):
        self.index_dir = Path(index_dir)
        self.symbols = self._load_jsonl(self.index_dir / "symbol_index.jsonl")
        self.ui_records = self._load_jsonl(self.index_dir / "ui_index.jsonl")

    @staticmethod
    def _load_jsonl(path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            raise FileNotFoundError(f"索引文件不存在: {path}")
        items = []
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                items.append(json.loads(line))
        return items

    @staticmethod
    def _norm(text: Any) -> str:
        return str(text or "").lower()

    @staticmethod
    def _camel_tokens(text: Any) -> list[str]:
        return [token.lower() for token in _CAMEL_TOKEN_RE.findall(str(text or "")) if token]

    @classmethod
    def _collapse(cls, text: Any) -> str:
        return re.sub(r"[^a-z0-9]+", "", cls._norm(text))

    @classmethod
    def _tokenize_free_text(cls, text: Any) -> list[str]:
        return [item for item in re.findall(r"[a-z0-9]+", cls._norm(text).replace("@", " ")) if item]

    @staticmethod
    def _dedupe_texts(items: list[str]) -> list[str]:
        ordered: list[str] = []
        seen = set()
        for item in items:
            value = str(item or "").strip()
            if not value or value in seen:
                continue
            seen.add(value)
            ordered.append(value)
        return ordered

    @classmethod
    def _clean_proc_tokens(cls, tokens: list[str]) -> list[str]:
        cleaned = []
        for token in tokens:
            lowered = cls._norm(token)
            if not lowered:
                continue
            if lowered in _PROC_STOP_TOKENS:
                continue
            if len(lowered) == 1:
                continue
            cleaned.append(lowered)
        return cls._dedupe_texts(cleaned)

    @classmethod
    def _derive_proc_phrases(cls, text: Any) -> list[str]:
        name = str(text or "")
        if not name:
            return []
        phrases: list[str] = []
        collapsed = cls._collapse(name)
        if len(collapsed) >= 6:
            phrases.append(collapsed)
        tokens = cls._clean_proc_tokens(cls._camel_tokens(name))
        if len(tokens) >= 2:
            phrases.append("".join(tokens[:2]))
        if len(tokens) >= 3:
            phrases.append("".join(tokens[:3]))
        if len(tokens) >= 2:
            phrases.append("".join(tokens[-2:]))
        strong_tokens = [token for token in tokens if len(token) > 2]
        if len(strong_tokens) >= 2:
            phrases.append("".join(strong_tokens[:2]))
        if len(strong_tokens) >= 3:
            phrases.append("".join(strong_tokens[:3]))
        return cls._dedupe_texts([item for item in phrases if len(item) >= 4])

    @staticmethod
    def _short_module_path(module_path: str, keep: int = 4) -> str:
        parts = [item for item in str(module_path or "").split(".") if item]
        if not parts:
            return module_path
        return ".".join(parts[-keep:])

    def lookup_hypotheses(self, hypotheses: list[dict[str, Any]], limit: int = 6) -> list[dict[str, Any]]:
        resolved = []
        for hypothesis in hypotheses:
            query = hypothesis.get("code_query", {})
            candidates = self._match_candidates(query)
            resolved.append(
                {
                    **hypothesis,
                    "candidate_code_scope": candidates[:limit],
                }
            )
        return resolved

    def lookup_proc_sources(self, proc_source_hints: list[dict[str, Any]], limit: int = 3) -> list[dict[str, Any]]:
        resolved = []
        for hint in proc_source_hints:
            candidates = self._match_proc_source_candidates(hint)
            resolved.append(
                {
                    **hint,
                    "decompiled_candidates": candidates[:limit],
                }
            )
        return resolved

    def _build_proc_source_query(self, hint: dict[str, Any]) -> dict[str, Any]:
        source_path = str(hint.get("source_path", "") or "")
        path_obj = Path(source_path) if source_path else None
        source_name = path_obj.stem if path_obj else str(hint.get("owner_name", "") or "")
        parent_name = path_obj.parent.name if path_obj else ""
        if source_name.lower() == "index" and parent_name:
            source_name = parent_name
        owner_name = str(hint.get("owner_name", "") or source_name)

        source_tokens = self._clean_proc_tokens(self._camel_tokens(source_name))
        parent_tokens = self._clean_proc_tokens(self._camel_tokens(parent_name))
        owner_tokens = self._clean_proc_tokens(self._camel_tokens(owner_name))

        package_tokens: list[str] = []
        package_phrases: list[str] = []
        for package in hint.get("packages", []):
            tokens = self._clean_proc_tokens(
                self._tokenize_free_text(str(package).replace("/", " ").replace("-", " ").replace(".", " "))
            )
            package_tokens.extend(tokens)
            if len(tokens) >= 2:
                package_phrases.append("".join(tokens[:2]))

        raw_symbols = [self._norm(item) for item in hint.get("symbols", []) if item]
        symbol_keywords = []
        wants_lifecycle = False
        for symbol in raw_symbols:
            compact = self._collapse(symbol)
            if compact and (len(compact) >= 4 or compact in {"tn", "h5", "ui"}):
                symbol_keywords.append(compact)
            if any(token in compact for token in ("abouttoappear", "initialrender", "onpageshow", "build")):
                wants_lifecycle = True

        strong_phrases = self._dedupe_texts(
            self._derive_proc_phrases(source_name)
            + self._derive_proc_phrases(parent_name)
            + self._derive_proc_phrases(owner_name)
            + [item for item in package_phrases if len(item) >= 6]
        )
        topic_tokens = self._dedupe_texts(source_tokens + parent_tokens + owner_tokens + package_tokens)

        return {
            "source_path": source_path,
            "source_name": source_name,
            "topic_tokens": topic_tokens[:12],
            "strong_phrases": strong_phrases[:8],
            "symbol_keywords": self._dedupe_texts(symbol_keywords)[:6],
            "wants_lifecycle": wants_lifecycle,
            "list_bias": any(
                token in topic_tokens
                for token in ("search", "list", "product", "commodity", "waterflow", "flow", "skeleton", "card", "container", "item")
            ),
            "animation_bias": any(token in topic_tokens for token in ("skeleton", "animation", "gradient", "lottie")),
            "search_bias": any(token in topic_tokens for token in ("search", "tn", "product", "commodity", "shop")),
            "web_bias": any(token in topic_tokens for token in ("web", "hybrid", "h5")),
        }

    def _match_candidates(self, query: dict[str, Any]) -> list[dict[str, Any]]:
        owner_keywords = [self._norm(item) for item in query.get("owner_keywords", []) if item]
        module_keywords = [self._norm(item) for item in query.get("module_keywords", []) if item]
        ui_keywords = [self._norm(item) for item in query.get("ui_keywords", []) if item]
        symbol_keywords = [self._norm(item) for item in query.get("symbol_keywords", []) if item]

        symbol_rows = self._score_symbols(owner_keywords, module_keywords, ui_keywords, symbol_keywords)
        ui_by_symbol = self._collect_ui_hits(symbol_rows)

        candidates = []
        for row in symbol_rows:
            symbol_id = row["id"]
            score = row["_score"]
            reasons = list(row["_reasons"])
            ui_hits = ui_by_symbol.get(symbol_id, [])
            ui_names = [item["ui_api"] for item in ui_hits]
            if ui_names:
                reasons.append(f"UI命中: {', '.join(ui_names[:4])}")

            module_path = row.get("module_path", "")
            owner_name = row.get("owner_name", "")
            owner_type = row.get("owner_type", "unknown")
            symbol_name = row.get("symbol_name", "")

            cause_tags = []
            lowered_ui = {name.lower() for name in ui_names}
            if any(name in lowered_ui for name in _LIST_UI_KEYS):
                cause_tags.append("list_rebuild")
            if any(keyword in self._norm(module_path) for keyword in ["web", "hybrid"]):
                cause_tags.append("web_hybrid")
            if "map" in self._norm(module_path) or "map" in self._norm(owner_name):
                cause_tags.append("map_refresh")
            if symbol_name.lower().endswith(("abouttoappear", "onpageshow", "initialrender", "build")):
                cause_tags.append("lifecycle_entry")

            candidates.append(
                {
                    "file": row.get("file"),
                    "line_start": row.get("line_start"),
                    "line_end": row.get("line_end"),
                    "owner_name": owner_name,
                    "owner_type": owner_type,
                    "symbol_name": symbol_name,
                    "module_path": module_path,
                    "module_path_short": self._short_module_path(module_path),
                    "ui_keywords": row.get("ui_keywords", []),
                    "matched_ui_hits": ui_hits,
                    "score": score,
                    "reasons": self._dedupe_texts(reasons),
                    "cause_tags": cause_tags,
                }
            )

        return self._dedupe_candidates(candidates)

    def _match_proc_source_candidates(self, hint: dict[str, Any]) -> list[dict[str, Any]]:
        query = self._build_proc_source_query(hint)
        scored = []
        for row in self.symbols:
            owner_name = self._norm(row.get("owner_name"))
            module_path = self._norm(row.get("module_path"))
            symbol_name = self._norm(row.get("symbol_name"))
            normalized = self._norm(row.get("normalized_recovered_from") or row.get("recovered_from"))
            owner_type = self._norm(row.get("owner_type"))
            ui_names = [self._norm(item) for item in row.get("ui_keywords", [])]
            collapsed = self._collapse(" ".join([owner_name, module_path, symbol_name, normalized, " ".join(ui_names)]))
            compact_symbol = self._collapse(symbol_name)

            score = 0
            reasons: list[str] = []

            for idx, phrase in enumerate(query["strong_phrases"]):
                if phrase and phrase in collapsed:
                    bonus = 18 if idx == 0 else 12 if idx < 3 else 8
                    score += bonus
                    reasons.append(f"短语命中 {phrase}")

            for token in query["topic_tokens"]:
                if token and token in owner_name:
                    score += 7
                    reasons.append(f"owner命中 {token}")
                elif token and token in module_path:
                    score += 6
                    reasons.append(f"module命中 {token}")
                elif token and token in normalized:
                    score += 4
                    reasons.append(f"recover命中 {token}")
                elif token and token in ui_names:
                    score += 4
                    reasons.append(f"UI命中 {token}")

            for keyword in query["symbol_keywords"]:
                if keyword and keyword in compact_symbol:
                    score += 7
                    reasons.append(f"symbol匹配 {keyword}")
                elif keyword and keyword in collapsed:
                    score += 3
                    reasons.append(f"链路关键字 {keyword}")

            if query["wants_lifecycle"] and any(
                token in compact_symbol for token in ("abouttoappear", "initialrender", "onpageshow", "build")
            ):
                score += 6
                reasons.append("生命周期入口")

            if query["list_bias"] and any(name in ui_names for name in _LIST_UI_KEYS):
                score += 6
                reasons.append("列表UI命中")

            if query["animation_bias"] and any(token in collapsed for token in ("skeleton", "animation", "gradient")):
                score += 4
                reasons.append("动画/骨架屏命中")

            if query["web_bias"] and any(token in collapsed for token in ("web", "hybrid", "h5")):
                score += 4
                reasons.append("Web/Hybrid 命中")

            if query["search_bias"] and any(token in collapsed for token in ("search", "product", "commodity", "shop", "tn")):
                score += 3
                reasons.append("搜索/商品域命中")

            if owner_type in {"page", "component", "view"}:
                score += 2
                reasons.append(f"owner_type={owner_type}")

            if symbol_name in _GENERIC_SYMBOLS:
                score -= 4
                reasons.append("符号泛化")

            if "lottie" in collapsed and not query["animation_bias"]:
                score -= 10
                reasons.append("偏动画噪声")

            if score <= 0:
                continue

            enriched = dict(row)
            enriched["_score"] = score
            enriched["_reasons"] = self._dedupe_texts(reasons)[:6]
            scored.append(enriched)

        scored = sorted(scored, key=lambda x: (-x["_score"], x.get("file", ""), x.get("line_start", 0)))
        ui_by_symbol = self._collect_ui_hits(scored)

        candidates = []
        for row in scored:
            ui_hits = ui_by_symbol.get(row["id"], [])
            ui_names = [item.get("ui_api") for item in ui_hits if item.get("ui_api")]
            reasons = list(row.get("_reasons", []))
            if ui_names:
                reasons.append(f"UI命中: {', '.join(ui_names[:3])}")
            candidates.append(
                {
                    "file": row.get("file"),
                    "line_start": row.get("line_start"),
                    "line_end": row.get("line_end"),
                    "owner_name": row.get("owner_name"),
                    "owner_type": row.get("owner_type", "unknown"),
                    "symbol_name": row.get("symbol_name"),
                    "module_path": row.get("module_path", ""),
                    "module_path_short": self._short_module_path(row.get("module_path", "")),
                    "ui_keywords": row.get("ui_keywords", []),
                    "matched_ui_hits": ui_hits,
                    "score": row.get("_score", 0),
                    "reasons": self._dedupe_texts(reasons),
                }
            )

        return self._dedupe_candidates(candidates)

    def _score_symbols(
        self,
        owner_keywords: list[str],
        module_keywords: list[str],
        ui_keywords: list[str],
        symbol_keywords: list[str],
    ) -> list[dict[str, Any]]:
        scored = []
        for row in self.symbols:
            owner_name = self._norm(row.get("owner_name"))
            module_path = self._norm(row.get("module_path"))
            symbol_name = self._norm(row.get("symbol_name"))
            owner_type = self._norm(row.get("owner_type"))
            ui_names = [self._norm(item) for item in row.get("ui_keywords", [])]
            line_span = max(1, int((row.get("line_end") or 0) - (row.get("line_start") or 0) + 1))

            score = 0
            reasons: list[str] = []

            for keyword in owner_keywords:
                if keyword and keyword == owner_name:
                    score += 8
                    reasons.append(f"owner精确匹配 {row.get('owner_name')}")
                elif keyword and keyword in owner_name:
                    score += 6
                    reasons.append(f"owner包含 {keyword}")

            for keyword in module_keywords:
                if keyword and keyword in module_path:
                    score += 4
                    reasons.append(f"module包含 {keyword}")

            for keyword in symbol_keywords:
                if keyword and keyword in symbol_name:
                    score += 3
                    reasons.append(f"symbol包含 {keyword}")

            for keyword in ui_keywords:
                if keyword and keyword in ui_names:
                    score += 4
                    reasons.append(f"UI关键字命中 {keyword}")

            if owner_type in {"component", "view"}:
                score += 4
                reasons.append(f"owner_type={owner_type}")
            elif owner_type == "page":
                score += 2
                reasons.append("owner_type=page")

            if symbol_name.endswith(("initialrender", "abouttoappear", "onpageshow", "build")):
                score += 3
                reasons.append("生命周期/渲染入口")

            if ui_names:
                score += min(len(ui_names), 3)

            if line_span > 5000:
                score -= 8
                reasons.append("跨度过大")
            elif line_span > 500:
                score -= 4
                reasons.append("跨度较大")

            if symbol_name in _GENERIC_SYMBOLS:
                score -= 5
                reasons.append("符号过于泛化")

            if score <= 0:
                continue

            enriched = dict(row)
            enriched["_score"] = score
            enriched["_reasons"] = reasons
            scored.append(enriched)

        return sorted(scored, key=lambda x: (-x["_score"], x.get("file", ""), x.get("line_start", 0)))

    def _collect_ui_hits(self, symbol_rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
        by_symbol: dict[str, list[dict[str, Any]]] = {}
        wanted = {row["id"] for row in symbol_rows}
        for item in self.ui_records:
            symbol_id = item.get("symbol_id")
            if symbol_id not in wanted:
                continue
            by_symbol.setdefault(symbol_id, []).append(
                {
                    "ui_api": item.get("ui_api"),
                    "count": item.get("count"),
                    "first_line": item.get("first_line"),
                    "category": item.get("category"),
                }
            )
        return by_symbol

    def _dedupe_candidates(self, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
        exact_unique = []
        seen = set()
        for item in sorted(candidates, key=lambda x: (-x["score"], x.get("file") or "", x.get("line_start") or 0)):
            key = (item.get("file"), item.get("line_start"), item.get("owner_name"), item.get("symbol_name"))
            if key in seen:
                continue
            seen.add(key)
            exact_unique.append(item)

        diversified = []
        deferred = []
        owner_counts: dict[str, int] = {}

        for item in exact_unique:
            owner_key = item.get("module_path") or item.get("owner_name") or item.get("file")
            if owner_counts.get(owner_key, 0) == 0:
                diversified.append(item)
                owner_counts[owner_key] = 1
            else:
                deferred.append(item)

        for item in deferred:
            owner_key = item.get("module_path") or item.get("owner_name") or item.get("file")
            if owner_counts.get(owner_key, 0) >= 2:
                continue
            diversified.append(item)
            owner_counts[owner_key] = owner_counts.get(owner_key, 0) + 1

        return diversified


# ── 模块归因（方向三）────────────────────────────────────────────────────────

# 业务包名 → 中文业务域描述
_BUSINESS_DOMAIN_MAP: dict[str, str] = {
    "business-poi":         "地图/POI搜索",
    "business_poi":         "地图/POI搜索",
    "business-home":        "首页",
    "business_home":        "首页",
    "business-msgcenter":   "消息中心",
    "business_msgcenter":   "消息中心",
    "business-cart":        "购物车",
    "business_cart":        "购物车",
    "business-order":       "订单",
    "business_order":       "订单",
    "business-search":      "搜索",
    "business_search":      "搜索",
    "lib-personal":         "个人中心库",
    "lib_personal":         "个人中心库",
    "lib-common":           "公共组件库",
    "lib_common":           "公共组件库",
    "lib-network":          "网络库",
    "lib_network":          "网络库",
}

_VERSION_RE = re.compile(r"&(\d+\.\d+[\.\d]*)[\.#]")


def _parse_module_path(module_path: str, recovered_from: str = "") -> dict[str, str]:
    """
    从 module_path 解析包名、业务域、层级。
    module_path 示例：
      jd-oh.business-poi.src.main.ets.components.CategorySearchContainer
      jd-oh.lib_personal.src.main.ets.tn.SilkTNContainer
    recovered_from 示例：
      &@jd-oh.business-poi.src.main.ets.components.CategorySearchContainer&2.0.0.#~@0>#aboutToAppear
    """
    if not module_path:
        return {}

    parts = module_path.split(".")
    # 结构: <org>.<package>.<src/...>.<...>.<ClassName>
    org = parts[0] if len(parts) > 0 else ""
    pkg = parts[1] if len(parts) > 1 else ""
    full_package = f"{org}.{pkg}" if org and pkg else pkg

    # 解析 src 后面的层级
    try:
        src_idx = parts.index("src")
        layer_parts = [p for p in parts[src_idx + 1:] if p not in ("main", "ets", "js", "ts")]
        layer = layer_parts[0] if layer_parts else ""
    except ValueError:
        layer = ""

    # 版本号
    version = ""
    vm = _VERSION_RE.search(recovered_from or "")
    if vm:
        version = vm.group(1)

    business = _BUSINESS_DOMAIN_MAP.get(pkg, pkg)

    return {
        "package": f"@{full_package}",
        "version": version,
        "business_domain": business,
        "layer": layer,
    }


def get_module_attributions(
    index_dir: str | Path,
    owner_names: list[str],
) -> dict[str, dict[str, str]]:
    """
    从 symbol_index.jsonl 中为指定组件名列表提取模块归因信息。

    Returns:
        { owner_name: { package, version, business_domain, layer } }
    """
    index_dir = Path(index_dir)
    symbol_index = index_dir / "symbol_index.jsonl"
    if not symbol_index.exists():
        return {}

    target_set = set(owner_names)
    result: dict[str, dict[str, str]] = {}

    with open(symbol_index, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            owner = rec.get("owner_name", "")
            if owner not in target_set or owner in result:
                continue
            mp = rec.get("module_path", "") or ""
            rf = rec.get("recovered_from", "") or ""
            info = _parse_module_path(mp, rf)
            if info:
                result[owner] = info
            if len(result) >= len(target_set):
                break

    return result


def format_module_attribution_text(attributions: dict[str, dict[str, str]]) -> str:
    """将模块归因格式化为 prompt 友好的文本段落。"""
    if not attributions:
        return ""
    lines = ["## 嫌疑组件业务归属\n"]
    for owner, info in attributions.items():
        pkg = info.get("package", "unknown")
        ver = info.get("version", "")
        domain = info.get("business_domain", "")
        layer = info.get("layer", "")
        ver_str = f"@{ver}" if ver else ""
        layer_str = f"（{layer} 层）" if layer else ""
        lines.append(f"- **{owner}**: {pkg}{ver_str}  ←  业务域：**{domain}**{layer_str}")
    return "\n".join(lines)
