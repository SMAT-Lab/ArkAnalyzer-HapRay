"""
解析 HAP 反编译器路径：环境变量 > skills 内置 decompile_hap.py > 可选 vendor/decompiler.py。
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

ENV_HAP_DECOMPILER_CMD = 'HAPRAY_HAP_DECOMPILER_CMD'
_SKILLS_REL = Path('skills') / 'hapray' / 'tools' / 'hap_decompiler'
_BUILTIN_SCRIPT = 'decompile_hap.py'
_VENDOR_SCRIPT = Path('vendor') / 'decompiler.py'


def find_repo_root(start: Path | None = None) -> Path | None:
    """向上查找含 perf_testing/pyproject.toml 的仓库根。"""
    here = (start or Path(__file__)).resolve()
    for parent in [here, *here.parents]:
        if (parent / 'perf_testing' / 'pyproject.toml').is_file():
            return parent
        if (parent / 'pyproject.toml').is_file() and (parent / 'perf_testing').is_dir():
            return parent
    return None


def skills_decompiler_dir(repo_root: Path | None = None) -> Path | None:
    root = repo_root or find_repo_root()
    if not root:
        return None
    tool_dir = root / _SKILLS_REL
    return tool_dir if tool_dir.is_dir() else None


def resolve_hap_decompiler_cmd() -> str:
    """返回可用于 ``maybe_decompile_and_index`` 的 shell 命令模板。"""
    explicit = (os.environ.get(ENV_HAP_DECOMPILER_CMD) or '').strip()
    if explicit:
        return explicit

    tool_dir = skills_decompiler_dir()
    if not tool_dir:
        return ''

    vendor = tool_dir / _VENDOR_SCRIPT
    builtin = tool_dir / _BUILTIN_SCRIPT
    py = Path(sys.executable)

    if vendor.is_file():
        cmd = f'"{py}" "{vendor}" --input {{hap}} --output {{output}}'
        logger.debug('Using vendor hap decompiler: %s', vendor)
        return cmd
    if builtin.is_file():
        cmd = f'"{py}" "{builtin}" --input {{hap}} --output {{output}}'
        logger.debug('Using skills builtin hap decompiler: %s', builtin)
        return cmd
    return ''


def ensure_decompiler_env() -> bool:
    """若未设置环境变量，则写入解析到的默认命令（仅当前进程）。"""
    if (os.environ.get(ENV_HAP_DECOMPILER_CMD) or '').strip():
        return True
    cmd = resolve_hap_decompiler_cmd()
    if not cmd:
        return False
    os.environ[ENV_HAP_DECOMPILER_CMD] = cmd
    logger.info('Auto-configured %s from skills hap_decompiler', ENV_HAP_DECOMPILER_CMD)
    return True
