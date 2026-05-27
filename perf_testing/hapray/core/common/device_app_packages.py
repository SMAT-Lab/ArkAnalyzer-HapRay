"""
从 OpenHarmony 设备拉取应用 HAP/包目录，供 root-cause 反编译与索引使用。
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import Callable, Optional

from hapray.core.common.hap_decompiler_bridge import ensure_decompiler_env
from hapray.core.common.root_cause_source import count_files_with_suffix, count_source_files

logger = logging.getLogger(__name__)

ENV_HAP_DECOMPILER_CMD = 'HAPRAY_HAP_DECOMPILER_CMD'
ENV_APP_PACKAGES_DIR = 'HAPRAY_APP_PACKAGES_DIR'
DEFAULT_PACKAGES_DIRNAME = '.app_packages'
MANIFEST_NAME = 'app_packages_manifest.json'

# root-cause 输入类型：decompiled 源码树 vs 仅 HAP 包
ROOT_CAUSE_INPUT_SOURCE = 'source'
ROOT_CAUSE_INPUT_HAP = 'hap'
ROOT_CAUSE_INPUT_NONE = 'none'


def _count_files_with_suffix(path: Path, suffix: str, *, limit: int = 64) -> int:
    """向后兼容别名，见 ``root_cause_source.count_files_with_suffix``。"""
    return count_files_with_suffix(path, suffix, limit=limit)


def _count_source_files(path: Path, *, limit: int = 64) -> int:
    return count_source_files(path, limit=limit)


def _has_symbol_index(index_dir: Path) -> bool:
    return (index_dir / 'symbol_index.jsonl').is_file()


def resolve_decompiled_root(bundle_root: Path) -> Optional[Path]:
    """解析 bundle 目录下的反编译/源码树根（``decompiled/`` 或用户直指的源码树）。"""
    if not bundle_root.is_dir():
        return None

    manifest_path = bundle_root / MANIFEST_NAME
    if manifest_path.is_file():
        try:
            raw = json.loads(manifest_path.read_text(encoding='utf-8'))
            if isinstance(raw, dict):
                declared = (raw.get('decompiled_dir') or '').strip()
                if declared:
                    p = Path(declared)
                    if p.is_dir():
                        return p.resolve()
        except (OSError, json.JSONDecodeError):
            pass

    decompiled = bundle_root / 'decompiled'
    if decompiled.is_dir() and (
        _has_symbol_index(decompiled / 'index')
        or _count_source_files(decompiled) > 0
        or _count_files_with_suffix(decompiled, '.callgraph.json') > 0
    ):
        return decompiled.resolve()

    if _count_source_files(bundle_root) >= 3 or _count_files_with_suffix(
        bundle_root, '.callgraph.json'
    ) > 0:
        return bundle_root.resolve()

    src_main = bundle_root / 'src' / 'main' / 'ets'
    if src_main.is_dir() and _count_source_files(src_main) > 0:
        return bundle_root.resolve()

    return None


def detect_root_cause_input_kind(path: Path) -> str:
    """自动识别目录是反编译/源码（``source``）还是 HAP 包（``hap``）。

    - **source**：含 ``symbol_index.jsonl``、足够 ``*.ts`` / ``*.ets`` / ``*.callgraph.json``，或典型 ``src/main/ets`` 布局
    - **hap**：含 ``*.hap`` 且不具备源码树特征
    - **none**：均不满足
    """
    if not path.is_dir():
        return ROOT_CAUSE_INPUT_NONE

    decompiled = resolve_decompiled_root(path)
    if decompiled is not None:
        index_dir = decompiled / 'index' if decompiled.name == 'decompiled' else decompiled / 'index'
        if decompiled.name == 'decompiled' and _has_symbol_index(index_dir):
            return ROOT_CAUSE_INPUT_SOURCE
        src_under = _count_source_files(decompiled)
        cg_under = _count_files_with_suffix(decompiled, '.callgraph.json')
        if _has_symbol_index(decompiled / 'index') or src_under >= 3 or cg_under > 0:
            return ROOT_CAUSE_INPUT_SOURCE
        if (decompiled / 'src' / 'main' / 'ets').is_dir() and _count_source_files(decompiled / 'src' / 'main' / 'ets') > 0:
            return ROOT_CAUSE_INPUT_SOURCE
        if (path / 'decompiled').is_dir():
            inner = path / 'decompiled'
            if _has_symbol_index(inner / 'index') or _count_source_files(inner) >= 3:
                return ROOT_CAUSE_INPUT_SOURCE
            if (inner / 'src' / 'main' / 'ets').is_dir() and _count_source_files(inner / 'src' / 'main' / 'ets') > 0:
                return ROOT_CAUSE_INPUT_SOURCE

    manifest_path = path / MANIFEST_NAME
    if manifest_path.is_file():
        try:
            raw = json.loads(manifest_path.read_text(encoding='utf-8'))
            if isinstance(raw, dict) and raw.get('input_kind') == ROOT_CAUSE_INPUT_SOURCE:
                declared = (raw.get('decompiled_dir') or '').strip()
                if declared and Path(declared).is_dir() and _count_source_files(Path(declared)) > 0:
                    return ROOT_CAUSE_INPUT_SOURCE
        except (OSError, json.JSONDecodeError):
            pass

    src_count = _count_source_files(path)
    cg_count = _count_files_with_suffix(path, '.callgraph.json')
    if _has_symbol_index(path / 'index') or src_count >= 3 or cg_count > 0:
        return ROOT_CAUSE_INPUT_SOURCE
    if (path / 'src' / 'main' / 'ets').is_dir() and _count_source_files(path / 'src' / 'main' / 'ets') > 0:
        return ROOT_CAUSE_INPUT_SOURCE

    hap_count = len(list(path.glob('*.hap')))
    if (path / 'hap').is_dir():
        hap_count += len(list((path / 'hap').glob('*.hap')))
    if hap_count == 0:
        try:
            hap_count = min(_count_files_with_suffix(path, '.hap'), 8)
        except OSError:
            hap_count = 0
    if hap_count > 0:
        return ROOT_CAUSE_INPUT_HAP

    return ROOT_CAUSE_INPUT_NONE


def looks_like_app_packages_root(path: Path) -> bool:
    """目录是否已具备 root-cause 输入（源码树或 HAP，无需再拉设备）。"""
    return detect_root_cause_input_kind(path) != ROOT_CAUSE_INPUT_NONE


def resolve_user_app_packages_source(cli_path: Optional[str]) -> Optional[Path]:
    if cli_path:
        p = Path(cli_path).expanduser()
        if p.is_dir():
            return p.resolve()
        logger.warning('Ignoring --app-packages-dir (not a directory): %s', cli_path)
    env_val = (os.environ.get(ENV_APP_PACKAGES_DIR) or '').strip()
    if env_val:
        p = Path(env_val).expanduser()
        if p.is_dir():
            return p.resolve()
        logger.warning('Ignoring %s (not a directory): %s', ENV_APP_PACKAGES_DIR, env_val)
    return None


def _write_app_packages_manifest(dest_root: Path, bundle_name: str, data: dict) -> None:
    payload = {'bundle_name': bundle_name, **data}
    try:
        (dest_root / MANIFEST_NAME).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    except OSError as e:
        logger.warning('Failed to write %s: %s', MANIFEST_NAME, e)


def _write_minimal_manifest(dest_root: Path, bundle_name: str, hap_files: list[str]) -> None:
    _write_app_packages_manifest(
        dest_root,
        bundle_name,
        {
            'input_kind': ROOT_CAUSE_INPUT_HAP,
            'hap_files': hap_files,
            'source': 'user_provided',
        },
    )


def _stage_decompiled_source_into_dest(user_source: Path, dest_root: Path) -> Optional[Path]:
    """将用户提供的反编译/源码树落入 ``dest_root/decompiled``。"""
    src = user_source.resolve()
    dest_decompiled = dest_root / 'decompiled'

    if src == dest_decompiled.resolve():
        return dest_decompiled if detect_root_cause_input_kind(dest_decompiled) == ROOT_CAUSE_INPUT_SOURCE else None

    if (src / 'decompiled').is_dir() and detect_root_cause_input_kind(src / 'decompiled') == ROOT_CAUSE_INPUT_SOURCE:
        try:
            shutil.copytree(src / 'decompiled', dest_decompiled, dirs_exist_ok=True)
            return dest_decompiled
        except OSError as e:
            logger.warning('Failed to copy decompiled/ tree: %s', e)
            return None

    if detect_root_cause_input_kind(src) != ROOT_CAUSE_INPUT_SOURCE:
        return None

    try:
        if dest_decompiled.exists():
            shutil.rmtree(dest_decompiled)
        shutil.copytree(src, dest_decompiled, dirs_exist_ok=True)
    except OSError as e:
        logger.warning('Failed to copy source tree into decompiled/: %s', e)
        return None
    return dest_decompiled


def _materialize_user_source_tree(user_source: Path, dest_root: Path, bundle_name: str) -> bool:
    decompiled = _stage_decompiled_source_into_dest(user_source, dest_root)
    if decompiled is None:
        return False
    hap_dir = dest_root / 'hap'
    if hap_dir.is_dir():
        shutil.rmtree(hap_dir)
    index_dir = decompiled / 'index'
    _write_app_packages_manifest(
        dest_root,
        bundle_name,
        {
            'input_kind': ROOT_CAUSE_INPUT_SOURCE,
            'decompiled_dir': str(decompiled.resolve()),
            'index_dir': str(index_dir.resolve()) if index_dir.is_dir() else '',
            'source': 'user_provided',
        },
    )
    logger.info('Staged decompiled source for %s -> %s (skip HAP decompile)', bundle_name, decompiled)
    return True


def _materialize_user_hap_tree(user_source: Path, dest_root: Path, bundle_name: str) -> bool:
    """将用户提供的 HAP 整理到 ``dest_root/hap``（不拷贝无关源码）。"""
    src = user_source.resolve()
    hap_dest = dest_root / 'hap'
    hap_dest.mkdir(parents=True, exist_ok=True)
    downloaded: list[str] = []
    for hap in sorted({p.resolve() for p in src.rglob('*.hap')}):
        target = hap_dest / hap.name
        if target.is_file():
            downloaded.append(str(target))
            continue
        try:
            shutil.copy2(hap, target)
            downloaded.append(str(target))
        except OSError as e:
            logger.warning('Failed to copy HAP %s -> %s: %s', hap, target, e)
    if not downloaded:
        return False
    _write_minimal_manifest(dest_root, bundle_name, downloaded)
    return True


def _materialize_user_app_packages(user_source: Path, dest_root: Path, bundle_name: str) -> bool:
    """将用户提供的 **源码树或 HAP** 整理到 ``dest_root``（自动识别，互斥处理）。"""
    dest_root.mkdir(parents=True, exist_ok=True)
    src = user_source.resolve()
    user_kind = detect_root_cause_input_kind(src)

    if looks_like_app_packages_root(dest_root):
        dest_kind = detect_root_cause_input_kind(dest_root)
        # 用户给了源码树，但报告缓存里只有 HAP → 用用户源码覆盖，勿沿用旧 HAP
        if user_kind == ROOT_CAUSE_INPUT_SOURCE and dest_kind == ROOT_CAUSE_INPUT_HAP:
            logger.info(
                'Replacing cached HAP under %s with user-provided source from %s',
                dest_root,
                src,
            )
        elif dest_kind != ROOT_CAUSE_INPUT_NONE:
            return True

    kind = user_kind

    # 用户已指向 report 下标准布局：<report>/.app_packages/<bundle>
    if src == dest_root.resolve():
        return looks_like_app_packages_root(dest_root)

    # 用户指向 .../.app_packages/<bundle>
    if src.name == bundle_name and src.parent.name == DEFAULT_PACKAGES_DIRNAME:
        if looks_like_app_packages_root(src):
            shutil.copytree(src, dest_root, dirs_exist_ok=True)
            return looks_like_app_packages_root(dest_root)

    # 用户指向 .../.app_packages，取子目录
    if src.name == DEFAULT_PACKAGES_DIRNAME:
        sub = src / bundle_name
        if sub.is_dir() and looks_like_app_packages_root(sub):
            shutil.copytree(sub, dest_root, dirs_exist_ok=True)
            return looks_like_app_packages_root(dest_root)

    # 完整 bundle 布局（manifest 已标明类型，或同时含 hap/ + decompiled/）
    if (src / MANIFEST_NAME).is_file():
        shutil.copytree(src, dest_root, dirs_exist_ok=True)
        return looks_like_app_packages_root(dest_root)

    if kind == ROOT_CAUSE_INPUT_SOURCE:
        return _materialize_user_source_tree(src, dest_root, bundle_name)

    if kind == ROOT_CAUSE_INPUT_HAP:
        if (src / 'hap').is_dir() or (src / 'decompiled').is_dir():
            shutil.copytree(src, dest_root, dirs_exist_ok=True)
            return looks_like_app_packages_root(dest_root)
        return _materialize_user_hap_tree(src, dest_root, bundle_name)

    # 兜底：含 decompiled/ 子目录则按源码，否则尝试 HAP
    if (src / 'decompiled').is_dir():
        shutil.copytree(src, dest_root, dirs_exist_ok=True)
        return looks_like_app_packages_root(dest_root)
    return _materialize_user_hap_tree(src, dest_root, bundle_name)


def stage_user_app_packages_for_bundle(
    user_source: Path,
    report_dir: str,
    bundle_name: str,
) -> Optional[Path]:
    dest = bundle_packages_dir(report_dir, bundle_name)
    if _materialize_user_app_packages(user_source, dest, bundle_name):
        logger.info('Using user-provided app packages for %s -> %s', bundle_name, dest)
        return dest
    return None


def prepare_app_packages_for_report(
    report_dir: str,
    bundle_names: list[str],
    user_source: Optional[Path],
    *,
    device_downloader: Callable[[str, str], Optional[Path]],
) -> tuple[dict[str, Path], str]:
    """准备各 bundle 的本地 HAP 目录。

    Returns:
        (bundle_name -> package_root, source_tag)
        source_tag: ``user`` | ``existing`` | ``device`` | ``none``
    """
    resolved: dict[str, Path] = {}

    if user_source is not None:
        for bundle in bundle_names:
            staged = stage_user_app_packages_for_bundle(user_source, report_dir, bundle)
            if staged:
                prepare_root_cause_artifacts(staged)
                resolved[bundle] = staged
        if resolved:
            return (resolved, 'user')
        logger.warning(
            'User app-packages path did not contain usable source/HAP artifacts: %s. '
            'Will try existing report cache or device pull.',
            user_source,
        )

    for bundle in bundle_names:
        if bundle in resolved:
            continue
        root = bundle_packages_dir(report_dir, bundle)
        if looks_like_app_packages_root(root):
            resolved[bundle] = root

    if bundle_names and len(resolved) == len(bundle_names):
        return (resolved, 'existing')

    for bundle in bundle_names:
        if bundle in resolved:
            continue
        got = device_downloader(bundle, report_dir)
        if got:
            prepare_root_cause_artifacts(got)
            resolved[bundle] = got

    if resolved:
        return (resolved, 'device')
    return ({}, 'none')


def app_packages_ready_for_root_cause(report_dir: str, bundle_name: str) -> bool:
    return looks_like_app_packages_root(bundle_packages_dir(report_dir, bundle_name))


def _parse_json_from_shell_output(out: str) -> Optional[dict]:
    if not out or not out.strip():
        return None
    i = out.find('{')
    if i < 0:
        return None
    try:
        data = json.loads(out[i:])
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def collect_hap_paths_from_bm(data: object, bundle_name: str) -> list[str]:
    """从 bm dump JSON 收集设备上的 .hap 绝对路径（去重）。"""
    seen: set[str] = set()
    out: list[str] = []

    def consider(path: str) -> None:
        p = path.strip().rstrip('/')
        if not p.startswith('/') or not p.lower().endswith('.hap'):
            return
        if bundle_name and bundle_name not in p and f'/bundle/{bundle_name}/' not in p:
            return
        if p in seen:
            return
        seen.add(p)
        out.append(p)

    def walk(obj: object) -> None:
        if isinstance(obj, dict):
            for k, v in obj.items():
                if isinstance(v, str) and k in {
                    'hapPath',
                    'modulePath',
                    'moduleInstallPath',
                    'bundleDataDir',
                    'bundleDataPath',
                    'appDataDir',
                    'hapModulePath',
                }:
                    consider(v)
                else:
                    walk(v)
        elif isinstance(obj, list):
            for x in obj:
                walk(x)
        elif isinstance(obj, str) and obj.startswith('/data/') and obj.lower().endswith('.hap'):
            consider(obj)

    walk(data)
    return out


def collect_bundle_roots_from_bm(data: object, bundle_name: str) -> list[str]:
    """收集可整目录 recv 的安装根路径（用于尽量拉全包内资源）。"""
    keys = {
        'modulePath',
        'hapPath',
        'moduleInstallPath',
        'bundleDataDir',
        'bundleDataPath',
        'appDataDir',
        'hapModulePath',
    }
    roots: list[str] = []
    seen: set[str] = set()

    def walk(obj: object) -> None:
        if isinstance(obj, dict):
            for k, v in obj.items():
                if isinstance(v, str) and k in keys and v.startswith('/'):
                    base = v.rstrip('/')
                    if base.lower().endswith('.hap') or base.lower().endswith('.har'):
                        base = str(Path(base).parent)
                    if bundle_name in base and base not in seen:
                        seen.add(base)
                        roots.append(base)
                else:
                    walk(v)
        elif isinstance(obj, list):
            for x in obj:
                walk(x)

    walk(data)
    return roots


def packages_root_for_report(report_dir: str) -> Path:
    return Path(report_dir) / DEFAULT_PACKAGES_DIRNAME


def bundle_packages_dir(report_dir: str, bundle_name: str) -> Path:
    return packages_root_for_report(report_dir) / bundle_name


def download_app_packages_for_bundle(
    bundle_name: str,
    report_dir: str,
    *,
    run_hdc_cmd: Callable[[list[str], int], tuple[bool, str]],
    looks_like_libs: Callable[[Path], bool],
    try_recv_dir: Callable[[str, Path], bool],
    try_recv_file: Callable[[str, Path], bool],
    timeout_bm: int = 45,
) -> Optional[Path]:
    """拉取 bundle 对应 HAP 文件及可选安装目录，写入 ``<report_dir>/.app_packages/<bundle>/``。"""
    ok, out = run_hdc_cmd(['shell', 'bm', 'dump', '-n', bundle_name], timeout_bm)
    dump = _parse_json_from_shell_output(out) if ok else None
    hap_remotes: list[str] = collect_hap_paths_from_bm(dump, bundle_name) if dump else []
    bundle_roots = collect_bundle_roots_from_bm(dump, bundle_name) if dump else []

    root = bundle_packages_dir(report_dir, bundle_name)
    hap_local = root / 'hap'
    bundle_local = root / 'bundle'
    hap_local.mkdir(parents=True, exist_ok=True)

    downloaded_haps: list[str] = []
    for remote in hap_remotes:
        name = Path(remote).name
        local = hap_local / name
        if local.is_file():
            downloaded_haps.append(str(local))
            continue
        if try_recv_file(remote, local):
            downloaded_haps.append(str(local))
            logger.info('Downloaded HAP %s -> %s', remote, local)
        else:
            logger.warning('Failed to download HAP from device: %s', remote)

    recv_bundle = False
    if bundle_roots:
        for remote_root in bundle_roots[:3]:
            if try_recv_dir(remote_root, bundle_local):
                recv_bundle = True
                logger.info('Downloaded bundle tree %s -> %s', remote_root, bundle_local)
                break

    if not downloaded_haps and not recv_bundle and not looks_like_libs(root / 'libs'):
        return None

    manifest = {
        'bundle_name': bundle_name,
        'input_kind': ROOT_CAUSE_INPUT_HAP,
        'hap_files': downloaded_haps,
        'hap_remote_paths': hap_remotes,
        'bundle_tree_local': str(bundle_local) if recv_bundle and bundle_local.exists() else '',
        'libs_hint': str(root / 'libs') if (root / 'libs').is_dir() else '',
    }
    try:
        (root / MANIFEST_NAME).write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    except OSError as e:
        logger.warning('Failed to write %s: %s', MANIFEST_NAME, e)
    return root


def _ensure_index_for_decompiled_tree(
    bundle_pkg_dir: Path,
    decompiled_root: Path,
) -> tuple[Optional[Path], Optional[Path]]:
    """为已有反编译/源码树构建或复用 ``decompiled/index``。"""
    index_dir = decompiled_root / 'index'
    if _has_symbol_index(index_dir):
        _update_manifest_decompile_paths(bundle_pkg_dir, decompiled_root, index_dir)
        return (decompiled_root, index_dir)

    if _count_source_files(decompiled_root) == 0:
        logger.warning('Source tree under %s has no .ts/.ets files; cannot build index', decompiled_root)
        return (decompiled_root, None)

    index_dir.mkdir(parents=True, exist_ok=True)
    try:
        from hapray.analyze.llm_root_cause.index_builder import build_index

        build_index(decompiled_root, index_dir)
        logger.info('Built root-cause index from source tree at %s', index_dir)
    except Exception as e:
        logger.warning('Root-cause index build from source failed: %s', e)
        return (decompiled_root, None)

    _update_manifest_decompile_paths(bundle_pkg_dir, decompiled_root, index_dir)
    return (decompiled_root, index_dir)


def _decompile_hap_packages(
    bundle_pkg_dir: Path,
    hap_files: list[Path],
    *,
    run_subprocess: Optional[Callable[..., subprocess.CompletedProcess]] = None,
) -> tuple[Optional[Path], Optional[Path]]:
    """对 HAP 包反编译并构建索引（仅 ``input_kind=hap`` 时调用）。"""
    decompiled_root = bundle_pkg_dir / 'decompiled'
    index_dir = decompiled_root / 'index'
    if _has_symbol_index(index_dir):
        return (decompiled_root, index_dir)

    ensure_decompiler_env()
    decompiler_cmd = (os.environ.get(ENV_HAP_DECOMPILER_CMD) or '').strip()
    if not decompiler_cmd:
        logger.warning(
            'HAP package(s) under %s but %s is unset; skipping HAP decompile. '
            'Root-cause will run in analyze mode, or provide a decompiled source tree via --app-packages-dir. '
            'Set e.g. HAPRAY_HAP_DECOMPILER_CMD=\'python /path/to/decompiler.py --input {hap} --output {output}\'',
            bundle_pkg_dir,
            ENV_HAP_DECOMPILER_CMD,
        )
        return (None, None)

    run = run_subprocess or subprocess.run
    for hap in hap_files:
        out_sub = decompiled_root / hap.stem
        out_sub.mkdir(parents=True, exist_ok=True)
        rendered = (
            decompiler_cmd.replace('{hap}', str(hap))
            .replace('{input}', str(hap))
            .replace('{output}', str(out_sub))
            .replace('{bundle}', bundle_pkg_dir.name)
            .replace('{out_dir}', str(bundle_pkg_dir))
        )
        logger.info('Running HAP decompiler: %s', rendered)
        try:
            cp = run(
                rendered,
                shell=True,
                check=False,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
            )
        except OSError as e:
            logger.warning('HAP decompiler failed to start: %s', e)
            return (None, None)
        if cp.returncode != 0:
            logger.warning('HAP decompiler exited %s: %s', cp.returncode, (cp.stderr or cp.stdout or '')[:500])
            return (None, None)

    if _count_files_with_suffix(decompiled_root, '.ts') == 0:
        logger.warning('Decompiler produced no .ts under %s', decompiled_root)
        return (None, None)

    return _ensure_index_for_decompiled_tree(bundle_pkg_dir, decompiled_root)


def prepare_root_cause_artifacts(
    bundle_pkg_dir: Path,
    *,
    run_subprocess: Optional[Callable[..., subprocess.CompletedProcess]] = None,
) -> tuple[Optional[Path], Optional[Path]]:
    """按输入类型准备 root-cause 产物：源码树直接建索引；HAP 包才反编译。

    Returns:
        (decompiled_dir, index_dir)
    """
    kind = detect_root_cause_input_kind(bundle_pkg_dir)
    decompiled = resolve_decompiled_root(bundle_pkg_dir)

    if kind == ROOT_CAUSE_INPUT_SOURCE or decompiled is not None:
        if decompiled is None:
            return (None, None)
        logger.info(
            'Root-cause input: decompiled source (skip HAP decompile) under %s',
            bundle_pkg_dir,
        )
        return _ensure_index_for_decompiled_tree(bundle_pkg_dir, decompiled)

    if kind != ROOT_CAUSE_INPUT_HAP:
        return (None, None)

    manifest_path = bundle_pkg_dir / MANIFEST_NAME
    hap_files: list[Path] = []
    if manifest_path.is_file():
        try:
            raw = json.loads(manifest_path.read_text(encoding='utf-8'))
            if isinstance(raw, dict):
                hap_files = [Path(p) for p in raw.get('hap_files', []) if p]
        except (OSError, json.JSONDecodeError):
            pass
    if not hap_files:
        hap_files = sorted((bundle_pkg_dir / 'hap').glob('*.hap'))
    if not hap_files:
        return (None, None)

    logger.info('Root-cause input: HAP package(s); decompiling %d file(s) under %s', len(hap_files), bundle_pkg_dir)
    return _decompile_hap_packages(bundle_pkg_dir, hap_files, run_subprocess=run_subprocess)


def maybe_decompile_and_index(
    bundle_pkg_dir: Path,
    *,
    run_subprocess: Optional[Callable[..., subprocess.CompletedProcess]] = None,
) -> tuple[Optional[Path], Optional[Path]]:
    """向后兼容别名，见 ``prepare_root_cause_artifacts``。"""
    return prepare_root_cause_artifacts(bundle_pkg_dir, run_subprocess=run_subprocess)


def _update_manifest_decompile_paths(bundle_pkg_dir: Path, decompiled: Path, index_dir: Path) -> None:
    manifest_path = bundle_pkg_dir / MANIFEST_NAME
    data: dict = {}
    if manifest_path.is_file():
        try:
            raw = json.loads(manifest_path.read_text(encoding='utf-8'))
            if isinstance(raw, dict):
                data = raw
        except (OSError, json.JSONDecodeError):
            pass
    data['input_kind'] = ROOT_CAUSE_INPUT_SOURCE
    data['decompiled_dir'] = str(decompiled)
    data['index_dir'] = str(index_dir)
    try:
        manifest_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    except OSError:
        pass


def resolve_root_cause_artifacts(report_dir: str, bundle_name: str) -> tuple[Optional[str], Optional[str]]:
    """读取 manifest / 目录布局，返回 (index_dir, decompiled_dir)。"""
    root = bundle_packages_dir(report_dir, bundle_name)
    decompiled = resolve_decompiled_root(root)
    if decompiled is None:
        return (None, None)

    index_dir = decompiled / 'index'
    if _has_symbol_index(index_dir):
        return (str(index_dir.resolve()), str(decompiled.resolve()))

    manifest_path = root / MANIFEST_NAME
    if manifest_path.is_file():
        try:
            data = json.loads(manifest_path.read_text(encoding='utf-8'))
            if isinstance(data, dict):
                index = (data.get('index_dir') or '').strip()
                if index and Path(index).is_dir() and _has_symbol_index(Path(index)):
                    dec = (data.get('decompiled_dir') or '').strip() or str(decompiled)
                    return (index, dec)
        except (OSError, json.JSONDecodeError):
            pass

    if _count_source_files(decompiled) > 0:
        return (None, str(decompiled.resolve()))
    return (None, None)


def root_cause_llm_mode_for_bundle(report_dir: str, bundle_name: str) -> str:
    """``with_source``：有反编译/源码树；``analyze``：仅 HAP 或无代码片段。"""
    _index, decompiled = resolve_root_cause_artifacts(report_dir, bundle_name)
    if decompiled and Path(decompiled).is_dir():
        if _index or _count_source_files(Path(decompiled)) > 0:
            return 'with_source'
    return 'analyze'
