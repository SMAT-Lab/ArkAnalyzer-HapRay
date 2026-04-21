"""
Copyright (c) 2025 Huawei Device Co., Ltd.
Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
"""

from __future__ import annotations

import csv
import base64
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import zlib
from pathlib import Path
from typing import Optional

from hapray.core.common.common_utils import CommonUtils

logger = logging.getLogger(__name__)

ENV_SO_DIR = 'HAPRAY_SO_DIR'
ENV_TOP_N = 'HAPRAY_SYMBOL_RECOVERY_TOP_N'
ENV_STAT = 'HAPRAY_SYMBOL_RECOVERY_STAT'
ENV_OUTPUT_ROOT = 'HAPRAY_SYMBOL_RECOVERY_OUTPUT'
ENV_SYMBOL_RECOVERY_ROOT = 'HAPRAY_SYMBOL_RECOVERY_ROOT'
ENV_SYMBOL_RECOVERY_PYTHON = 'HAPRAY_SYMBOL_RECOVERY_PYTHON'
# 可选：直接指定符号恢复可执行文件（与源码树并列的独立打包产物，或任意路径的 exe）
ENV_SYMBOL_RECOVERY_EXE = 'HAPRAY_SYMBOL_RECOVERY_EXE'

DEFAULT_TOP_N = 50
DEFAULT_STAT = 'event_count'

# 与 tools/symbol_recovery/core/utils/config.py 中 LLM 就绪判定一致（避免依赖已解析的 symbol_recovery 根目录）
_SR_LLM_SERVICE_API_KEYS: dict[str, str] = {
    'poe': 'POE_API_KEY',
    'openai': 'OPENAI_API_KEY',
    'claude': 'ANTHROPIC_API_KEY',
    'deepseek': 'DEEPSEEK_API_KEY',
}
_SR_LLM_SERVICE_BASE_URLS: dict[str, str] = {
    'poe': 'https://api.poe.com/v1',
    'openai': 'https://api.openai.com/v1',
    'claude': 'https://api.anthropic.com/v1',
    'deepseek': 'https://api.deepseek.com/v1',
}

# HapRay 桌面端 ~/.hapray-gui/config.json 中的键（与 desktop config_object_to_env_vars 大写规则一致）
_GUI_JSON_LLM_KEYS: tuple[tuple[str, str], ...] = (
    ('llm_api_key', 'LLM_API_KEY'),
    ('llm_base_url', 'LLM_BASE_URL'),
    ('llm_model', 'LLM_MODEL'),
    ('llm_service_type', 'LLM_SERVICE_TYPE'),
    ('llm_timeout', 'LLM_TIMEOUT'),
)


def _json_config_scalar_to_str(value: object) -> str:
    if value is None or isinstance(value, (dict, list)):
        return ''
    if isinstance(value, bool):
        return 'true' if value else ''
    s = str(value).strip()
    return s


def try_load_llm_from_hapray_gui_config() -> None:
    """将 ~/.hapray-gui/config.json 中的 LLM 项写入环境变量（仅当对应变量尚未设置或为空）。

    与桌面端启动 perf-testing 时注入的环境一致；便于用户直接命令行运行 exe 时仍使用 GUI 里保存的 Key/URL。
    """
    path = Path.home() / '.hapray-gui' / 'config.json'
    if not path.is_file():
        return
    try:
        raw = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, UnicodeError, json.JSONDecodeError) as e:
        logger.debug('Skip HapRay GUI config LLM merge: %s', e)
        return
    if not isinstance(raw, dict):
        return

    chunks: list[dict] = []
    global_obj = {k: v for k, v in raw.items() if k != 'plugins'}
    if global_obj:
        chunks.append(global_obj)
    plugins = raw.get('plugins')
    if isinstance(plugins, dict):
        for _pid, wrap in plugins.items():
            if not isinstance(wrap, dict):
                continue
            cfg = wrap.get('config')
            if isinstance(cfg, dict):
                chunks.append(cfg)

    merged: dict[str, str] = {}
    for chunk in chunks:
        for json_key, env_key in _GUI_JSON_LLM_KEYS:
            if json_key not in chunk:
                continue
            val = _json_config_scalar_to_str(chunk[json_key])
            if val:
                merged[env_key] = val

    applied = False
    for env_key, val in merged.items():
        if os.environ.get(env_key, '').strip():
            continue
        os.environ[env_key] = val
        applied = True
    if applied:
        logger.debug('Applied LLM-related env from HapRay GUI config: %s', path)


def try_load_dotenv_for_llm() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        load_dotenv = None  # type: ignore[assignment,misc]
    if load_dotenv is not None:
        roots = [
            CommonUtils.get_project_root(),
            CommonUtils.get_project_root().parent,
        ]
        for root in roots:
            env_path = root / '.env'
            if env_path.is_file():
                load_dotenv(env_path, override=False)
    try_load_llm_from_hapray_gui_config()


