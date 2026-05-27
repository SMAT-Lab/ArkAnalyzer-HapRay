"""Helpers to align /proc source hints with decompiled file paths."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from hapray.core.common.root_cause_source import basename_variants


def normalize_path(path: str) -> str:
    return str(path or '').replace('\\', '/')


def source_path_aligned(candidate_file: str, source_path: str) -> bool:
    """True when local source file path corresponds to the /proc source_path."""
    cf = normalize_path(candidate_file).lower()
    sp = normalize_path(source_path).lower()
    if not cf or not sp:
        return False
    if sp in cf:
        return True
    sp_base = sp.rsplit('/', 1)[-1]
    cf_base = cf.rsplit('/', 1)[-1]
    for sp_name in basename_variants(sp_base):
        for cf_name in basename_variants(cf_base):
            if sp_name.lower() == cf_name.lower() and (cf.endswith('/' + cf_name.lower()) or cf.endswith(cf_name.lower())):
                return True
    return bool(sp_base) and (cf.endswith('/' + sp_base) or cf.endswith(sp_base))


def resolve_decompiled_file(decompiled_root: Path, source_path: str) -> Path | None:
    """Find a .ts/.ets/.js file under decompiled_root matching source_path basename."""
    sp = normalize_path(source_path)
    if not sp:
        return None
    base = Path(sp).name
    if not base:
        return None
    tail_parts = [p for p in Path(sp).parts if p not in ('src', 'main', 'ets')]
    best: Path | None = None
    best_score = -1
    for candidate_base in basename_variants(base):
        for path in decompiled_root.rglob(candidate_base):
            if not path.is_file():
                continue
            rel = normalize_path(str(path.relative_to(decompiled_root))).lower()
            score = 0
            if rel.endswith(sp.lower()):
                score += 100
            sp_lower = sp.lower()
            if sp_lower.endswith('.ets') and rel.endswith(sp_lower[:-4] + '.ts'):
                score += 90
            elif sp_lower.endswith('.ts') and rel.endswith(sp_lower[:-3] + '.ets'):
                score += 90
            for part in tail_parts[-3:]:
                if part.lower() in rel:
                    score += 10
            if score > best_score:
                best_score = score
                best = path
    return best


def pick_aligned_candidates(
    hint: dict[str, Any],
    candidates: list[dict[str, Any]],
    *,
    allow_fallback: bool = False,
) -> list[dict[str, Any]]:
    """Return only candidates whose decompiled path matches /proc source_path."""
    source = hint.get('source_path', '')
    aligned = [c for c in candidates if source_path_aligned(c.get('file', ''), source)]
    if aligned:
        return aligned
    if allow_fallback:
        return list(candidates)
    return []
