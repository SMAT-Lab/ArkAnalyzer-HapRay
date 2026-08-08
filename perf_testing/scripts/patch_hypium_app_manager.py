"""
Copyright (c) 2025 Huawei Device Co., Ltd.
Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.

Post-install patch for PyPI hypium: ``git apply``
``my-dev/third-party/hypium-launcher-ability.diff`` so ``_is_launcher_ability``
also recognizes HarmonyOS NEXT launcher action ``ohos.want.action.home``.

Runs after ``uv sync`` / pip install; locates ``hypium`` via import (any OS / Python path).
Idempotent: safe to run multiple times.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

_DIFF_NAME = 'hypium-launcher-ability.diff'
_ALREADY_MARKERS = (
    'ohos.want.action.home',
    'launcher_actions',
)


def _diff_path() -> Path:
    # scripts/ -> perf_testing/ -> my-dev/third-party/
    return Path(__file__).resolve().parents[2] / 'third-party' / _DIFF_NAME


def _site_packages_and_app_manager() -> tuple[Path, Path]:
    import hypium  # noqa: PLC0415

    pkg_root = Path(hypium.__file__).resolve().parent  # .../site-packages/hypium
    app_manager = pkg_root / 'uidriver' / 'ohos' / 'app_manager.py'
    return pkg_root.parent, app_manager


def _git_apply(diff_file: Path, site_packages: Path, *, reverse: bool = False, check: bool = False) -> subprocess.CompletedProcess[str]:
    """Apply patch under site-packages without using the HapRay git worktree as root."""
    # Absolute --directory needs --unsafe-paths; cwd outside repo avoids worktree path remap.
    cmd = ['git', 'apply', '-p1', '--unsafe-paths', f'--directory={site_packages}']
    if reverse:
        cmd.append('--reverse')
    if check:
        cmd.append('--check')
    cmd.append(str(diff_file))
    return subprocess.run(
        cmd,
        cwd=tempfile.gettempdir(),
        capture_output=True,
        text=True,
        check=False,
    )


def main() -> int:
    diff_file = _diff_path()
    if not diff_file.is_file():
        print(f'patch_hypium_app_manager: missing diff {diff_file}', file=sys.stderr)
        return 1

    try:
        site_packages, app_manager_py = _site_packages_and_app_manager()
    except ImportError:
        print('patch_hypium_app_manager: hypium not installed (install hypium first)', file=sys.stderr)
        return 1

    if not app_manager_py.is_file():
        print(f'patch_hypium_app_manager: missing {app_manager_py}', file=sys.stderr)
        return 1

    text = app_manager_py.read_text(encoding='utf-8')
    if all(m in text for m in _ALREADY_MARKERS):
        print(f'patch_hypium_app_manager: already applied ({app_manager_py})')
        return 0

    # Already applied (content matches reverse of the diff) even if markers differ
    reverse_check = _git_apply(diff_file, site_packages, reverse=True, check=True)
    if reverse_check.returncode == 0:
        print(f'patch_hypium_app_manager: already applied ({app_manager_py})')
        return 0

    check = _git_apply(diff_file, site_packages, check=True)
    if check.returncode != 0:
        detail = (check.stderr or check.stdout or '').strip()
        print(
            f'patch_hypium_app_manager: git apply --check failed for {diff_file.name}: {detail}; '
            f'please review {app_manager_py}',
            file=sys.stderr,
        )
        return 1

    applied = _git_apply(diff_file, site_packages)
    if applied.returncode != 0:
        detail = (applied.stderr or applied.stdout or '').strip()
        print(f'patch_hypium_app_manager: git apply failed: {detail}', file=sys.stderr)
        return 1

    print(f'patch_hypium_app_manager: git apply {diff_file.name} -> {app_manager_py}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