def _resolved_llm_api_key_and_base_url() -> tuple[str, str]:
    """与 symbol_recovery ``is_llm_ready_for_symbol_recovery`` 相同的解析规则（仅读环境变量）。"""
    st = os.environ.get('LLM_SERVICE_TYPE', '').strip().lower()
    api = (os.environ.get('LLM_API_KEY') or '').strip()
    if not api and st in _SR_LLM_SERVICE_API_KEYS:
        api = (os.environ.get(_SR_LLM_SERVICE_API_KEYS[st]) or '').strip()
    base = (os.environ.get('LLM_BASE_URL') or '').strip()
    if not base and st in _SR_LLM_SERVICE_BASE_URLS:
        base = _SR_LLM_SERVICE_BASE_URLS[st]
    return api, base


def llm_env_ready_for_symbol_recovery() -> bool:
    """是否已具备符号恢复子进程所需的 LLM 环境（API Key + Base URL，与 symbol_recovery 一致）。"""
    api, base = _resolved_llm_api_key_and_base_url()
    return bool(api and base)


def check_symbol_recovery_llm_ready() -> bool:
    """向后兼容别名：仅表示 LLM 环境是否就绪，不依赖 symbol_recovery 目录是否已找到。"""
    return llm_env_ready_for_symbol_recovery()


def _symbol_recovery_root_candidates(perf_root: Path) -> list[Path]:
    """
    在无需显式配置时，按相对布局探测 ``.../tools/symbol_recovery``。

    顺序（去重）：
    1. ``<perf_root 的父目录>/tools/symbol_recovery`` — 典型源码树：仓库根下 tools（perf_testing 与 tools 为兄弟）
    2. ``<perf_root>/tools/symbol_recovery`` — 将 symbol_recovery 打进/放在 perf-testing 插件目录旁
    3. 自 ``perf_root`` 起向上若干级祖先，每级尝试 ``<祖先>/tools/symbol_recovery`` — 适配打包后 exe 位于深层子目录、
       仓库或发布包在更上层仍保留 ``tools/symbol_recovery`` 的情况
    """
    seen: set[Path] = set()
    out: list[Path] = []

    def push(base: Path) -> None:
        try:
            c = (base / 'tools' / 'symbol_recovery').resolve()
        except OSError:
            return
        if c not in seen:
            seen.add(c)
            out.append(c)

    try:
        pr = perf_root.resolve()
    except OSError:
        return out

    push(pr.parent)
    push(pr)
    cur = pr
    for _ in range(8):
        parent = cur.parent
        if parent == cur:
            break
        cur = parent
        push(cur)
    return out


def resolve_symbol_recovery_root() -> Optional[Path]:
    raw = os.environ.get(ENV_SYMBOL_RECOVERY_ROOT, '').strip()
    if raw:
        root = Path(raw).expanduser().resolve()
        if (root / 'main.py').is_file():
            return root
        logger.warning('%s is set but main.py not found under: %s', ENV_SYMBOL_RECOVERY_ROOT, root)
        return None

    perf_root = CommonUtils.get_project_root()
    for cand in _symbol_recovery_root_candidates(perf_root):
        if (cand / 'main.py').is_file():
            logger.debug('Resolved symbol recovery root (relative search): %s', cand)
            return cand

    logger.debug(
        'Symbol recovery root not found under perf_root=%s (set %s or place tools/symbol_recovery on an ancestor path)',
        perf_root,
        ENV_SYMBOL_RECOVERY_ROOT,
    )
    return None


def _symbol_recovery_venv_python_candidates(sr_root: Path) -> list[Path]:
    """``symbol_recovery`` 仓库内常见虚拟环境布局（uv/pip）：``venv`` / ``.venv``。"""
    out: list[Path] = []
    for vname in ('venv', '.venv'):
        base = sr_root / vname
        if sys.platform == 'win32':
            exe = base / 'Scripts' / 'python.exe'
            if exe.is_file():
                out.append(exe)
        else:
            for bin_name in ('python3', 'python'):
                exe = base / 'bin' / bin_name
                if exe.is_file():
                    out.append(exe)
                    break
    return out


def _symbol_recovery_entrypoint_exe_candidates(sr_root: Path) -> list[Path]:
    """符号恢复「可执行入口」：与 ``pyproject [project.scripts]`` 一致的 ``symbol-recovery``，或目录下独立 exe。

    顺序：各 ``venv``/``.venv`` 内控制台脚本 → 源码根目录下常见 PyInstaller 产物名。
    """
    out: list[Path] = []
    seen: set[Path] = set()
    for vname in ('venv', '.venv'):
        base = sr_root / vname
        if sys.platform == 'win32':
            for name in ('symbol-recovery.exe', 'symbol_recovery.exe'):
                p = base / 'Scripts' / name
                if p.is_file():
                    rp = p.resolve()
                    if rp not in seen:
                        seen.add(rp)
                        out.append(rp)
        else:
            p = base / 'bin' / 'symbol-recovery'
            if p.is_file():
                rp = p.resolve()
                if rp not in seen:
                    seen.add(rp)
                    out.append(rp)
    if sys.platform == 'win32':
        for name in ('symbol-recovery.exe', 'symbol_recovery.exe', 'SymRecover.exe'):
            p = (sr_root / name).resolve()
            if p.is_file() and p not in seen:
                seen.add(p)
                out.append(p)
    else:
        for name in ('symbol-recovery', 'symbol_recovery'):
            p = (sr_root / name).resolve()
            if p.is_file() and p not in seen:
                seen.add(p)
                out.append(p)
    return out


