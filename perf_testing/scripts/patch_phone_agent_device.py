"""
Copyright (c) 2025 Huawei Device Co., Ltd.
Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.

Post-install patch for PyPI phone-agent: fix hdc swipe to use velocity (HarmonyOS uitest).
Runs after ``uv sync`` / pip install; locates ``phone_agent`` via import (any OS / Python path).
Idempotent: safe to run multiple times.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Unpatched template from phone-agent 0.1.x (duration_ms passed to uitest swipe)
_UNPATCHED_SNIPPET = """    hdc_prefix = _get_hdc_prefix(device_id)

    if duration_ms is None:
        # Calculate duration based on distance
        dist_sq = (start_x - end_x) ** 2 + (start_y - end_y) ** 2
        duration_ms = int(dist_sq / 1000)
        duration_ms = max(500, min(duration_ms, 1000))  # Clamp between 500-1000ms

    # HarmonyOS uses uitest uiInput swipe
    # Format: swipe startX startY endX endY duration
    _run_hdc_command(
        hdc_prefix
        + [
            "shell",
            "uitest",
            "uiInput",
            "swipe",
            str(start_x),
            str(start_y),
            str(end_x),
            str(end_y),
            str(duration_ms),
        ],
        capture_output=True,
    )"""

_PATCHED_SNIPPET = """    hdc_prefix = _get_hdc_prefix(device_id)

    # Calculate duration_ms if not provided, then convert to swipeVelocityPps_
    import math

    distance = math.sqrt((start_x - end_x) ** 2 + (start_y - end_y) ** 2)
    if duration_ms is None:
        duration_ms = int(distance**2 / 1000)
    duration_ms = max(500, min(duration_ms, 1000))  # Clamp between 500-1000ms
    swipeVelocityPps_ = int((distance / duration_ms) * 4000)
    swipeVelocityPps_ = max(500, min(swipeVelocityPps_, 40000))  # Clamp between 500-40000 pps

    _run_hdc_command(
        hdc_prefix
        + [
            "shell",
            "uitest",
            "uiInput",
            "swipe",
            str(start_x),
            str(start_y),
            str(end_x),
            str(end_y),
            str(swipeVelocityPps_),
        ],
        capture_output=True,
    )"""


def _device_py_path() -> Path:
    import phone_agent  # noqa: PLC0415

    return Path(phone_agent.__file__).resolve().parent / 'hdc' / 'device.py'


def main() -> int:
    try:
        device_py = _device_py_path()
    except ImportError:
        print('patch_phone_agent_device: phone_agent not installed (install phone-agent first)', file=sys.stderr)
        return 1

    if not device_py.is_file():
        print(f'patch_phone_agent_device: missing {device_py}', file=sys.stderr)
        return 1

    text = device_py.read_text(encoding='utf-8')

    if 'swipeVelocityPps_' in text and 'str(swipeVelocityPps_)' in text:
        print(f'patch_phone_agent_device: already applied ({device_py})')
        return 0

    if _UNPATCHED_SNIPPET not in text:
        print(
            'patch_phone_agent_device: upstream device.py does not match expected template; '
            f'please review {device_py}',
            file=sys.stderr,
        )
        return 1

    device_py.write_text(text.replace(_UNPATCHED_SNIPPET, _PATCHED_SNIPPET), encoding='utf-8')
    print(f'patch_phone_agent_device: patched {device_py}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
