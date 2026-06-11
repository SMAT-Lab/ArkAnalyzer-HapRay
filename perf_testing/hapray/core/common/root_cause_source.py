"""root-cause 源码树公共定义：反编译 ``*.ts`` 与 HarmonyOS 原生源码 ``*.ets``。"""

from __future__ import annotations

from pathlib import Path

# 反编译 HAP 产出 .ts；HarmonyOS 工程原生源码为 .ets
SOURCE_CODE_SUFFIXES = ('.ts', '.ets')


def count_files_with_suffix(path: Path, suffix: str, *, limit: int = 64) -> int:
    if not path.is_dir():
        return 0
    n = 0
    try:
        for p in path.rglob(f'*{suffix}'):
            if p.is_file():
                n += 1
                if n >= limit:
                    break
    except OSError:
        return 0
    return n


def count_source_files(path: Path, *, limit: int = 64) -> int:
    """统计目录下 ``*.ts`` / ``*.ets`` 文件数（用于 source 判定与 with_source 门禁）。"""
    return sum(count_files_with_suffix(path, suffix, limit=limit) for suffix in SOURCE_CODE_SUFFIXES)


def collect_source_files(input_root: Path) -> list[Path]:
    """递归收集索引/片段提取所需的源码文件。"""
    seen: set[Path] = set()
    for suffix in SOURCE_CODE_SUFFIXES:
        for path in input_root.rglob(f'*{suffix}'):
            if path.is_file():
                seen.add(path)
    return sorted(seen)


def basename_variants(name: str) -> list[str]:
    """同一模块 ``Foo.ets`` / ``Foo.ts`` 文件名互换（/proc 与本地树扩展名可能不一致）。"""
    if not name:
        return []
    variants = [name]
    lower = name.lower()
    if lower.endswith('.ets'):
        variants.append(f'{name[:-4]}.ts')
    elif lower.endswith('.ts'):
        variants.append(f'{name[:-3]}.ets')
    return variants