def resolve_symbol_recovery_exe(sr_root: Path) -> Optional[Path]:
    """解析用于子进程的符号恢复可执行文件；未配置则扫描 ``sr_root`` 下常见入口。"""
    raw = os.environ.get(ENV_SYMBOL_RECOVERY_EXE, '').strip()
    if raw:
        p = Path(raw).expanduser()
        if p.is_file():
            return p.resolve()
        logger.warning('%s is not a file: %s', ENV_SYMBOL_RECOVERY_EXE, raw)
        return None
    for cand in _symbol_recovery_entrypoint_exe_candidates(sr_root):
        return cand
    return None


def resolve_symbol_recovery_python() -> Optional[str]:
    explicit = os.environ.get(ENV_SYMBOL_RECOVERY_PYTHON, '').strip()
    if explicit:
        p = Path(explicit).expanduser()
        if p.is_file():
            return str(p.resolve())
        logger.warning('%s is not a file: %s', ENV_SYMBOL_RECOVERY_PYTHON, explicit)
        return None

    sr_root = resolve_symbol_recovery_root()
    if sr_root:
        for cand in _symbol_recovery_venv_python_candidates(sr_root):
            try:
                resolved = str(cand.resolve())
            except OSError:
                continue
            logger.info('Symbol recovery: using interpreter from symbol_recovery venv: %s', resolved)
            return resolved

    if not getattr(sys, 'frozen', False):
        return sys.executable

    for name in ('python3', 'python'):
        found = shutil.which(name)
        if found:
            logger.info(
                'Packaged perf-testing: using %r from PATH for symbol recovery '
                '(prefer %s under tools/symbol_recovery, or %s / %s)',
                found,
                'venv/Scripts/symbol-recovery.exe' if sys.platform == 'win32' else 'venv/bin/symbol-recovery',
                ENV_SYMBOL_RECOVERY_EXE,
                ENV_SYMBOL_RECOVERY_PYTHON,
            )
            return found

    logger.warning(
        'Packaged perf-testing: no Python on PATH for symbol recovery; set %s, %s, or install venv + symbol-recovery entrypoint under symbol_recovery.',
        ENV_SYMBOL_RECOVERY_EXE,
        ENV_SYMBOL_RECOVERY_PYTHON,
    )
    return None


def _ensure_symbol_recovery_on_syspath(sr_root: Path) -> None:
    s = str(sr_root.resolve())
    if s not in sys.path:
        sys.path.insert(0, s)


def resolve_effective_so_dir(cli_so_dir: Optional[str]) -> tuple[Optional[str], str]:
    if cli_so_dir:
        p = Path(cli_so_dir).expanduser()
        if p.is_dir():
            return (str(p.resolve()), 'cli')
        logger.warning('Ignoring --so_dir (not a directory): %s', cli_so_dir)
    env_val = os.environ.get(ENV_SO_DIR, '').strip()
    if env_val:
        p = Path(env_val).expanduser()
        if p.is_dir():
            return (str(p.resolve()), 'env')
        logger.warning('Ignoring %s (not a directory): %s', ENV_SO_DIR, env_val)
    return (None, 'none')


def symbol_recovery_excel_name(stat_method: str, top_n: int) -> str:
    if stat_method == 'call_count':
        return f'call_count_top{top_n}_analysis.xlsx'
    return f'event_count_top{top_n}_analysis.xlsx'


def symbol_recovery_report_name(stat_method: str, top_n: int) -> str:
    """与 tools/symbol_recovery 中 EVENT_COUNT_REPORT_PATTERN / CALL_COUNT_REPORT_PATTERN 一致。"""
    if stat_method == 'call_count':
        return f'call_count_top{top_n}_report.html'
    return f'event_count_top{top_n}_report.html'


def symbol_recovery_replaced_html_name(html_input_name: str) -> str:
    """Step4 产出的增强火焰图文件名（带推断符号与详细分析 tab）。"""
    p = Path(html_input_name)
    return f'{p.stem}_with_inferred_symbols{p.suffix or ".html"}'


