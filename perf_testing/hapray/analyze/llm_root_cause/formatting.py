"""Shared string helpers for root-cause evidence (avoid None in joins/format)."""
from __future__ import annotations

from typing import Any


def nonempty_thread_name(value: Any) -> str | None:
    """Return a stripped thread name, or None if missing/blank (caller should skip)."""
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def thread_label(value: Any, *, fallback: str = 'unknown') -> str:
    return nonempty_thread_name(value) or fallback


def wakeup_chain_labels(items: list[dict[str, Any]] | None, *, limit: int = 5) -> list[str]:
    """Ordered wakeup thread names; skips entries without a usable name."""
    labels: list[str] = []
    for item in (items or [])[:limit]:
        if not isinstance(item, dict):
            continue
        name = nonempty_thread_name(item.get('thread_name'))
        if name:
            labels.append(name)
    return labels