# 与 perf.json 中已由符号恢复写回的 ``名称 [反推，仅供参考] (lib*.so+0x...)`` 一致
_RE_EXISTING_INFERRED = re.compile(
    r'(?P<replaced>[^"\\]+?)\s*\[反推，仅供参考\]\s*\((?P<original>lib[\w_]+\.so\+0x[0-9a-fA-F]+)\)',
    re.IGNORECASE,
)
_RE_SO_ADDR = re.compile(r'lib[\w_]+\.so\+0x[0-9a-fA-F]+', re.IGNORECASE)


def _collect_existing_replacements_from_perf_json_text(json_text: str) -> list[dict[str, str]]:
    """二次 update 时从已有 perf.json 回收「地址 → 反推名」，避免清单显示 0 条。"""
    merged: dict[str, str] = {}
    for m in _RE_EXISTING_INFERRED.finditer(json_text):
        orig = m['original']
        rep = m['replaced'].strip()
        if orig and rep:
            merged[orig] = rep
    return [{'original': k, 'replaced': v} for k, v in sorted(merged.items())]


def _save_replacement_manifest(step_hiperf_dir: Path, rows: list[dict[str, str]]) -> None:
    """在 hiperf 目录写入替换清单（JSON + CSV）。"""
    try:
        step_hiperf_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        return
    jpath = step_hiperf_dir / 'symbol_recovery_replacements.json'
    cpath = step_hiperf_dir / 'symbol_recovery_replacements.csv'
    try:
        jpath.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding='utf-8')
    except OSError:
        logger.warning('Symbol recovery: failed to write %s', jpath)
    try:
        with cpath.open('w', encoding='utf-8', newline='') as f:
            w = csv.DictWriter(f, fieldnames=['original', 'replaced'])
            w.writeheader()
            for row in rows:
                w.writerow({'original': row.get('original', ''), 'replaced': row.get('replaced', '')})
    except OSError:
        logger.warning('Symbol recovery: failed to write %s', cpath)


def _load_replacement_manifest(step_hiperf_dir: Path) -> dict[str, str]:
    """读取 symbol_recovery_replacements.json，返回 地址->函数名 映射。"""
    manifest = step_hiperf_dir / 'symbol_recovery_replacements.json'
    if not manifest.is_file():
        return {}
    try:
        raw = json.loads(manifest.read_text(encoding='utf-8', errors='replace'))
    except (OSError, json.JSONDecodeError):
        logger.debug('Symbol recovery: failed to parse manifest %s', manifest)
        return {}
    if not isinstance(raw, list):
        return {}
    mapping: dict[str, str] = {}
    for item in raw:
        if not isinstance(item, dict):
            continue
        addr = str(item.get('original', '')).strip()
        rep = str(item.get('replaced', '')).strip()
        if addr and rep:
            mapping[addr] = rep
    return mapping


def load_symbol_recovery_mapping_for_step(scene_dir: str, step_dir: str) -> dict[str, str]:
    """读取指定 step 的地址->函数名映射。

    优先读取 ``symbol_recovery_replacements.json``；
    若为空，则回退读取 ``.symbol_recovery/<step>/<stat>_topN_analysis.xlsx``。
    """
    if not scene_dir or not step_dir:
        return {}
    step_hiperf = Path(scene_dir) / 'hiperf' / step_dir
    mapping = _load_replacement_manifest(step_hiperf)
    if mapping:
        return mapping
    return _load_mapping_from_symbol_recovery_excel(scene_dir, step_dir)


def _load_mapping_from_symbol_recovery_excel(scene_dir: str, step_dir: str) -> dict[str, str]:
    try:
        from hapray.core.config.config import Config
    except Exception:
        return {}

    top_n = int(Config.get('symbol_recovery_top_n', DEFAULT_TOP_N) or DEFAULT_TOP_N)
    stat_method = (Config.get('symbol_recovery_stat_method', DEFAULT_STAT) or DEFAULT_STAT).strip()
    if stat_method not in ('event_count', 'call_count'):
        stat_method = DEFAULT_STAT
    output_root = (Config.get('symbol_recovery_output_root', '') or '').strip() or None
    out_dir = default_symbol_recovery_output_dir(scene_dir, step_dir, output_root)
    excel_path = out_dir / symbol_recovery_excel_name(stat_method, top_n)
    if not excel_path.is_file():
        return {}
    try:
        import pandas as pd
    except Exception:
        logger.debug('Symbol recovery: pandas unavailable, skip excel mapping fallback')
        return {}
    try:
        df = pd.read_excel(excel_path, engine='openpyxl')
    except Exception:
        logger.debug('Symbol recovery: failed reading excel %s', excel_path)
        return {}

    mapping: dict[str, str] = {}
    for _, row in df.iterrows():
        addr = str(row.get('地址', '')).strip()
        fn = str(row.get('LLM推断函数名', '')).strip()
        if not addr or not fn or fn in {'nan', 'None'}:
            continue
        if not fn.startswith('Function: '):
            fn = f'Function: {fn}'
        mapping[addr] = fn
    if mapping:
        logger.info('Loaded %d symbol recovery mappings from excel fallback: %s', len(mapping), excel_path)
    return mapping


def recover_symbol_name_from_mapping(mapping: dict[str, str], *candidates: Optional[str]) -> Optional[str]:
    """从候选文本中提取 lib*.so+0x... 并按 mapping 转为反推符号。"""
    if not mapping or not candidates:
        return None
    lower_mapping = {k.lower(): v for k, v in mapping.items()}
    for text in candidates:
        if not text:
            continue
        m = _RE_SO_ADDR.search(str(text))
        if not m:
            continue
        addr = m.group(0)
        fn = mapping.get(addr) or lower_mapping.get(addr.lower())
        if fn:
            return f'{fn} [反推，仅供参考] ({addr})'
    return None


def recover_symbol_name_from_callchain_fields(
    mapping: dict[str, str],
    *,
    symbol: Optional[str],
    path: Optional[str],
    callchain_name: Optional[str],
    ip: Optional[int],
    vaddr_in_file: Optional[int],
    offset_to_vaddr: Optional[int] = None,
) -> Optional[str]:
    """从调用链字段恢复反推符号。

    优先从 symbol/path/name 直接提取 ``lib*.so+0x...``；
    若没有地址字符串，则用 ``basename(path) + (ip-vaddr_in_file)`` 组装地址再匹配。
    """
    got = recover_symbol_name_from_mapping(mapping, symbol, path, callchain_name)
    if got:
        return got
    if not mapping or not path:
        return None
    try:
        ip_val = int(ip) if ip is not None else 0
        vaddr_val = int(vaddr_in_file) if vaddr_in_file is not None else 0
        offset_val = int(offset_to_vaddr) if offset_to_vaddr is not None else 0
    except (TypeError, ValueError):
        return None
    m = re.search(r'(lib[\w_]+\.so)', str(path), re.IGNORECASE)
    if not m:
        return None
    so_name = m.group(1)
    offsets: list[int] = []
    if ip_val > 0 and vaddr_val > 0 and ip_val >= vaddr_val:
        offsets.append(ip_val - vaddr_val)
    if vaddr_val > 0:
        offsets.append(vaddr_val)
    if offset_val > 0:
        offsets.append(offset_val)
        if vaddr_val > 0:
            offsets.append(vaddr_val + offset_val)
        if ip_val > 0 and ip_val >= offset_val:
            offsets.append(ip_val - offset_val)

    lower_mapping = {k.lower(): v for k, v in mapping.items()}
    seen_offsets: set[int] = set()
    for off in offsets:
        if off < 0 or off in seen_offsets:
            continue
        seen_offsets.add(off)
        addr = f'{so_name}+0x{off:x}'
        fn = mapping.get(addr) or mapping.get(addr.lower()) or lower_mapping.get(addr.lower())
        if fn:
            return f'{fn} [反推，仅供参考] ({addr})'
    return None


def _apply_address_mapping_to_text(raw_text: str, mapping: dict[str, str]) -> tuple[str, int]:
    """在任意文本中按地址替换为反推符号（幂等）。"""
    if not raw_text or not mapping:
        return raw_text, 0

    lower_mapping = {k.lower(): v for k, v in mapping.items()}
    replaced = {'count': 0}

    def _repl(m: re.Match[str]) -> str:
        addr = m.group(0)
        fn = mapping.get(addr) or lower_mapping.get(addr.lower())
        if not fn:
            return addr
        start, end = m.span()
        prev = raw_text[max(0, start - 32) : start]
        nxt = raw_text[end : min(len(raw_text), end + 2)]
        # 已经是 "... [反推，仅供参考] (libxxx.so+0x...)" 时保持幂等
        if '[反推，仅供参考] (' in prev and nxt.startswith(')'):
            return addr
        replaced['count'] += 1
        return f'{fn} [反推，仅供参考] ({addr})'

    new_text = _RE_SO_ADDR.sub(_repl, raw_text)
    return new_text, replaced['count']


def _apply_mapping_to_hiperf_html_payload(html_text: str, mapping: dict[str, str]) -> tuple[str, int]:
    """处理 hiperf_report.html 中 record_data 压缩载荷，替换后重新压缩。"""
    m = re.search(
        r'(<script\s+id=["\']record_data["\'][^>]*>)(.*?)(</script>)',
        html_text,
        re.IGNORECASE | re.DOTALL,
    )
    if not m:
        return html_text, 0
    payload_b64 = m.group(2).strip()
    if not payload_b64:
        return html_text, 0
    try:
        decoded = base64.b64decode(payload_b64)
        json_text = zlib.decompress(decoded).decode('utf-8', errors='replace')
    except Exception:
        return html_text, 0

    new_json, changed = _apply_address_mapping_to_text(json_text, mapping)
    if changed <= 0:
        return html_text, 0
    reencoded = base64.b64encode(zlib.compress(new_json.encode('utf-8'), level=9)).decode('ascii')
    replaced_html = html_text[: m.start(2)] + reencoded + html_text[m.end(2) :]
    return replaced_html, changed


def apply_symbol_recovery_manifest_to_scene_outputs(scene_dir: str) -> int:
    """将每个 step 的替换清单回写到报告产物（report/*.json 与 hiperf_report.html）。"""
    scene = Path(scene_dir)
    if not scene.is_dir():
        return 0

    total_replaced = 0
    manifest_files = sorted(scene.rglob('symbol_recovery_replacements.json'))
    for manifest in manifest_files:
        manifest_parent = manifest.parent
        step: Optional[Path] = None
        step_hiperf: Optional[Path] = None
        # 兼容两种布局：
        # 1) scene/step1/hiperf/symbol_recovery_replacements.json
        # 2) scene/hiperf/step1/symbol_recovery_replacements.json
        if manifest_parent.name == 'hiperf':
            step_hiperf = manifest_parent
            step = manifest_parent.parent
        elif manifest_parent.parent.name == 'hiperf':
            step = manifest_parent
            step_hiperf = manifest_parent
        if step_hiperf is None or step is None:
            continue
        mapping = _load_replacement_manifest(step_hiperf)
        if not mapping:
            continue

        targets: list[Path] = []
        report_dir = scene / 'report'
        if report_dir.is_dir():
            targets.extend(sorted(report_dir.glob('*.json')))
        hiperf_info = scene / 'hiperf' / 'hiperf_info.json'
        if hiperf_info.is_file():
            targets.append(hiperf_info)
        step_report = step / 'report'
        if step_report.is_dir():
            targets.extend(sorted(step_report.glob('*.json')))
        for p in ('perf.json', 'hiperf_report.html'):
            fp = step_hiperf / p
            if fp.is_file():
                targets.append(fp)

        seen: set[str] = set()
        dedup_targets: list[Path] = []
        for fp in targets:
            key = str(fp.resolve())
            if key in seen:
                continue
            seen.add(key)
            dedup_targets.append(fp)

        for fp in dedup_targets:
            try:
                raw = fp.read_text(encoding='utf-8', errors='replace')
                if fp.name == 'hiperf_report.html':
                    new_text, changed = _apply_mapping_to_hiperf_html_payload(raw, mapping)
                    if changed <= 0:
                        new_text, changed = _apply_address_mapping_to_text(raw, mapping)
                else:
                    new_text, changed = _apply_address_mapping_to_text(raw, mapping)
                if changed > 0:
                    fp.write_text(new_text, encoding='utf-8')
                    total_replaced += changed
            except OSError:
                logger.debug('Symbol recovery post-process skip unreadable file: %s', fp)

    if total_replaced > 0:
        logger.info('Symbol recovery post-process applied %d replacements under scene: %s', total_replaced, scene_dir)
    return total_replaced


_EMBED_MARKER = '<!-- hapray-symbol-recovery-embedded -->'


def embed_symbol_recovery_report_into_hiperf_html(
    hiperf_report_html: Path,
    symbol_recovery_detail_html: Path,
) -> bool:
    """在 hiperf_report.html 末尾嵌入符号恢复详细页（iframe）。若详细页不存在则不改文件。"""
    if not hiperf_report_html.is_file():
        return False
    if not symbol_recovery_detail_html.is_file():
        return False
    try:
        text = hiperf_report_html.read_text(encoding='utf-8', errors='replace')
    except OSError:
        return False
    if _EMBED_MARKER in text or 'hapray-symbol-recovery-panel' in text:
        return True
    rel = os.path.relpath(symbol_recovery_detail_html, hiperf_report_html.parent)
    rel_s = rel.replace('\\', '/')
    block = f"""{_EMBED_MARKER}
<div id="hapray-symbol-recovery-panel" style="margin:16px;">
<h2 style="font-family:sans-serif;">符号恢复分析报告</h2>
<iframe title="symbol recovery" src="{rel_s}" style="width:100%;min-height:480px;border:1px solid #ccc;"></iframe>
</div>
"""
    lower = text.lower()
    idx = lower.rfind('</body>')
    if idx != -1:
        new_text = text[:idx] + block + '\n' + text[idx:]
    else:
        new_text = text + '\n' + block
    try:
        hiperf_report_html.write_text(new_text, encoding='utf-8')
    except OSError:
        return False
    logger.info('Embedded symbol recovery detail into %s', hiperf_report_html)
    return True


def build_symbol_recovery_argv(
    *,
    sr_root: Path,
    entry_exe: Optional[Path],
    python_exe: Optional[str],
    perf_data: Path,
    perf_db: Path,
    so_dir: str,
    output_dir: Path,
    top_n: int,
    stat_method: str,
    extra_args: Optional[list[str]] = None,
) -> list[str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    tail = [
        '--skip-step1',
        '--perf-data',
        str(perf_data),
        '--perf-db',
        str(perf_db),
        '--so-dir',
        so_dir,
        '--output-dir',
        str(output_dir),
        '--top-n',
        str(top_n),
        '--stat-method',
        stat_method,
    ]
    if entry_exe is not None:
        cmd = [str(entry_exe), *tail]
    elif python_exe:
        main_py = sr_root / 'main.py'
        cmd = [python_exe, str(main_py), *tail]
    else:
        raise ValueError('entry_exe and python_exe cannot both be unset')
    if extra_args:
        cmd.extend(extra_args)
    return cmd


def build_symbol_recovery_html_argv(
    *,
    sr_root: Path,
    entry_exe: Optional[Path],
    python_exe: Optional[str],
    html_input: Path,
    output_dir: Path,
    top_n: int,
    stat_method: str,
) -> list[str]:
    """构建 symbol_recovery Step4 命令，生成新的增强火焰图 HTML。"""
    output_dir.mkdir(parents=True, exist_ok=True)
    tail = [
        '--only-step4',
        '--html-input',
        str(html_input),
        '--output-dir',
        str(output_dir),
        '--top-n',
        str(top_n),
        '--stat-method',
        stat_method,
    ]
    if entry_exe is not None:
        return [str(entry_exe), *tail]
    if python_exe:
        return [python_exe, str(sr_root / 'main.py'), *tail]
    raise ValueError('entry_exe and python_exe cannot both be unset')


def run_symbol_recovery_subprocess(argv: list[str], *, cwd: Path, timeout_sec: Optional[float] = None) -> int:
    logger.info('Symbol recovery subprocess: %s', ' '.join(argv))
    env = os.environ.copy()
    try:
        completed = subprocess.run(
            argv,
            cwd=str(cwd),
            env=env,
            timeout=timeout_sec,
            check=False,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
        )
    except subprocess.TimeoutExpired:
        logger.error('Symbol recovery subprocess timed out')
        return -1
    if completed.stdout:
        logger.debug(completed.stdout[:8000])
    if completed.stderr:
        logger.info(completed.stderr[:8000])
    if completed.returncode != 0:
        logger.warning('Symbol recovery exited with code %s', completed.returncode)
    return int(completed.returncode)


def load_mapping_and_apply_perf_json(sr_root: Path, excel_path: Path, perf_json_path: Path) -> bool:
    _ensure_symbol_recovery_on_syspath(sr_root)
    try:
        from core.utils.symbol_replacer import apply_function_mapping_to_perf_json_text, load_function_mapping
    except Exception:
        logger.exception('Failed to import symbol_replacer')
        return False
    if not excel_path.is_file():
        logger.warning('Symbol recovery Excel not found: %s', excel_path)
        return False
    if not perf_json_path.is_file():
        logger.warning('perf.json not found: %s', perf_json_path)
        return False
    try:
        mapping = load_function_mapping(excel_path)
    except Exception:
        logger.exception('Failed to load function mapping from %s', excel_path)
        return False
    if not mapping:
        logger.warning('Empty function mapping from %s', excel_path)
        return False
    try:
        raw = perf_json_path.read_text(encoding='utf-8', errors='replace')
        existing_rows = _collect_existing_replacements_from_perf_json_text(raw)
        new_text, replacement_info = apply_function_mapping_to_perf_json_text(raw, mapping)
        merged_by_addr: dict[str, str] = {r['original']: r['replaced'] for r in existing_rows}
        for r in replacement_info:
            merged_by_addr[r['original']] = r['replaced']
        merged_rows = [{'original': k, 'replaced': v} for k, v in sorted(merged_by_addr.items())]
        perf_json_path.write_text(new_text, encoding='utf-8')
        _save_replacement_manifest(perf_json_path.parent, merged_rows)
    except Exception:
        logger.exception('Failed to apply mapping to %s', perf_json_path)
        return False
    logger.info('Applied symbol recovery mapping to %s', perf_json_path)
    return True


def default_symbol_recovery_output_dir(scene_dir: str, step_dir: str, output_root: Optional[str]) -> Path:
    if output_root:
        return Path(output_root).expanduser().resolve() / Path(scene_dir).name / step_dir
    return Path(scene_dir) / '.symbol_recovery' / step_dir


def maybe_run_symbol_recovery_for_step(
    scene_dir: str,
    step_dir: str,
    perf_db_path: str,
    *,
    effective_so_dir: str,
    top_n: int,
    stat_method: str,
    output_root: Optional[str],
    subprocess_timeout_sec: Optional[float] = None,
    extra_args: Optional[list[str]] = None,
) -> bool:
    sr_root = resolve_symbol_recovery_root()
    if not sr_root:
        logger.info(
            'Symbol recovery skipped: symbol recovery tree not found (set %s to the directory that contains main.py, e.g. your tools/symbol_recovery checkout)',
            ENV_SYMBOL_RECOVERY_ROOT,
        )
        return False
    entry_exe = resolve_symbol_recovery_exe(sr_root)
    py_exe: Optional[str] = None
    if entry_exe is None:
        py_exe = resolve_symbol_recovery_python()
        if not py_exe:
            logger.info(
                'Symbol recovery skipped: no launcher (install venv in %s and ``uv sync`` so '
                'venv/Scripts/symbol-recovery.exe exists, place a packaged exe in that directory, or set %s / %s)',
                sr_root,
                ENV_SYMBOL_RECOVERY_EXE,
                ENV_SYMBOL_RECOVERY_PYTHON,
            )
            return False
    else:
        logger.info('Symbol recovery subprocess entry: %s', entry_exe)

    step_hiperf = Path(perf_db_path).parent
    perf_data = step_hiperf / 'perf.data'
    perf_db = Path(perf_db_path)
    if not perf_db.is_file():
        logger.warning('Symbol recovery skipped: missing perf.db %s', perf_db)
        return False
    if not perf_data.is_file():
        logger.warning('Symbol recovery skipped: missing perf.data %s', perf_data)
        return False

    out_dir = default_symbol_recovery_output_dir(scene_dir, step_dir, output_root)
    argv = build_symbol_recovery_argv(
        sr_root=sr_root,
        entry_exe=entry_exe,
        python_exe=py_exe,
        perf_data=perf_data,
        perf_db=perf_db,
        so_dir=effective_so_dir,
        output_dir=out_dir,
        top_n=top_n,
        stat_method=stat_method,
        extra_args=extra_args,
    )
    rc = run_symbol_recovery_subprocess(argv, cwd=sr_root, timeout_sec=subprocess_timeout_sec)
    if rc != 0:
        return False
    excel = out_dir / symbol_recovery_excel_name(stat_method, top_n)
    perf_json = step_hiperf / 'perf.json'
    return load_mapping_and_apply_perf_json(sr_root, excel, perf_json)


def maybe_generate_symbol_recovery_html_for_step(
    scene_dir: str,
    step_dir: str,
    *,
    top_n: int,
    stat_method: str,
    output_root: Optional[str],
) -> Optional[Path]:
    """在 perf.json 已更新且 hiperf_report.html 已生成后，补跑 Step4 生成增强版 HTML。"""
    sr_root = resolve_symbol_recovery_root()
    if not sr_root:
        return None
    entry_exe = resolve_symbol_recovery_exe(sr_root)
    py_exe: Optional[str] = None
    if entry_exe is None:
        py_exe = resolve_symbol_recovery_python()
        if not py_exe:
            return None

    step_hiperf = Path(scene_dir) / 'hiperf' / step_dir
    html_input = step_hiperf / 'hiperf_report.html'
    if not html_input.is_file():
        logger.info('Symbol recovery Step4 skipped: missing hiperf html %s', html_input)
        return None

    output_dir = default_symbol_recovery_output_dir(scene_dir, step_dir, output_root)
    argv = build_symbol_recovery_html_argv(
        sr_root=sr_root,
        entry_exe=entry_exe,
        python_exe=py_exe,
        html_input=html_input,
        output_dir=output_dir,
        top_n=top_n,
        stat_method=stat_method,
    )
    rc = run_symbol_recovery_subprocess(argv, cwd=sr_root)
    if rc != 0:
        return None
    generated = html_input.parent / symbol_recovery_replaced_html_name(html_input.name)
    if generated.is_file():
        return generated
    logger.info('Symbol recovery Step4 completed but generated html not found: %s', generated)
    return None


def parse_top_n_from_env(cli_top: Optional[int]) -> int:
    if cli_top is not None and cli_top > 0:
        return int(cli_top)
    env_val = os.environ.get(ENV_TOP_N, '').strip()
    if env_val.isdigit() and int(env_val) > 0:
        return int(env_val)
    return DEFAULT_TOP_N


def parse_stat_from_env(cli_stat: Optional[str]) -> str:
    if cli_stat in ('event_count', 'call_count'):
        return cli_stat
    env_val = os.environ.get(ENV_STAT, '').strip().lower()
    if env_val in ('event_count', 'call_count'):
        return env_val
    return DEFAULT_STAT


def parse_output_root_from_env(cli_output: Optional[str]) -> Optional[str]:
    if cli_output:
        return cli_output
    env_val = os.environ.get(ENV_OUTPUT_ROOT, '').strip()
    return env_val or None


def symbol_recovery_should_run(
    *,
    llm_ready: bool,
    effective_so_dir: Optional[str],
    perf_db_path: str,
    no_llm_override: bool,
) -> bool:
    if no_llm_override or not llm_ready:
        return False
    if not effective_so_dir:
        return False
    return bool(perf_db_path and Path(perf_db_path).is_file())
