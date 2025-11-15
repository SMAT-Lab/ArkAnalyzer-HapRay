import argparse
import json
import logging
import math
import os
import random
import re
import shutil
import subprocess
from collections import defaultdict
from pathlib import Path
from typing import Any, Optional

import joblib
import numpy as np
from elftools.elf.elffile import ELFFile
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.feature_selection import f_classif
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import precision_recall_curve, precision_score
from sklearn.model_selection import GridSearchCV, StratifiedKFold
from sklearn.neural_network import MLPClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.svm import LinearSVC


# -------------------- Utils --------------------
def set_global_seed(seed: int = 42):
    random.seed(seed)
    np.random.seed(seed)


def count_by_label(items: list[tuple[str, int]]) -> dict[str, int]:
    pos = sum(1 for _, y in items if y == 1)
    neg = sum(1 for _, y in items if y == 0)
    return {'pos': pos, 'neg': neg, 'total': len(items)}


def run_cmd(cmd: list[str], timeout: int = 10) -> tuple[int, str, str]:
    try:
        cp = subprocess.run(cmd, check=False, capture_output=True, text=True, timeout=timeout)
        return cp.returncode, cp.stdout, cp.stderr
    except Exception as e:
        return 127, '', str(e)


def which_any(cands: list[str]) -> Optional[str]:
    for c in cands:
        p = shutil.which(c)
        if p:
            return p
    return None


# -------------------- 阈值优化 --------------------
def optimize_threshold(y_true: np.ndarray, y_proba: np.ndarray, metric: str = 'precision') -> tuple[float, float]:
    """基于PR曲线优化阈值，默认优化precision"""
    if len(y_proba.shape) > 1:
        y_proba = y_proba[:, 1]
    precisions, recalls, thresholds = precision_recall_curve(y_true, y_proba)
    if metric == 'f1':
        f1_scores = 2 * (precisions * recalls) / (precisions + recalls + 1e-10)
        best_idx = int(np.argmax(f1_scores))
        thr = thresholds[best_idx] if best_idx < len(thresholds) else 0.5
        return float(thr), float(f1_scores[best_idx])
    # precision 优先于 recall
    valid_mask = recalls >= 0.4  # 可按需要下调/上调
    if valid_mask.any():
        prs = precisions[valid_mask]
        # thresholds 的长度 = len(precisions) - 1，这里对齐索引
        ths = thresholds[np.where(valid_mask[:-1])[0]] if len(thresholds) > 0 else np.array([0.5])
        best_idx = int(np.argmax(prs))
        thr = ths[best_idx] if best_idx < len(ths) else 0.5
        return float(thr), float(prs[best_idx])
    return 0.5, float(precisions[0])


# -------------------- key 规范化 & 分组切分 --------------------
_LIB_RE = re.compile(r'(lib[^/]+?\.so)(?:\.\d+)*$')


def normalize_lib_key(name: str) -> str:
    m = _LIB_RE.search(name)
    return m.group(1) if m else name


def _safe_split_counts(n: int, ratios) -> tuple[int, int, int]:
    r = np.array(ratios, dtype=float)
    r = r / r.sum()
    n_tr = int(np.floor(n * r[0]))
    n_va = int(np.floor(n * r[1]))
    n_te = n - n_tr - n_va
    if n >= 3 and n_te == 0:
        if n_va > 1:
            n_va -= 1
            n_te += 1
        elif n_tr > 1:
            n_tr -= 1
            n_te += 1
    if n >= 2 and n_va == 0 and (n_tr > 1):
        n_tr -= 1
        n_va += 1
    if n_tr + n_va + n_te != n:
        diff = n - (n_tr + n_va + n_te)
        n_tr += diff
    return n_tr, n_va, n_te


def stratified_split(items: list[tuple[str, int]], ratios=(0.6, 0.2, 0.2)):
    pos = [it for it in items if it[1] == 1]
    neg = [it for it in items if it[1] == 0]
    random.shuffle(pos)
    random.shuffle(neg)

    def take(lst):
        n = len(lst)
        if n == 0:
            return [], [], []
        if n == 1:
            return lst[:1], [], []
        if n == 2:
            return lst[:1], [], lst[1:2]
        n_tr, n_va, n_te = _safe_split_counts(n, ratios)
        tr = lst[:n_tr]
        va = lst[n_tr : n_tr + n_va]
        te = lst[n_tr + n_va : n_tr + n_va + n_te]
        return tr, va, te

    trp, vap, tep = take(pos)
    trn, van, ten = take(neg)
    tr = trp + trn
    va = vap + van
    te = tep + ten
    random.shuffle(tr)
    random.shuffle(va)
    random.shuffle(te)
    return tr, va, te


def groupwise_split_by_key(items: list[tuple[str, int]], ratios=(0.6, 0.2, 0.2)):
    """按 normalize_lib_key 将同名库的不同变体放入同一 split"""
    groups = defaultdict(list)
    for path, y in items:
        k = normalize_lib_key(Path(path).name)
        groups[k].append((path, y))
    keys = list(groups.keys())
    random.shuffle(keys)
    N = len(items)
    target = np.array(ratios, dtype=float)
    target /= target.sum()
    target_counts = (target * N).astype(int)
    splits = [[], [], []]  # tr, va, te
    counts = np.array([0, 0, 0])
    for k in keys:
        g = groups[k]
        diffs = target_counts - counts
        idx = int(np.argmax(diffs))
        splits[idx].extend(g)
        counts[idx] += len(g)
    tr, va, te = splits
    random.shuffle(tr)
    random.shuffle(va)
    random.shuffle(te)
    return tr, va, te


# -------------------- 字节级（hier管线里用到） --------------------
class CompilerProvenanceExtractor:
    """字节级特征提取（配合 hier 管线的基础版）"""

    def __init__(self, max_bytes: int = 4096):
        self.max_bytes = max_bytes

    def _extract_executable_bytes(self, path: str) -> bytes:
        try:
            with open(path, 'rb') as f:
                data = f.read()
            with open(path, 'rb') as f2:
                elf = ELFFile(f2)
                text_sec = elf.get_section_by_name('.text')
                if text_sec and text_sec['sh_size'] > 0:
                    start = int(text_sec['sh_offset'])
                    size = int(text_sec['sh_size'])
                    return data[start : start + size]
                for seg in elf.iter_segments():
                    if seg['p_type'] == 'PT_LOAD' and (seg['p_flags'] & 0x1):
                        start = int(seg['p_offset'])
                        size = int(seg['p_filesz'])
                        return data[start : start + size]
        except Exception:
            pass
        with open(path, 'rb') as f:
            return f.read(self.max_bytes)

    def _compute_byte_statistics(self, data: bytes) -> dict[str, float]:
        if len(data) == 0:
            return {
                'entropy': 0.0,
                'zero_ratio': 0.0,
                'ascii_ratio': 0.0,
                'byte_diversity': 0.0,
                'avg_byte': 0.0,
                'byte_std': 0.0,
            }
        arr = np.frombuffer(data, dtype=np.uint8)
        counts = np.bincount(arr, minlength=256)
        probs = counts / len(arr)
        probs = probs[probs > 0]
        entropy = -np.sum(probs * np.log2(probs))
        zero_ratio = float(np.mean(arr == 0))
        ascii_ratio = float(np.mean((arr >= 32) & (arr <= 126)))
        byte_diversity = float(len(np.unique(arr)) / 256.0)
        avg_byte = float(np.mean(arr))
        byte_std = float(np.std(arr))
        return {
            'entropy': entropy,
            'zero_ratio': zero_ratio,
            'ascii_ratio': ascii_ratio,
            'byte_diversity': byte_diversity,
            'avg_byte': avg_byte,
            'byte_std': byte_std,
        }

    def extract(self, path: str) -> tuple[np.ndarray, list[str], str]:
        exec_bytes = self._extract_executable_bytes(path)
        if len(exec_bytes) == 0:
            features = np.zeros(512, dtype=np.float32)
            feature_names = [f'feat_{i}' for i in range(512)]
            key = normalize_lib_key(Path(path).name)
            return features, feature_names, key
        if len(exec_bytes) > self.max_bytes:
            exec_bytes = exec_bytes[: self.max_bytes]
        arr = np.frombuffer(exec_bytes, dtype=np.uint8)
        features = []
        feature_names = []
        byte_hist = np.bincount(arr, minlength=256).astype(np.float32)
        byte_hist = byte_hist / max(1.0, len(arr))
        features.extend(byte_hist)
        feature_names.extend([f'byte_freq_{i}' for i in range(256)])
        if len(arr) > 1:
            byte_pairs = arr[:-1].astype(np.uint16) * 256 + arr[1:].astype(np.uint16)
            pair_hist = np.bincount(byte_pairs, minlength=256 * 256)
            top_pairs = np.argsort(pair_hist)[-128:]
            pair_features = pair_hist[top_pairs].astype(np.float32)
            pair_features = pair_features / max(1.0, pair_features.sum())
        else:
            pair_features = np.zeros(128, dtype=np.float32)
        features.extend(pair_features)
        feature_names.extend([f'byte_pair_{i}' for i in range(128)])
        stats = self._compute_byte_statistics(exec_bytes)
        features.extend(
            [
                stats['entropy'],
                stats['zero_ratio'],
                stats['ascii_ratio'],
                stats['byte_diversity'],
                stats['avg_byte'] / 255.0,
                stats['byte_std'] / 255.0,
            ]
        )
        feature_names.extend(
            ['entropy', 'zero_ratio', 'ascii_ratio', 'byte_diversity', 'avg_byte_norm', 'byte_std_norm']
        )
        file_size = len(exec_bytes)
        features.extend([file_size, np.log(file_size + 1), file_size / 1024.0, file_size / (1024.0 * 1024.0)])
        feature_names.extend(['file_size', 'log_file_size', 'file_size_kb', 'file_size_mb'])
        if len(arr) > 0:
            percentiles = np.percentile(arr, [5, 10, 25, 50, 75, 90, 95, 99])
            features.extend(percentiles / 255.0)
            feature_names.extend([f'percentile_{p}' for p in [5, 10, 25, 50, 75, 90, 95, 99]])
            features.append((percentiles[7] - percentiles[0]) / 255.0)
            feature_names.append('percentile_range_99_5')
            features.append((percentiles[6] - percentiles[1]) / 255.0)
            feature_names.append('percentile_range_95_10')
            features.append((percentiles[5] - percentiles[2]) / 255.0)
            feature_names.append('percentile_range_90_25')
        else:
            features.extend([0.0] * 11)
            feature_names.extend(
                [f'percentile_{p}' for p in [5, 10, 25, 50, 75, 90, 95, 99]]
                + ['percentile_range_99_5', 'percentile_range_95_10', 'percentile_range_90_25']
            )
        key = normalize_lib_key(Path(path).name)
        # padding到512
        while len(features) < 512:
            feature_names.append(f'pad_{len(features)}')
            features.append(0.0)
        features = features[:512]
        feature_names = feature_names[:512]
        return np.array(features, dtype=np.float32), feature_names, key


# -------------------- Legacy 提取与训练（仅 legacy 特征组） --------------------
def _safe_float(x) -> float:
    try:
        v = float(x)
        if math.isfinite(v):
            return v
        return 0.0
    except Exception:
        return 0.0


class LegacyFeatureExtractor:
    """仅提取 Legacy 特征组（readelf/objdump/strings 等）"""

    def __init__(self):
        self.BIN_READELF = which_any(['readelf', 'llvm-readelf'])
        self.BIN_OBJDUMP = which_any(['objdump', 'llvm-objdump'])
        self.BIN_STRINGS = which_any(['strings'])

    def _run_legacy(self, cmd: list[str], timeout=10) -> str:
        rc, out, _ = run_cmd(cmd, timeout=timeout)
        return out if rc == 0 else ''

    def _legacy_basic(self, p: str) -> dict[str, Any]:
        try:
            st = os.stat(p)
            with open(p, 'rb') as f:
                hdr = f.read(64)
            return {
                'file_size': float(st.st_size),
                'is_elf': float(1.0 if hdr[:4] == b'\x7fELF' else 0.0),
                'header_hex': float(len(hdr.hex()[:32]) if isinstance(hdr, (bytes, bytearray)) else 0.0),
            }
        except Exception:
            return {'file_size': 0.0, 'is_elf': 0.0, 'header_hex': 0.0}

    def _legacy_elf_header(self, p: str) -> dict[str, Any]:
        out = self._run_legacy([self.BIN_READELF or 'readelf', '-h', p])
        if not out:
            return {
                'elf_type': 0.0,
                'machine_type': 0.0,
                'entry_point': 0.0,
                'section_header_count': 0.0,
                'program_header_count': 0.0,
            }
        d = {}
        m = re.search(r'Type:\s+(\w+)', out)
        d['elf_type'] = float(len(m.group(1))) if m else 0.0
        m = re.search(r'Machine:\s+([^\n]+)', out)
        d['machine_type'] = float(len(m.group(1).strip())) if m else 0.0
        m = re.search(r'Entry point address:\s+(0x[0-9a-fA-F]+)', out)
        d['entry_point'] = 1.0 if m else 0.0
        m = re.search(r'Number of section headers:\s+(\d+)', out)
        d['section_header_count'] = float(int(m.group(1))) if m else 0.0
        m = re.search(r'Number of program headers:\s+(\d+)', out)
        d['program_header_count'] = float(int(m.group(1))) if m else 0.0
        return d

    def _legacy_symbol_table(self, p: str) -> dict[str, Any]:
        out = self._run_legacy([self.BIN_OBJDUMP or 'objdump', '-t', p])
        if not out:
            return {
                k: 0.0
                for k in [
                    'total_symbols',
                    'function_symbols',
                    'data_symbols',
                    'local_symbols',
                    'global_symbols',
                    'weak_symbols',
                    'artificial_symbols',
                    'lto_symbols',
                    'undefined_symbols',
                    'common_symbols',
                    'absolute_symbols',
                    'debug_symbols',
                    'function_ratio',
                    'data_ratio',
                    'local_ratio',
                    'global_ratio',
                    'artificial_ratio',
                    'lto_ratio',
                ]
            }
        f = {
            k: 0
            for k in [
                'total_symbols',
                'function_symbols',
                'data_symbols',
                'local_symbols',
                'global_symbols',
                'weak_symbols',
                'artificial_symbols',
                'lto_symbols',
                'undefined_symbols',
                'common_symbols',
                'absolute_symbols',
                'debug_symbols',
            ]
        }
        for line in out.splitlines():
            if not line or 'SYMBOL TABLE' in line:
                continue
            parts = line.split()
            if len(parts) < 6:
                continue
            f['total_symbols'] += 1
            st = parts[4] if len(parts) > 4 else ''
            sb = parts[5] if len(parts) > 5 else ''
            sn = parts[-1] if parts else ''
            if 'F' in st:
                f['function_symbols'] += 1
            if any(c in st for c in ('O', 'D', 'B')):
                f['data_symbols'] += 1
            if 'l' in sb:
                f['local_symbols'] += 1
            elif 'g' in sb:
                f['global_symbols'] += 1
            elif 'w' in sb:
                f['weak_symbols'] += 1
            if 'a' in st:
                f['absolute_symbols'] += 1
            elif 'C' in st:
                f['common_symbols'] += 1
            elif 'U' in st:
                f['undefined_symbols'] += 1
            elif 'N' in st:
                f['debug_symbols'] += 1
            if '<artificial>' in sn:
                f['artificial_symbols'] += 1
            if ('LTO' in sn) or ('lto' in sn):
                f['lto_symbols'] += 1
        t = f['total_symbols'] or 1
        for k in list(f.keys()):  # noqa: PLC0206
            f[k] = float(f[k])
        f.update(
            {
                'function_ratio': float(f['function_symbols'] / t),
                'data_ratio': float(f['data_symbols'] / t),
                'local_ratio': float(f['local_symbols'] / t),
                'global_ratio': float(f['global_symbols'] / t),
                'artificial_ratio': float(f['artificial_symbols'] / t),
                'lto_ratio': float(f['lto_symbols'] / t),
            }
        )
        return f

    def _legacy_sections(self, p: str) -> dict[str, Any]:
        out = self._run_legacy([self.BIN_OBJDUMP or 'objdump', '-h', p])
        if not out:
            return {
                'total_sections': 0.0,
                'text_sections': 0.0,
                'data_sections': 0.0,
                'bss_sections': 0.0,
                'debug_sections': 0.0,
                'total_text_size': 0.0,
                'total_data_size': 0.0,
                'total_bss_size': 0.0,
                'total_debug_size': 0.0,
                'text_size_ratio': 0.0,
                'data_size_ratio': 0.0,
                'bss_size_ratio': 0.0,
            }
        f = {
            'total_sections': 0,
            'text_sections': 0,
            'data_sections': 0,
            'bss_sections': 0,
            'debug_sections': 0,
            'total_text_size': 0,
            'total_data_size': 0,
            'total_bss_size': 0,
            'total_debug_size': 0,
        }
        for line in out.splitlines():
            if not line or 'Sections:' in line or 'Idx' in line:
                continue
            parts = line.split()
            if len(parts) < 4:
                continue
            name = parts[1]
            try:
                size = int(parts[2], 16) if parts[2] != '00000000' else 0
            except Exception:
                size = 0
            f['total_sections'] += 1
            if '.text' in name:
                f['text_sections'] += 1
                f['total_text_size'] += size
            elif ('.data' in name) or ('.rodata' in name):
                f['data_sections'] += 1
                f['total_data_size'] += size
            elif '.bss' in name:
                f['bss_sections'] += 1
                f['total_bss_size'] += size
            elif '.debug' in name or '.comment' in name:
                f['debug_sections'] += 1
                f['total_debug_size'] += size
        total = f['total_text_size'] + f['total_data_size'] + f['total_bss_size'] or 1
        for k in list(f.keys()):  # noqa: PLC0206
            f[k] = float(f[k])
        f.update(
            {
                'text_size_ratio': float(f['total_text_size'] / total),
                'data_size_ratio': float(f['total_data_size'] / total),
                'bss_size_ratio': float(f['total_bss_size'] / total),
            }
        )
        return f

    def _legacy_relocs(self, p: str) -> dict[str, Any]:
        out = self._run_legacy([self.BIN_OBJDUMP or 'objdump', '-R', p])
        if not out:
            return {
                'total_relocations': 0.0,
                'text_relocations': 0.0,
                'data_relocations': 0.0,
                'plt_relocations': 0.0,
                'got_relocations': 0.0,
                'dynamic_relocations': 0.0,
                'plt_ratio': 0.0,
                'got_ratio': 0.0,
                'dynamic_ratio': 0.0,
            }
        f = {
            'total_relocations': 0,
            'text_relocations': 0,
            'data_relocations': 0,
            'plt_relocations': 0,
            'got_relocations': 0,
            'dynamic_relocations': 0,
        }
        for line in out.splitlines():
            if not line or 'RELOCATION' in line:
                continue
            f['total_relocations'] += 1
            if 'PLT' in line:
                f['plt_relocations'] += 1
            elif 'GOT' in line:
                f['got_relocations'] += 1
            elif 'DYNAMIC' in line:
                f['dynamic_relocations'] += 1
            elif '.text' in line:
                f['text_relocations'] += 1
            elif '.data' in line or '.rodata' in line:
                f['data_relocations'] += 1
        t = f['total_relocations'] or 1
        for k in list(f.keys()):  # noqa: PLC0206
            f[k] = float(f[k])
        f.update(
            {
                'plt_ratio': float(f['plt_relocations'] / t),
                'got_ratio': float(f['got_relocations'] / t),
                'dynamic_ratio': float(f['dynamic_relocations'] / t),
            }
        )
        return f

    def _legacy_dynamic(self, p: str) -> dict[str, Any]:
        out = self._run_legacy([self.BIN_READELF or 'readelf', '-d', p])
        if not out:
            return {
                'total_dynamic_entries': 0.0,
                'needed_libraries': 0.0,
                'rpath_entries': 0.0,
                'runpath_entries': 0.0,
                'symbol_versions': 0.0,
                'init_functions': 0.0,
                'fini_functions': 0.0,
            }
        f = {
            'total_dynamic_entries': 0,
            'needed_libraries': 0,
            'rpath_entries': 0,
            'runpath_entries': 0,
            'symbol_versions': 0,
            'init_functions': 0,
            'fini_functions': 0,
        }
        for line in out.splitlines():
            if not line or 'DYNAMIC' in line:
                continue
            f['total_dynamic_entries'] += 1
            u = line.upper()
            if 'NEEDED' in u:
                f['needed_libraries'] += 1
            elif 'RPATH' in u:
                f['rpath_entries'] += 1
            elif 'RUNPATH' in u:
                f['runpath_entries'] += 1
            elif 'VERSYM' in u or 'VERNEED' in u:
                f['symbol_versions'] += 1
            elif 'INIT' in u:
                f['init_functions'] += 1
            elif 'FINI' in u:
                f['fini_functions'] += 1
        for k in list(f.keys()):  # noqa: PLC0206
            f[k] = float(f[k])
        return f

    def _legacy_strings(self, p: str) -> dict[str, Any]:
        out = self._run_legacy([self.BIN_STRINGS or 'strings', p])
        if not out:
            return {
                'total_strings': 0.0,
                'lto_strings': 0.0,
                'compiler_strings': 0.0,
                'optimization_strings': 0.0,
                'linker_strings': 0.0,
                'gcc_strings': 0.0,
                'gnu_strings': 0.0,
                'lto_string_ratio': 0.0,
                'compiler_string_ratio': 0.0,
                'optimization_string_ratio': 0.0,
            }
        arr = out.splitlines()
        f = {
            'total_strings': len(arr),
            'lto_strings': 0,
            'compiler_strings': 0,
            'optimization_strings': 0,
            'linker_strings': 0,
            'gcc_strings': 0,
            'gnu_strings': 0,
        }
        for s in arr:
            sl = s.lower()
            if ('lto' in sl) or ('link-time' in sl):
                f['lto_strings'] += 1
            if ('gcc' in sl) or ('clang' in sl):
                f['compiler_strings'] += 1
            if ('optimization' in sl) or ('optimize' in sl):
                f['optimization_strings'] += 1
            if ('linker' in sl) or (sl == 'ld'):
                f['linker_strings'] += 1
            if 'gcc:' in sl:
                f['gcc_strings'] += 1
            if 'gnu' in sl:
                f['gnu_strings'] += 1
        t = f['total_strings'] or 1
        for k in list(f.keys()):  # noqa: PLC0206
            f[k] = float(f[k])
        f.update(
            {
                'lto_string_ratio': float(f['lto_strings'] / t),
                'compiler_string_ratio': float(f['compiler_strings'] / t),
                'optimization_string_ratio': float(f['optimization_strings'] / t),
            }
        )
        return f

    def _legacy_bytes(self, p: str) -> dict[str, Any]:
        try:
            with open(p, 'rb') as f:
                b = f.read()
        except Exception:
            return {
                'file_size': 0.0,
                'zero_byte_ratio': 0.0,
                'ascii_ratio': 0.0,
                'entropy': 0.0,
                'elf_header_present': 0.0,
                'lto_patterns': 0.0,
            }
        if not b:
            return {
                'file_size': 0.0,
                'zero_byte_ratio': 0.0,
                'ascii_ratio': 0.0,
                'entropy': 0.0,
                'elf_header_present': 0.0,
                'lto_patterns': 0.0,
            }
        arr = np.frombuffer(b, dtype=np.uint8)
        counts = np.bincount(arr, minlength=256).astype(np.float64)
        total = counts.sum()
        ent = 0.0
        if total > 0:
            p0 = counts / total
            p0 = p0[p0 > 0]
            ent = float(-(p0 * np.log2(p0)).sum())
        pats = [b'LTO', b'lto', b'link-time', b'whole-program', b'visibility', b'fat-lto', b'linker-plugin']
        return {
            'file_size': float(len(b)),
            'zero_byte_ratio': float((arr == 0).mean()),
            'ascii_ratio': float(((arr >= 32) & (arr <= 126)).mean()),
            'entropy': ent,
            'elf_header_present': float(1.0 if b.startswith(b'\x7fELF') else 0.0),
            'lto_patterns': float(sum(b.count(pt) for pt in pats)),
        }

    def _legacy_compiler(self, p: str) -> dict[str, Any]:
        out = self._run_legacy([self.BIN_READELF or 'readelf', '-S', p])
        if not out:
            return {
                'has_comment_section': 0.0,
                'has_note_section': 0.0,
                'has_debug_sections': 0.0,
                'compiler_info': 0.0,
                'build_id_present': 0.0,
            }
        f = {
            'has_comment_section': 0.0,
            'has_note_section': 0.0,
            'has_debug_sections': 0.0,
            'compiler_info': 0.0,
            'build_id_present': 0.0,
        }
        if '.comment' in out:
            f['has_comment_section'] = 1.0
        if '.note' in out:
            f['has_note_section'] = 1.0
        if '.debug' in out:
            f['has_debug_sections'] = 1.0
        if 'GNU_BUILD_ID' in out:
            f['build_id_present'] = 1.0
        return f

    def _legacy_optim(self, p: str) -> dict[str, Any]:
        out = self._run_legacy([self.BIN_OBJDUMP or 'objdump', '-d', p], timeout=15)
        if not out:
            return {
                'optimization_level': 0.0,
                'has_inline_functions': 0.0,
                'has_unrolled_loops': 0.0,
                'has_vectorized_code': 0.0,
                'has_tail_calls': 0.0,
            }
        f = {
            'optimization_level': 0.0,
            'has_inline_functions': 0.0,
            'has_unrolled_loops': 0.0,
            'has_vectorized_code': 0.0,
            'has_tail_calls': 0.0,
        }
        if 'callq' in out and 'nop' in out:
            f['has_inline_functions'] = 1.0
        if 'rep ' in out and 'mov' in out:
            f['has_unrolled_loops'] = 1.0
        if ('xmm' in out) or ('ymm' in out):
            f['has_vectorized_code'] = 1.0
        if 'jmp' in out and 'ret' in out:
            f['has_tail_calls'] = 1.0
        return f

    def extract(self, path: str) -> tuple[np.ndarray, list[str], str]:
        feats = {}
        try:
            feats.update(self._legacy_basic(path))
            feats.update(self._legacy_elf_header(path))
            feats.update(self._legacy_symbol_table(path))
            feats.update(self._legacy_sections(path))
            feats.update(self._legacy_relocs(path))
            feats.update(self._legacy_dynamic(path))
            feats.update(self._legacy_strings(path))
            feats.update(self._legacy_bytes(path))
            feats.update(self._legacy_compiler(path))
            feats.update(self._legacy_optim(path))
        except Exception as e:
            logging.warning(f'特征提取失败 {path}: {e}')
        feature_names = sorted(feats.keys())
        features = [_safe_float(feats.get(k, 0.0)) for k in feature_names]
        key = normalize_lib_key(Path(path).name)
        return np.array(features, dtype=np.float32), feature_names, key


# -------------------- O3-focused Feature Extractor (增强版) --------------------
class O3FocusedFeatureExtractor(LegacyFeatureExtractor):
    """
    O3 定向特征工程（AArch64 增强）：
    核心改动（更利于线性/逻辑/MLP）：
      - 段尺寸：.text/.rodata/.data/.bss/.plt/.plt.sec/.got/.got.plt/.eh_frame/.gcc_except_table 等
      - 比例：相对 text / 相对 (text+rodata+data+bss) / 每KB密度
      - 对数：log1p(尺寸/计数) 以减少长尾
      - 重定位类型分布 + 熵
      - 指令代理：BL/BLR/BR/B/RET/CBZ/CBNZ/TBZ/TBNZ/ADRP/LDR/ADD/向量指令
      - 条件分支率、间接调用率、call/ret 比、GOT 三元代理（以 min(ADRP,ADD,LDR) 近似）
      - 符号可见性与导出密度：GLOBAL/LOCAL/WEAK、HIDDEN/DEFAULT 比、每KB导出函数数
      - 版本段与COMDAT：.gnu.version{,_d,_r} 存在、.group 计数
    """

    def __init__(self):
        super().__init__()
        self.BIN_OBJDUMP = which_any(['aarch64-linux-gnu-objdump', 'llvm-objdump', 'objdump']) or 'objdump'
        self.BIN_READELF = which_any(['readelf', 'llvm-readelf']) or 'readelf'

    def _sec_sizes_map(self, p: str) -> dict[str, int]:
        out = self._run_legacy([self.BIN_READELF, '-S', p], timeout=20)
        names = [
            '.text',
            '.rodata',
            '.data',
            '.bss',
            '.plt',
            '.plt.sec',
            '.got',
            '.got.plt',
            '.eh_frame',
            '.gcc_except_table',
            '.init_array',
            '.fini_array',
            '.text.hot',
            '.text.unlikely',
            '.group',
            '.gnu.version',
            '.gnu.version_d',
            '.gnu.version_r',
        ]
        sizes = {n: 0 for n in names}
        if not out:
            return sizes
        for line in out.splitlines():
            # 解析：] <name> ... <size_hex>
            m = re.search(r'\]\s+(\S+)\s+\S+\s+[0-9a-fA-Fx]+\s+[0-9a-fA-F]+\s+([0-9a-fA-F]+)', line)
            if not m:
                continue
            name, size_hex = m.group(1), m.group(2)
            try:
                size = int(size_hex, 16)
            except Exception:
                size = 0
            if name in sizes:
                sizes[name] = size
        return sizes

    def _dyn_relocs(self, p: str) -> dict[str, int]:
        out = self._run_legacy([self.BIN_READELF, '-r', p], timeout=20)
        rel = {'TOTAL': 0, 'JUMP_SLOT': 0, 'GLOB_DAT': 0, 'RELATIVE': 0, 'IRELATIVE': 0}
        if not out:
            return rel
        for line in out.splitlines():
            if 'R_AARCH64_' in line or 'JUMP_SLOT' in line:
                rel['TOTAL'] += 1
                if 'JUMP_SLOT' in line:
                    rel['JUMP_SLOT'] += 1
                elif 'GLOB_DAT' in line:
                    rel['GLOB_DAT'] += 1
                elif 'IRELATIVE' in line:
                    rel['IRELATIVE'] += 1
                elif 'RELATIVE' in line:
                    rel['RELATIVE'] += 1
        return rel

    def _sym_table(self, p: str) -> dict[str, int]:
        out = self._run_legacy([self.BIN_READELF, '-sW', p], timeout=20)
        d = {
            'SYM_TOTAL': 0,
            'FUNC_TOTAL': 0,
            'FUNC_LOCAL': 0,
            'FUNC_GLOBAL': 0,
            'FUNC_WEAK': 0,
            'VIS_DEFAULT': 0,
            'VIS_HIDDEN': 0,
        }
        if not out:
            return d
        for line in out.splitlines():
            if not line or ('FUNC' not in line and 'OBJECT' not in line):
                continue
            d['SYM_TOTAL'] += 1
            if 'FUNC' in line:
                d['FUNC_TOTAL'] += 1
                if ' GLOBAL ' in line:
                    d['FUNC_GLOBAL'] += 1
                elif ' LOCAL ' in line:
                    d['FUNC_LOCAL'] += 1
                if ' WEAK ' in line:
                    d['FUNC_WEAK'] += 1
                if ' DEFAULT ' in line:
                    d['VIS_DEFAULT'] += 1
                if ' HIDDEN ' in line:
                    d['VIS_HIDDEN'] += 1
        return d

    def _disasm_stats_aarch64(self, p: str) -> dict[str, int]:
        out = self._run_legacy([self.BIN_OBJDUMP, '-d', p], timeout=40)
        c = {
            'INSN_TOTAL': 0,
            'BL': 0,
            'BLR': 0,
            'BR': 0,
            'B': 0,
            'BCOND': 0,
            'RET': 0,
            'CBZ': 0,
            'CBNZ': 0,
            'TBZ': 0,
            'TBNZ': 0,
            'ADRP': 0,
            'LDR': 0,
            'ADD': 0,
            'VEC': 0,
        }
        if not out:
            return c
        for line in out.splitlines():
            if ':' not in line:
                continue
            low = line.lower()
            c['INSN_TOTAL'] += 1
            # 匹配注意单词边界
            if re.search(r'\bbl\b', low):
                c['BL'] += 1
            if re.search(r'\bblr\b', low):
                c['BLR'] += 1
            if re.search(r'\bbr\b', low):
                c['BR'] += 1
            if re.search(r'\bb\b(?!\w)', low):
                c['B'] += 1
            if re.search(r'\bb\.[a-z]{2,3}\b', low):
                c['BCOND'] += 1
            if re.search(r'\bret\b', low):
                c['RET'] += 1
            if re.search(r'\bcbz\b', low):
                c['CBZ'] += 1
            if re.search(r'\bcbnz\b', low):
                c['CBNZ'] += 1
            if re.search(r'\btbz\b', low):
                c['TBZ'] += 1
            if re.search(r'\btbnz\b', low):
                c['TBNZ'] += 1
            if re.search(r'\badrp\b', low):
                c['ADRP'] += 1
            if re.search(r'\bldr\b', low):
                c['LDR'] += 1
            if re.search(r'\badd\b', low):
                c['ADD'] += 1
            if re.search(r'\b(ld1|st1|fmla|fadd|fmul|zip1|uzp1|trn1|dup|ins|eor\s+v)\b', low):
                c['VEC'] += 1
        return c

    @staticmethod
    def _entropy_from_counts(d: dict[str, int], keys: list[str]) -> float:
        vals = np.array([max(0, int(d.get(k, 0))) for k in keys], dtype=np.float64)
        s = vals.sum()
        if s <= 0:
            return 0.0
        p = vals / s
        p = p[p > 0]
        return float(-(p * np.log2(p)).sum())

    def extract(self, path: str) -> tuple[np.ndarray, list[str], str]:
        ss = self._sec_sizes_map(path)
        rel = self._dyn_relocs(path)
        sy = self._sym_table(path)
        di = self._disasm_stats_aarch64(path)

        # 汇总尺寸
        text = max(1, ss['.text'])
        ro = ss['.rodata']
        data = ss['.data']
        bss = ss['.bss']
        total_core = max(1, text + ro + data + bss)
        text_kb = text / 1024.0

        # 版本/COMDAT/组段存在性
        has_ver = 1.0 if (ss['.gnu.version'] > 0 or ss['.gnu.version_d'] > 0 or ss['.gnu.version_r'] > 0) else 0.0
        has_group = 1.0 if ss['.group'] > 0 else 0.0

        # 三元 GOT 近似代理
        got_triplet = float(min(di['ADRP'], di['ADD'], di['LDR']))

        # 密度/比例/对数
        def rdiv(a, b):
            a = float(a)
            b = float(b)
            return a / (b if b > 0 else 1.0)

        def log(x):
            return float(np.log1p(max(0.0, float(x))))

        reloc_keys = ['JUMP_SLOT', 'GLOB_DAT', 'RELATIVE', 'IRELATIVE']
        reloc_entropy = self._entropy_from_counts(rel, reloc_keys)

        # 组合比率
        calls = di['BL'] + di['BLR']
        cond_br = di['BCOND'] + di['CBZ'] + di['CBNZ'] + di['TBZ'] + di['TBNZ']
        r_call_ret = rdiv(calls, di['RET'])
        r_blr_total = rdiv(di['BLR'], max(1, calls))
        r_cond_uncond = rdiv(cond_br, (di['B'] + di['BR']))
        r_bl_ret = rdiv(di['BL'], di['RET'])
        r_vec_total = rdiv(di['VEC'], max(1, di['INSN_TOTAL']))
        r_hidden_vis = rdiv(sy['VIS_HIDDEN'], (sy['VIS_DEFAULT'] + sy['VIS_HIDDEN']))
        r_gotplt_text = rdiv(ss['.got.plt'], text)
        r_plt_text = rdiv(ss['.plt'], text)
        r_pltsec_text = rdiv(ss['.plt.sec'], text)
        r_data_total = rdiv(data, total_core)
        r_ro_total = rdiv(ro, total_core)
        r_bss_total = rdiv(bss, total_core)
        r_text_total = rdiv(text, total_core)
        r_export_kb = rdiv(sy['FUNC_GLOBAL'], text_kb)  # 每KB导出函数数
        r_funcs_total = rdiv(sy['FUNC_TOTAL'], max(1, sy['SYM_TOTAL']))

        plt_entries = 0
        out_d = self._run_legacy([self.BIN_OBJDUMP, '-d', path], timeout=40)
        if out_d:
            in_plt = False
            for line in out_d.splitlines():
                if '<.plt>' in line or '<.plt.sec>' in line:
                    in_plt = True
                    continue
                if in_plt and line.strip().endswith('>:'):  # 下一段开头，退出
                    in_plt = False
                if in_plt and ':' in line:
                    plt_entries += 1

        features: dict[str, float] = {
            # 1) 段尺寸 & 比例 & 对数
            'sz_text': float(text),
            'sz_rodata': float(ro),
            'sz_data': float(data),
            'sz_bss': float(bss),
            'sz_plt': float(ss['.plt']),
            'sz_plt_sec': float(ss['.plt.sec']),
            'sz_got': float(ss['.got']),
            'sz_gotplt': float(ss['.got.plt']),
            'sz_eh_frame': float(ss['.eh_frame']),
            'sz_gcc_except': float(ss['.gcc_except_table']),
            'sz_text_hot': float(ss['.text.hot']),
            'sz_text_unlikely': float(ss['.text.unlikely']),
            'r_text_total': r_text_total,
            'r_ro_total': r_ro_total,
            'r_data_total': r_data_total,
            'r_bss_total': r_bss_total,
            'r_gotplt_text': r_gotplt_text,
            'r_plt_text': r_plt_text,
            'r_pltsec_text': r_pltsec_text,
            'log_sz_text': log(text),
            'log_sz_plt': log(ss['.plt']),
            'log_sz_gotplt': log(ss['.got.plt']),
            'log_sz_eh_frame': log(ss['.eh_frame']),
            'log_sz_except': log(ss['.gcc_except_table']),
            # 2) 重定位分布 & 熵
            'rel_total': float(rel['TOTAL']),
            'rel_js_ratio': rdiv(rel['JUMP_SLOT'], rel['TOTAL']),
            'rel_gd_ratio': rdiv(rel['GLOB_DAT'], rel['TOTAL']),
            'rel_rel_ratio': rdiv(rel['RELATIVE'], rel['TOTAL']),
            'rel_irel_ratio': rdiv(rel['IRELATIVE'], rel['TOTAL']),
            'rel_entropy': reloc_entropy,
            'log_rel_total': log(rel['TOTAL']),
            # 3) 符号/可见性/导出
            'func_total': float(sy['FUNC_TOTAL']),
            'func_global': float(sy['FUNC_GLOBAL']),
            'func_local': float(sy['FUNC_LOCAL']),
            'func_weak': float(sy['FUNC_WEAK']),
            'r_func_global_total': rdiv(sy['FUNC_GLOBAL'], max(1, sy['FUNC_TOTAL'])),
            'r_func_local_total': rdiv(sy['FUNC_LOCAL'], max(1, sy['FUNC_TOTAL'])),
            'r_hidden_default': r_hidden_vis,
            'r_funcs_total': r_funcs_total,
            'export_per_kb': r_export_kb,
            'log_func_total': log(sy['FUNC_TOTAL']),
            'log_func_global': log(sy['FUNC_GLOBAL']),
            # 4) 指令密度/比例/三元代理
            'd_bl_per_kb': rdiv(di['BL'], text_kb),
            'd_blr_per_kb': rdiv(di['BLR'], text_kb),
            'd_br_per_kb': rdiv(di['BR'], text_kb),
            'd_b_per_kb': rdiv(di['B'], text_kb),
            'd_bcond_per_kb': rdiv(di['BCOND'], text_kb),
            'd_ret_per_kb': rdiv(di['RET'], text_kb),
            'd_cbz_per_kb': rdiv(di['CBZ'], text_kb),
            'd_cbnz_per_kb': rdiv(di['CBNZ'], text_kb),
            'd_tbz_per_kb': rdiv(di['TBZ'], text_kb),
            'd_tbnz_per_kb': rdiv(di['TBNZ'], text_kb),
            'd_adrp_per_kb': rdiv(di['ADRP'], text_kb),
            'd_ldr_per_kb': rdiv(di['LDR'], text_kb),
            'd_add_per_kb': rdiv(di['ADD'], text_kb),
            'd_vec_per_kb': rdiv(di['VEC'], text_kb),
            'r_call_ret': r_call_ret,
            'r_blr_total': r_blr_total,  # 间接调用率（寄存器调用）
            'r_cond_uncond': r_cond_uncond,
            'r_bl_ret': r_bl_ret,
            'r_vec_total': r_vec_total,
            'got_triplet_per_kb': rdiv(got_triplet, text_kb),
            # 5) PLT/GOT 使用代理
            'plt_entries': float(plt_entries),
            'd_plt_entries_per_kb': rdiv(plt_entries, text_kb),
            'r_plt_calls': rdiv(plt_entries, max(1, calls)),
            # 6) 版本/COMDAT存在性
            'has_symver': has_ver,
            'has_comdat_group': has_group,
        }

        # 生成特征向量
        feature_names = list(features.keys())
        feature_values = [float(features[k]) for k in feature_names]
        key = normalize_lib_key(Path(path).name)
        return np.array(feature_values, dtype=np.float32), feature_names, key


# -------------------- Dataset Wrappers --------------------
class LegacyFeatureDataset:
    def __init__(self, items: list[tuple[str, int]], extractor):
        self.items = list(items)
        self.extractor = extractor
        self.features = []
        self.labels = []
        self.paths = []
        self.keys = []
        self.feature_names = None
        for path, label in self.items:
            try:
                feat, names, key = self.extractor.extract(path)
                self.features.append(feat)
                self.labels.append(int(label))
                self.paths.append(path)
                self.keys.append(key)
                if self.feature_names is None:
                    self.feature_names = names
            except Exception as e:
                logging.warning(f'Failed to extract features from {path}: {e}')
                if self.feature_names is None:
                    self.feature_names = []
                feat = np.zeros(len(self.feature_names), dtype=np.float32)
                self.features.append(feat)
                self.labels.append(int(label))
                self.paths.append(path)
                self.keys.append(normalize_lib_key(Path(path).name))
        if len(self.features) == 0:
            self.feature_names = []
            self.X = np.zeros((0, 0), dtype=np.float32)
            self.y = np.zeros((0,), dtype=np.int64)
        else:
            max_len = max(len(f) for f in self.features)
            if self.feature_names is None:
                self.feature_names = [f'feat_{i}' for i in range(max_len)]
            padded_features = []
            for f in self.features:
                if len(f) < max_len:
                    padded = np.pad(f, (0, max_len - len(f)), mode='constant')
                elif len(f) > max_len:
                    padded = f[:max_len]
                else:
                    padded = f
                padded_features.append(padded)
            self.X = np.stack(padded_features, axis=0).astype(np.float32)
            self.y = np.array(self.labels, dtype=np.int64)
        if self.feature_names is None:
            self.feature_names = [f'f{i}' for i in range(self.X.shape[1] if self.X.shape[0] > 0 else 0)]

    def __len__(self):
        return len(self.y)

    def __getitem__(self, idx):
        return self.X[idx], self.y[idx], self.paths[idx], self.keys[idx]


class CompilerProvenanceDataset:
    """用于 hier 管线的字节级特征数据集"""

    def __init__(self, items: list[tuple[str, int]], extractor: CompilerProvenanceExtractor):
        self.items = list(items)
        self.extractor = extractor
        self.features = []
        self.labels = []
        self.paths = []
        self.keys = []
        self.feature_names = None
        for path, label in self.items:
            try:
                feat, names, key = self.extractor.extract(path)
                self.features.append(feat)
                self.labels.append(int(label))
                self.paths.append(path)
                self.keys.append(key)
                if self.feature_names is None:
                    self.feature_names = names
            except Exception as e:
                logging.warning(f'Failed to extract features from {path}: {e}')
                feat = np.zeros(512, dtype=np.float32)
                self.features.append(feat)
                self.labels.append(int(label))
                self.paths.append(path)
                self.keys.append(normalize_lib_key(Path(path).name))
        if len(self.features) == 0:
            self.feature_names = [f'f{i}' for i in range(512)]
            self.X = np.zeros((0, len(self.feature_names)), dtype=np.float32)
            self.y = np.zeros((0,), dtype=np.int64)
        else:
            self.X = np.stack(self.features, axis=0).astype(np.float32)
            self.y = np.array(self.labels, dtype=np.int64)
        if self.feature_names is None:
            self.feature_names = [f'f{i}' for i in range(self.X.shape[1])]


# -------------------- 分类器封装 --------------------
class CompilerProvenanceSVM:
    def __init__(
        self,
        C: float = 0.1,  # noqa: N803
        class_weight: Optional[str] = 'balanced',
        random_state: int = 42,  # noqa: N803
        use_calibration: bool = True,
    ):
        self.C = C
        self.class_weight = class_weight
        self.random_state = random_state
        self.use_calibration = use_calibration
        self.scaler = StandardScaler()
        self.svm = LinearSVC(
            C=C, class_weight=class_weight, random_state=random_state, max_iter=50000, dual=False, tol=1e-4
        )
        self.calibrator = None
        self.is_fitted = False

    def fit(self, X: np.ndarray, y: np.ndarray, X_val: np.ndarray = None, y_val: np.ndarray = None):  # noqa: N803
        Xs = self.scaler.fit_transform(X)
        self.svm.fit(Xs, y)
        if self.use_calibration:
            if X_val is not None and y_val is not None:
                Xvs = self.scaler.transform(X_val)
                decision_val = self.svm.decision_function(Xvs).reshape(-1, 1)
                self.calibrator = LogisticRegression(solver='lbfgs', max_iter=1000)
                self.calibrator.fit(decision_val, y_val)
            else:
                decision_train = self.svm.decision_function(Xs).reshape(-1, 1)
                self.calibrator = LogisticRegression(solver='lbfgs', max_iter=1000)
                self.calibrator.fit(decision_train, y)
        self.is_fitted = True

    def predict(self, X: np.ndarray) -> np.ndarray:  # noqa: N803
        if not self.is_fitted:
            raise ValueError('fit first')
        Xs = self.scaler.transform(X)
        return self.svm.predict(Xs)

    def predict_proba(self, X: np.ndarray) -> np.ndarray:  # noqa: N803
        if not self.is_fitted:
            raise ValueError('fit first')
        Xs = self.scaler.transform(X)
        if self.calibrator is not None:
            decision_scores = self.svm.decision_function(Xs).reshape(-1, 1)
            proba = self.calibrator.predict_proba(decision_scores)
        else:
            decision_scores = self.svm.decision_function(Xs)
            proba = 1 / (1 + np.exp(-decision_scores))
            proba = np.column_stack([1 - proba, proba])
        return proba

    def get_feature_importance(self) -> np.ndarray:
        if not self.is_fitted:
            raise ValueError('fit first')
        return np.abs(self.svm.coef_[0])


class CompilerProvenanceRF:
    def __init__(self, n_estimators: int = 400, max_depth: Optional[int] = None, random_state: int = 42):
        self.rf = RandomForestClassifier(
            n_estimators=n_estimators,
            max_depth=max_depth,
            min_samples_split=2,
            min_samples_leaf=1,
            n_jobs=-1,
            random_state=random_state,
        )
        self.is_fitted = False

    def fit(self, X, y):  # noqa: N803
        self.rf.fit(X, y)
        self.is_fitted = True

    def predict(self, X):  # noqa: N803
        if not self.is_fitted:
            raise ValueError('fit first')
        return self.rf.predict(X)

    def predict_proba(self, X):  # noqa: N803
        if not self.is_fitted:
            raise ValueError('fit first')
        return (
            self.rf.predict_proba(X)
            if hasattr(self.rf, 'predict_proba')
            else np.column_stack([1 - self.rf.predict(X), self.rf.predict(X)])
        )

    def get_feature_importance(self) -> np.ndarray:
        return getattr(
            self.rf,
            'feature_importances_',
            np.zeros(self.rf.n_features_in_ if hasattr(self.rf, 'n_features_in_') else 0),
        )


class CompilerProvenanceGBDT:
    def __init__(
        self,
        n_estimators: int = 400,
        learning_rate: float = 0.05,
        max_depth: int = 3,
        subsample: float = 0.9,
        random_state: int = 42,
    ):
        self.gbdt = GradientBoostingClassifier(
            n_estimators=n_estimators,
            learning_rate=learning_rate,
            max_depth=max_depth,
            subsample=subsample,
            random_state=random_state,
        )
        self.is_fitted = False

    def fit(self, X, y):  # noqa: N803
        self.gbdt.fit(X, y)
        self.is_fitted = True

    def predict(self, X):  # noqa: N803
        if not self.is_fitted:
            raise ValueError('fit first')
        return self.gbdt.predict(X)

    def predict_proba(self, X):  # noqa: N803
        if not self.is_fitted:
            raise ValueError('fit first')
        if hasattr(self.gbdt, 'predict_proba'):
            return self.gbdt.predict_proba(X)
        scores = self.gbdt.decision_function(X)
        proba = 1 / (1 + np.exp(-scores))
        return np.column_stack([1 - proba, proba])

    def get_feature_importance(self) -> np.ndarray:
        return getattr(
            self.gbdt,
            'feature_importances_',
            np.zeros(self.gbdt.n_features_in_ if hasattr(self.gbdt, 'n_features_in_') else 0),
        )


class CompilerProvenanceLR:
    def __init__(self, C: float = 1.0, penalty: str = 'l2', class_weight: Optional[str] = None, random_state: int = 42):  # noqa: N803
        self.scaler = StandardScaler()
        self.lr = LogisticRegression(
            C=C, penalty=penalty, solver='lbfgs', max_iter=2000, class_weight=class_weight, random_state=random_state
        )
        self.is_fitted = False

    def fit(self, X, y):  # noqa: N803
        Xs = self.scaler.fit_transform(X)
        self.lr.fit(Xs, y)
        self.is_fitted = True

    def predict(self, X):  # noqa: N803
        if not self.is_fitted:
            raise ValueError('fit first')
        return self.lr.predict(self.scaler.transform(X))

    def predict_proba(self, X):  # noqa: N803
        if not self.is_fitted:
            raise ValueError('fit first')
        return self.lr.predict_proba(self.scaler.transform(X))

    def get_feature_importance(self) -> np.ndarray:
        coef = getattr(self.lr, 'coef_', None)
        if coef is None:
            return np.zeros(self.lr.n_features_in_ if hasattr(self.lr, 'n_features_in_') else 0)
        return np.abs(coef[0])


class CompilerProvenanceMLP:
    def __init__(
        self,
        hidden_layer_sizes=(256, 64),
        activation='relu',
        alpha=1e-4,
        learning_rate_init=1e-3,
        max_iter=400,
        random_state=42,
    ):
        self.scaler = StandardScaler()
        self.mlp = MLPClassifier(
            hidden_layer_sizes=hidden_layer_sizes,
            activation=activation,
            alpha=alpha,
            learning_rate_init=learning_rate_init,
            max_iter=max_iter,
            random_state=random_state,
            early_stopping=True,
            validation_fraction=0.1,
        )
        self.is_fitted = False

    def fit(self, X, y):  # noqa: N803
        Xs = self.scaler.fit_transform(X)
        self.mlp.fit(Xs, y)
        self.is_fitted = True

    def predict(self, X):  # noqa: N803
        if not self.is_fitted:
            raise ValueError('fit first')
        return self.mlp.predict(self.scaler.transform(X))

    def predict_proba(self, X):  # noqa: N803
        if not self.is_fitted:
            raise ValueError('fit first')
        return self.mlp.predict_proba(self.scaler.transform(X))


# -------------------- Trainers --------------------
class _BaseTrainer:
    def __init__(self, level: str, log_dir: str, logger_name: str, group_split: bool):
        self.level = level
        self.out_dir = Path(log_dir) / level / logger_name
        self.out_dir.mkdir(parents=True, exist_ok=True)
        logfile = self.out_dir.parent / f'{level}_{logger_name}.log'
        if logfile.exists():
            logfile.unlink()
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[logging.FileHandler(str(logfile)), logging.StreamHandler()],
        )
        self.logger = logging.getLogger(logger_name)
        self.group_split = bool(group_split)

    def _collect_files(self) -> list[tuple[str, int]]:
        base_non = Path('data') / self.level
        base_full = Path(f'data/{self.level}LTOfull')
        base_thin = Path(f'data/{self.level}LTOthin')
        out = []
        if base_non.is_dir():
            out += [(str(p), 0) for p in base_non.rglob('*.so')]
        else:
            self.logger.warning(f'输入目录不存在: {base_non}')
        if base_full.is_dir():
            out += [(str(p), 1) for p in base_full.rglob('*.so')]
        else:
            self.logger.warning(f'输入目录不存在: {base_full}')
        if base_thin.is_dir():
            out += [(str(p), 1) for p in base_thin.rglob('*.so')]
        else:
            self.logger.warning(f'输入目录不存在: {base_thin}')
        return out

    def _split_items(self, items):
        if self.group_split:
            self.logger.info('使用按库 key 的分组切分（group_split=True）')
            return groupwise_split_by_key(items)
        return stratified_split(items)

    @staticmethod
    def _metrics(y_true, y_pred):
        y_true = y_true.astype(int)
        y_pred = y_pred.astype(int)
        tp = int(((y_true == 1) & (y_pred == 1)).sum())
        tn = int(((y_true == 0) & (y_pred == 0)).sum())
        fp = int(((y_true == 0) & (y_pred == 1)).sum())
        fn = int(((y_true == 1) & (y_pred == 0)).sum())
        acc = (tp + tn) / max(1, (tp + tn + fp + fn))
        prec = tp / max(1, (tp + fp))
        rec = tp / max(1, (tp + fn))
        f1 = 0.0 if (prec + rec) == 0 else 2 * prec * rec / (prec + rec)
        return {'accuracy': acc, 'precision': prec, 'recall': rec, 'f1': f1, 'tp': tp, 'tn': tn, 'fp': fp, 'fn': fn}


class LegacyFeatureTrainer(_BaseTrainer):
    def __init__(self, level: str, log_dir: str = 'outs', group_split: bool = False):
        super().__init__(level, log_dir, 'legacy_features', group_split)

    def prepare(self):
        items = self._collect_files()
        c0 = count_by_label(items)
        self.logger.info(f'发现样本（文件级）：total={c0["total"]}, pos={c0["pos"]}, neg={c0["neg"]}')
        tr, va, te = self._split_items(items)
        extractor = LegacyFeatureExtractor()
        trds = LegacyFeatureDataset(tr, extractor)
        vads = LegacyFeatureDataset(va, extractor)
        teds = LegacyFeatureDataset(te, extractor)
        self.logger.info(f'特征维度: {len(trds.feature_names)} | 训练:{len(trds)} 验证:{len(vads)} 测试:{len(teds)}')
        return trds, vads, teds

    def run(self):
        try:
            trds, vads, teds = self.prepare()
            Xtr, ytr = trds.X, trds.y
            Xva, yva = vads.X, vads.y
            Xte, yte = teds.X, teds.y
            self.logger.info('开始 Legacy 特征训练（SVM + RF + GBDT + LR + MLP）...')

            # ---- SVM ----
            param_grid = {'C': [0.01, 0.1, 1.0, 10.0], 'class_weight': ['balanced', None]}
            base_svm = LinearSVC(random_state=42, max_iter=50000, dual=False, tol=1e-4)
            grid = GridSearchCV(
                base_svm,
                param_grid,
                cv=StratifiedKFold(n_splits=5, shuffle=True, random_state=42),
                scoring='precision',
                n_jobs=-1,
                verbose=0,
            )
            grid.fit(Xtr, ytr)
            best_params = grid.best_params_
            svm = CompilerProvenanceSVM(C=best_params['C'], class_weight=best_params['class_weight'])
            svm.fit(Xtr, ytr, Xva, yva)
            va_proba = svm.predict_proba(Xva)
            thr_svm, _ = optimize_threshold(yva, va_proba, metric='precision')
            te_pred_svm = (svm.predict_proba(Xte)[:, 1] >= thr_svm).astype(int)

            # ---- RF ----
            rf_space = [
                {'n_estimators': 300, 'max_depth': None},
                {'n_estimators': 600, 'max_depth': None},
                {'n_estimators': 400, 'max_depth': 20},
                {'n_estimators': 400, 'max_depth': 40},
            ]
            best_rf, best_rf_prec, _best_rf_params = None, -1.0, None
            for ps in rf_space:
                mdl = CompilerProvenanceRF(**ps)
                mdl.fit(Xtr, ytr)
                pred = mdl.predict(Xva)
                prec = precision_score(yva, pred, zero_division=0)
                if prec > best_rf_prec:
                    best_rf_prec, best_rf, _best_rf_params = prec, mdl, ps
            rf = best_rf
            va_proba = rf.predict_proba(Xva)
            thr_rf, _ = optimize_threshold(yva, va_proba, metric='precision')
            te_pred_rf = (rf.predict_proba(Xte)[:, 1] >= thr_rf).astype(int)

            # ---- GBDT ----
            gbdt_space = [
                {'n_estimators': 300, 'learning_rate': 0.05, 'max_depth': 3, 'subsample': 0.9},
                {'n_estimators': 500, 'learning_rate': 0.03, 'max_depth': 3, 'subsample': 0.9},
                {'n_estimators': 400, 'learning_rate': 0.05, 'max_depth': 4, 'subsample': 0.85},
            ]
            best_g, best_g_prec, _best_g_params = None, -1.0, None
            for ps in gbdt_space:
                mdl = CompilerProvenanceGBDT(**ps)
                mdl.fit(Xtr, ytr)
                pred = mdl.predict(Xva)
                prec = precision_score(yva, pred, zero_division=0)
                if prec > best_g_prec:
                    best_g_prec, best_g, _best_g_params = prec, mdl, ps
            gbdt = best_g
            va_proba = gbdt.predict_proba(Xva)
            thr_g, _ = optimize_threshold(yva, va_proba, metric='precision')
            te_pred_g = (gbdt.predict_proba(Xte)[:, 1] >= thr_g).astype(int)

            # ---- LR ----
            lr_space = [(0.5, None), (1.0, None), (2.0, None), (1.0, 'balanced'), (2.0, 'balanced')]
            best_lr, best_lr_prec, _best_lr_cfg = None, -1.0, None
            for C, cw in lr_space:
                mdl = CompilerProvenanceLR(C=C, penalty='l2', class_weight=cw)
                mdl.fit(Xtr, ytr)
                pred = mdl.predict(Xva)
                prec = precision_score(yva, pred, zero_division=0)
                if prec > best_lr_prec:
                    best_lr_prec, best_lr, _best_lr_cfg = prec, mdl, (C, cw)
            lr = best_lr
            va_proba = lr.predict_proba(Xva)
            thr_lr, _ = optimize_threshold(yva, va_proba, metric='precision')
            te_pred_lr = (lr.predict_proba(Xte)[:, 1] >= thr_lr).astype(int)

            # ---- MLP ----
            mlp_space = [(128,), (256, 64), (256, 128, 64)]
            best_mlp, best_mlp_prec, _best_mlp_cfg = None, -1.0, None
            for hl in mlp_space:
                mdl = CompilerProvenanceMLP(hidden_layer_sizes=hl)
                mdl.fit(Xtr, ytr)
                pred = mdl.predict(Xva)
                prec = precision_score(yva, pred, zero_division=0)
                if prec > best_mlp_prec:
                    best_mlp_prec, best_mlp, _best_mlp_cfg = prec, mdl, hl
            mlp = best_mlp
            va_proba = mlp.predict_proba(Xva)
            thr_mlp, _ = optimize_threshold(yva, va_proba, metric='precision')
            te_pred_mlp = (mlp.predict_proba(Xte)[:, 1] >= thr_mlp).astype(int)

            # 保存Random Forest模型和特征名称（供run_lto_pipeline.py使用）
            try:
                joblib.dump(rf, self.out_dir / 'rf_model.pkl')
                with open(self.out_dir / 'feature_names.json', 'w', encoding='utf-8') as f:
                    json.dump({'feature_names': trds.feature_names}, f, indent=2, ensure_ascii=False)
                self.logger.info(f'已保存Random Forest模型和特征名称到 {self.out_dir}')
            except Exception as e:
                self.logger.warning(f'保存模型失败: {e}')

            # 评估
            res = {
                'SVM': self._metrics(yte, te_pred_svm),
                'RF': self._metrics(yte, te_pred_rf),
                'GBDT': self._metrics(yte, te_pred_g),
                'LR': self._metrics(yte, te_pred_lr),
                'MLP': self._metrics(yte, te_pred_mlp),
            }
            lines = ['=' * 72, f'Legacy特征 LTO 检测报告（group_split={self.group_split}）', '=' * 72]
            for k, v in res.items():
                lines.append(
                    f'{k}: Prec={v["precision"]:.4f} F1={v["f1"]:.4f} Acc={v["accuracy"]:.4f} Rec={v["recall"]:.4f}'
                )
            with open(self.out_dir / 'report.txt', 'w', encoding='utf-8') as f:
                f.write('\n'.join(lines))
            print('\n'.join(lines))
            return True
        except Exception as e:
            self.logger.error(f'训练失败: {e}')
            return False


class CompilerProvenanceTrainer(_BaseTrainer):
    """hier：字节直方图+对统计（用于 baseline/hier 管线），也支持 group_split"""

    def __init__(self, level: str, log_dir: str = 'outs', hier_max_features: int = 128, group_split: bool = False):
        super().__init__(level, log_dir, 'compiler_provenance_svm', group_split)
        self.hier_max_features = int(hier_max_features)

    @staticmethod
    def _feature_group_of(name: str) -> str:
        if name.startswith('byte_freq_'):
            return 'LOW'
        if name.startswith('file_size') or name.startswith('percentile_'):
            return 'LOW'
        if name.startswith('byte_pair_'):
            return 'MID'
        if name in ('entropy', 'zero_ratio', 'ascii_ratio', 'byte_diversity', 'avg_byte_norm', 'byte_std_norm'):
            return 'MID'
        return 'NOISE'

    def _select_hierarchical_features(self, names: list[str], X: np.ndarray, y: np.ndarray) -> list[int]:  # noqa: N803
        try:
            f_vals, _ = f_classif(X, y)
        except Exception:
            f_vals = np.zeros(X.shape[1], dtype=np.float64)
        f_vals = np.nan_to_num(f_vals, nan=0.0, posinf=0.0, neginf=0.0)
        var_vals = np.var(X, axis=0)

        def _norm(v):
            v = np.asarray(v, dtype=np.float64)
            return (v / (v.max() + 1e-12)) if v.max() > 0 else np.zeros_like(v)

        score = _norm(f_vals) + 0.1 * _norm(var_vals)
        groups_static: dict[str, list[int]] = {'LOW': [], 'MID': [], 'NOISE': []}
        for i, n in enumerate(names):
            groups_static[self._feature_group_of(n)].append(i)
        low_idx = groups_static.get('LOW', [])
        mid_idx = groups_static.get('MID', [])
        pool_lm = low_idx + mid_idx
        high_pool: list[int] = []
        if pool_lm:
            k_high = max(1, int(np.ceil(0.10 * len(pool_lm))))
            high_pool = sorted(pool_lm, key=lambda i: score[i], reverse=True)[:k_high]
            low_idx = [i for i in low_idx if i not in high_pool]
            mid_idx = [i for i in mid_idx if i not in high_pool]
        K = max(1, self.hier_max_features)
        quota = {'LOW': 0.6, 'MID': 0.3, 'HIGH': 0.1}
        alloc = {g: int(np.floor(K * r)) for g, r in quota.items()}
        rem = K - sum(alloc.values())
        for g in ['LOW', 'MID', 'HIGH']:
            if rem <= 0:
                break
            alloc[g] += 1
            rem -= 1

        def pick_sorted(idxs: list[int], k: int) -> list[int]:
            if k <= 0 or not idxs:
                return []
            idxs_sorted = sorted(idxs, key=lambda i: score[i], reverse=True)
            return idxs_sorted[:k]

        selected: list[int] = []
        selected.extend(pick_sorted(low_idx, alloc['LOW']))
        selected.extend(pick_sorted(mid_idx, alloc['MID']))
        selected.extend(pick_sorted(high_pool, alloc['HIGH']))
        if len(selected) < K:
            remain = [i for i in (low_idx + mid_idx + high_pool) if i not in selected]
            remain_sorted = sorted(remain, key=lambda i: score[i], reverse=True)
            selected.extend(remain_sorted[: (K - len(selected))])
        seen = set()
        final = []
        for i in selected:
            if i in seen:
                continue
            seen.add(i)
            final.append(i)
            if len(final) >= K:
                break
        if not final:
            final = list(range(min(K, X.shape[1])))
        return final

    def prepare(self):
        items = self._collect_files()
        c0 = count_by_label(items)
        self.logger.info(f'发现样本（文件级）：total={c0["total"]}, pos={c0["pos"]}, neg={c0["neg"]}')
        tr, va, te = self._split_items(items)
        extractor = CompilerProvenanceExtractor(max_bytes=4096)
        trds = CompilerProvenanceDataset(tr, extractor)
        vads = CompilerProvenanceDataset(va, extractor)
        teds = CompilerProvenanceDataset(te, extractor)
        # 层次特征选择
        try:
            self.logger.info(f'hier模式：原始维度={len(trds.feature_names)}，K={self.hier_max_features}')
            sel_idx = self._select_hierarchical_features(trds.feature_names, trds.X, trds.y)
            if 0 < len(sel_idx) < len(trds.feature_names):
                trds.X = trds.X[:, sel_idx]
                vads.X = vads.X[:, sel_idx]
                teds.X = teds.X[:, sel_idx]
                trds.feature_names = [trds.feature_names[i] for i in sel_idx]
        except Exception as e:
            self.logger.warning(f'层次特征筛选失败，回退全量：{e}')
        self.logger.info(f'特征维度: {len(trds.feature_names)} | 训练:{len(trds)} 验证:{len(vads)} 测试:{len(teds)}')
        return trds, vads, teds

    def run(self):
        try:
            trds, vads, teds = self.prepare()
            Xtr, ytr = trds.X, trds.y
            Xva, yva = vads.X, vads.y
            Xte, yte = teds.X, teds.y
            self.logger.info('开始 hier 特征训练（SVM + RF + GBDT + LR + MLP）...')
            # 与 LegacyTrainer 同步的模型流程（略写）
            # 仅示范：SVM + GBDT
            param_grid = {'C': [0.01, 0.1, 1.0, 10.0], 'class_weight': ['balanced', None]}
            base_svm = LinearSVC(random_state=42, max_iter=50000, dual=False, tol=1e-4)
            grid = GridSearchCV(
                base_svm,
                param_grid,
                cv=StratifiedKFold(n_splits=5, shuffle=True, random_state=42),
                scoring='precision',
                n_jobs=-1,
                verbose=0,
            )
            grid.fit(Xtr, ytr)
            best_params = grid.best_params_
            svm = CompilerProvenanceSVM(C=best_params['C'], class_weight=best_params['class_weight'])
            svm.fit(Xtr, ytr, Xva, yva)
            thr, _ = optimize_threshold(yva, svm.predict_proba(Xva), metric='precision')
            te_pred = (svm.predict_proba(Xte)[:, 1] >= thr).astype(int)
            res = self._metrics(yte, te_pred)
            lines = ['=' * 72, f'hier特征 LTO 检测报告（group_split={self.group_split}）', '=' * 72]
            lines.append(
                f'SVM: Prec={res["precision"]:.4f} F1={res["f1"]:.4f} Acc={res["accuracy"]:.4f} Rec={res["recall"]:.4f}'
            )
            with open(self.out_dir / 'report.txt', 'w', encoding='utf-8') as f:
                f.write('\n'.join(lines))
            print('\n'.join(lines))
            return True
        except Exception as e:
            self.logger.error(f'训练失败: {e}')
            return False


class O3FeatureTrainer(LegacyFeatureTrainer):
    """O3 定向特征（增强）+ 全量模型对比；支持 group_split"""

    def __init__(self, level: str, log_dir: str = 'outs', group_split: bool = True):
        super().__init__(level=level, log_dir=log_dir, group_split=group_split)
        self.logger = logging.getLogger('o3_enhanced')

    def prepare(self):
        items = self._collect_files()
        c0 = count_by_label(items)
        self.logger.info(f'[O3] 发现样本（文件级）：total={c0["total"]}, pos={c0["pos"]}, neg={c0["neg"]}')
        tr, va, te = self._split_items(items)
        extractor = O3FocusedFeatureExtractor()
        trds = LegacyFeatureDataset(tr, extractor)
        vads = LegacyFeatureDataset(va, extractor)
        teds = LegacyFeatureDataset(te, extractor)
        self.logger.info(
            f'[O3] 特征维度: {len(trds.feature_names)} | 训练:{len(trds)} 验证:{len(vads)} 测试:{len(teds)}'
        )
        # 记录特征名便于诊断
        try:
            with open(self.out_dir / 'o3_feature_names.txt', 'w', encoding='utf-8') as f:
                for n in trds.feature_names:
                    f.write(n + '\n')
        except Exception:
            pass
        return trds, vads, teds


# -------------------- Hybrid（新） --------------------
def _select_hier_features_generic(names: list[str], X: np.ndarray, y: np.ndarray, K: int) -> list[int]:  # noqa: N803
    """
    仅对 HIER 子向量做层次选择；names 为去前缀后的原始 hier 特征名（如 byte_freq_0 等）
    返回的是**局部**索引（相对 X 的列）。
    """

    def group_of(n: str) -> str:
        if n.startswith('byte_freq_'):
            return 'LOW'
        if n.startswith('file_size') or n.startswith('percentile_'):
            return 'LOW'
        if n.startswith('byte_pair_'):
            return 'MID'
        if n in ('entropy', 'zero_ratio', 'ascii_ratio', 'byte_diversity', 'avg_byte_norm', 'byte_std_norm'):
            return 'MID'
        return 'NOISE'

    try:
        f_vals, _ = f_classif(X, y)
    except Exception:
        f_vals = np.zeros(X.shape[1], dtype=np.float64)
    f_vals = np.nan_to_num(f_vals, nan=0.0, posinf=0.0, neginf=0.0)
    var_vals = np.var(X, axis=0)

    def _norm(v):
        v = np.asarray(v, dtype=np.float64)
        return (v / (v.max() + 1e-12)) if v.max() > 0 else np.zeros_like(v)

    score = _norm(f_vals) + 0.1 * _norm(var_vals)

    groups = {'LOW': [], 'MID': [], 'NOISE': []}
    for i, n in enumerate(names):
        groups[group_of(n)].append(i)
    low_idx = groups.get('LOW', [])
    mid_idx = groups.get('MID', [])
    pool_lm = low_idx + mid_idx
    high_pool: list[int] = []
    if pool_lm:
        k_high = max(1, int(np.ceil(0.10 * len(pool_lm))))
        high_pool = sorted(pool_lm, key=lambda i: score[i], reverse=True)[:k_high]
        low_idx = [i for i in low_idx if i not in high_pool]
        mid_idx = [i for i in mid_idx if i not in high_pool]
    K = max(1, int(K))
    quota = {'LOW': 0.6, 'MID': 0.3, 'HIGH': 0.1}
    alloc = {g: int(np.floor(K * r)) for g, r in quota.items()}
    rem = K - sum(alloc.values())
    for g in ['LOW', 'MID', 'HIGH']:
        if rem <= 0:
            break
        alloc[g] += 1
        rem -= 1

    def pick_sorted(idxs: list[int], k: int) -> list[int]:
        if k <= 0 or not idxs:
            return []
        idxs_sorted = sorted(idxs, key=lambda i: score[i], reverse=True)
        return idxs_sorted[:k]

    selected: list[int] = []
    selected.extend(pick_sorted(low_idx, alloc['LOW']))
    selected.extend(pick_sorted(mid_idx, alloc['MID']))
    selected.extend(pick_sorted(high_pool, alloc['HIGH']))
    if len(selected) < K:
        remain = [i for i in (low_idx + mid_idx + high_pool) if i not in selected]
        remain_sorted = sorted(remain, key=lambda i: score[i], reverse=True)
        selected.extend(remain_sorted[: (K - len(selected))])
    seen = set()
    final = []
    for i in selected:
        if i in seen:
            continue
        seen.add(i)
        final.append(i)
        if len(final) >= K:
            break
    if not final:
        final = list(range(min(K, X.shape[1])))
    return final


class HybridFeatureExtractor:
    """
    并行抽取三路特征并拼接（带前缀）：
      - LEG_* : LegacyFeatureExtractor
      - HIER_*: CompilerProvenanceExtractor
      - O3_*  : O3FocusedFeatureExtractor
    具体的 HIER 子向量筛选在 Trainer 中进行（保持 extractor 无状态）。
    """

    def __init__(self, hier_max_bytes: int = 4096):
        self.leg = LegacyFeatureExtractor()
        self.hier = CompilerProvenanceExtractor(max_bytes=hier_max_bytes)
        self.o3 = O3FocusedFeatureExtractor()

    def extract(self, path: str) -> tuple[np.ndarray, list[str], str]:
        f_leg, n_leg, k = self.leg.extract(path)
        f_hier, n_hier, _ = self.hier.extract(path)
        f_o3, n_o3, _ = self.o3.extract(path)
        n_leg = [f'LEG_{n}' for n in n_leg]
        n_hier = [f'HIER_{n}' for n in n_hier]
        n_o3 = [f'O3_{n}' for n in n_o3]
        feats = np.concatenate([f_leg, f_hier, f_o3]).astype(np.float32)
        names = n_leg + n_hier + n_o3
        return feats, names, k


class HybridFeatureTrainer(_BaseTrainer):
    """
    混合特征训练器：
      - 仅对 HIER 子向量做层次筛选（K 可配置）
      - 训练全套 6 模型 + 校准 + 阈值优化
    """

    def __init__(
        self, level: str, log_dir: str = 'outs', group_split: bool = True, hybrid_hier_max_features: int = 128
    ):
        super().__init__(level, log_dir, 'hybrid_features', group_split)
        self.hier_k = int(hybrid_hier_max_features)

    def prepare(self):
        items = self._collect_files()
        c0 = count_by_label(items)
        self.logger.info(f'[Hybrid] 发现样本（文件级）：total={c0["total"]}, pos={c0["pos"]}, neg={c0["neg"]}')
        tr, va, te = self._split_items(items)
        extractor = HybridFeatureExtractor()
        trds = LegacyFeatureDataset(tr, extractor)
        vads = LegacyFeatureDataset(va, extractor)
        teds = LegacyFeatureDataset(te, extractor)

        self.logger.info(
            f'[Hybrid] 初始维度: {len(trds.feature_names)} | 训练:{len(trds)} 验证:{len(vads)} 测试:{len(teds)}'
        )

        # ---- 只对子向量 HIER_* 做层次筛选 ----
        try:
            hier_idx_tr = [i for i, n in enumerate(trds.feature_names) if n.startswith('HIER_')]
            if self.hier_k > 0 and len(hier_idx_tr) > 0:
                # 去前缀后的名字
                hier_names_raw = [trds.feature_names[i][len('HIER_') :] for i in hier_idx_tr]
                sel_local = _select_hier_features_generic(hier_names_raw, trds.X[:, hier_idx_tr], trds.y, K=self.hier_k)
                sel_global = [hier_idx_tr[i] for i in sel_local]
                keep = set(
                    [i for i in range(len(trds.feature_names)) if not trds.feature_names[i].startswith('HIER_')]
                    + sel_global
                )
                keep_idx = sorted(keep)

                trds.X = trds.X[:, keep_idx]
                vads.X = vads.X[:, keep_idx]
                teds.X = teds.X[:, keep_idx]

                trds.feature_names = [trds.feature_names[i] for i in keep_idx]
                vads.feature_names = trds.feature_names[:]
                teds.feature_names = trds.feature_names[:]

                self.logger.info(f'[Hybrid] HIER 子向量裁剪至 {self.hier_k} 维，整体维度={len(trds.feature_names)}')
        except Exception as e:
            self.logger.warning(f'[Hybrid] 层次特征筛选失败，回退全量：{e}')

        # 记录最终特征名
        try:
            with open(self.out_dir / 'hybrid_feature_names.txt', 'w', encoding='utf-8') as f:
                for n in trds.feature_names:
                    f.write(n + '\n')
        except Exception:
            pass

        return trds, vads, teds

    def run(self):
        try:
            trds, vads, teds = self.prepare()
            Xtr, ytr = trds.X, trds.y
            Xva, yva = vads.X, vads.y
            Xte, yte = teds.X, teds.y
            self.logger.info('[Hybrid] 开始训练（SVM + RF + GBDT + LR + MLP）...')

            # ---- SVM ----
            param_grid = {'C': [0.01, 0.1, 1.0, 10.0], 'class_weight': ['balanced', None]}
            base_svm = LinearSVC(random_state=42, max_iter=50000, dual=False, tol=1e-4)
            grid = GridSearchCV(
                base_svm,
                param_grid,
                cv=StratifiedKFold(n_splits=5, shuffle=True, random_state=42),
                scoring='precision',
                n_jobs=-1,
                verbose=0,
            )
            grid.fit(Xtr, ytr)
            best_params = grid.best_params_
            svm = CompilerProvenanceSVM(C=best_params['C'], class_weight=best_params['class_weight'])
            svm.fit(Xtr, ytr, Xva, yva)
            thr_svm, _ = optimize_threshold(yva, svm.predict_proba(Xva), metric='precision')
            te_pred_svm = (svm.predict_proba(Xte)[:, 1] >= thr_svm).astype(int)

            # ---- RF ----
            rf_space = [
                {'n_estimators': 300, 'max_depth': None},
                {'n_estimators': 600, 'max_depth': None},
                {'n_estimators': 400, 'max_depth': 20},
                {'n_estimators': 400, 'max_depth': 40},
            ]
            best_rf, best_rf_prec = None, -1.0
            for ps in rf_space:
                mdl = CompilerProvenanceRF(**ps)
                mdl.fit(Xtr, ytr)
                pred = mdl.predict(Xva)
                prec = precision_score(yva, pred, zero_division=0)
                if prec > best_rf_prec:
                    best_rf_prec, best_rf = prec, mdl
            rf = best_rf
            thr_rf, _ = optimize_threshold(yva, rf.predict_proba(Xva), metric='precision')
            te_pred_rf = (rf.predict_proba(Xte)[:, 1] >= thr_rf).astype(int)

            # ---- GBDT ----
            gbdt_space = [
                {'n_estimators': 300, 'learning_rate': 0.05, 'max_depth': 3, 'subsample': 0.9},
                {'n_estimators': 500, 'learning_rate': 0.03, 'max_depth': 3, 'subsample': 0.9},
                {'n_estimators': 400, 'learning_rate': 0.05, 'max_depth': 4, 'subsample': 0.85},
            ]
            best_g, best_g_prec = None, -1.0
            for ps in gbdt_space:
                mdl = CompilerProvenanceGBDT(**ps)
                mdl.fit(Xtr, ytr)
                pred = mdl.predict(Xva)
                prec = precision_score(yva, pred, zero_division=0)
                if prec > best_g_prec:
                    best_g_prec, best_g = prec, mdl
            gbdt = best_g
            thr_g, _ = optimize_threshold(yva, gbdt.predict_proba(Xva), metric='precision')
            te_pred_g = (gbdt.predict_proba(Xte)[:, 1] >= thr_g).astype(int)

            # ---- LR ----
            lr_space = [(0.5, None), (1.0, None), (2.0, None), (1.0, 'balanced'), (2.0, 'balanced')]
            best_lr, best_lr_prec = None, -1.0
            for C, cw in lr_space:
                mdl = CompilerProvenanceLR(C=C, penalty='l2', class_weight=cw)
                mdl.fit(Xtr, ytr)
                pred = mdl.predict(Xva)
                prec = precision_score(yva, pred, zero_division=0)
                if prec > best_lr_prec:
                    best_lr_prec, best_lr = prec, mdl
            lr = best_lr
            thr_lr, _ = optimize_threshold(yva, lr.predict_proba(Xva), metric='precision')
            te_pred_lr = (lr.predict_proba(Xte)[:, 1] >= thr_lr).astype(int)

            # ---- MLP ----
            mlp_space = [(128,), (256, 64), (256, 128, 64)]
            best_mlp, best_mlp_prec = None, -1.0
            for hl in mlp_space:
                mdl = CompilerProvenanceMLP(hidden_layer_sizes=hl)
                mdl.fit(Xtr, ytr)
                pred = mdl.predict(Xva)
                prec = precision_score(yva, pred, zero_division=0)
                if prec > best_mlp_prec:
                    best_mlp_prec, best_mlp = prec, mdl
            mlp = best_mlp
            thr_mlp, _ = optimize_threshold(yva, mlp.predict_proba(Xva), metric='precision')
            te_pred_mlp = (mlp.predict_proba(Xte)[:, 1] >= thr_mlp).astype(int)

            # 保存Random Forest模型和特征名称（供run_lto_pipeline.py使用）
            try:
                joblib.dump(rf, self.out_dir / 'rf_model.pkl')
                with open(self.out_dir / 'feature_names.json', 'w', encoding='utf-8') as f:
                    json.dump({'feature_names': trds.feature_names}, f, indent=2, ensure_ascii=False)
                self.logger.info(f'已保存Random Forest模型和特征名称到 {self.out_dir}')
            except Exception as e:
                self.logger.warning(f'保存模型失败: {e}')

            # 评估
            res = {
                'SVM': self._metrics(yte, te_pred_svm),
                'RF': self._metrics(yte, te_pred_rf),
                'GBDT': self._metrics(yte, te_pred_g),
                'LR': self._metrics(yte, te_pred_lr),
                'MLP': self._metrics(yte, te_pred_mlp),
            }
            lines = ['=' * 72, f'Hybrid特征 LTO 检测报告（group_split={self.group_split}）', '=' * 72]
            for k, v in res.items():
                lines.append(
                    f'{k}: Prec={v["precision"]:.4f} F1={v["f1"]:.4f} Acc={v["accuracy"]:.4f} Rec={v["recall"]:.4f}'
                )
            with open(self.out_dir / 'report.txt', 'w', encoding='utf-8') as f:
                f.write('\n'.join(lines))
            print('\n'.join(lines))
            return True
        except Exception as e:
            self.logger.error(f'[Hybrid] 训练失败: {e}')
            return False


# -------------------- CLI --------------------
def main(args):
    set_global_seed(args.seed)
    if args.feature_mode == 'hier':
        trainer = CompilerProvenanceTrainer(
            level=args.level, hier_max_features=args.hier_max_features, group_split=args.group_split
        )
        print('开始 hier 特征 LTO 检测训练（支持 group_split）...')
    elif args.feature_mode == 'o3':
        trainer = O3FeatureTrainer(level=args.level, group_split=args.group_split)
        print('开始 O3 定向特征（增强版） LTO 检测训练（支持 group_split）...')
    elif args.feature_mode == 'hybrid':
        trainer = HybridFeatureTrainer(
            level=args.level, group_split=args.group_split, hybrid_hier_max_features=args.hybrid_hier_max_features
        )
        print('开始 Hybrid（LEG+HIER+O3 融合） LTO 检测训练（支持 group_split）...')
    else:
        trainer = LegacyFeatureTrainer(level=args.level, group_split=args.group_split)
        print('开始 Legacy 特征 LTO 检测训练（支持 group_split）...')
    print('=' * 60)
    ok = trainer.run()
    if ok:
        out_sub = {
            'hier': 'compiler_provenance_svm',
            'o3': 'legacy_features',
            'default': 'legacy_features',
            'hybrid': 'hybrid_features',
        }.get(args.feature_mode, 'legacy_features')
        print(f'\n✅ 完成！📦 产物目录: outs/{args.level}/{out_sub}')
    else:
        print('\n❌ 训练失败')


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description='编译器溯源恢复 LTO 检测器（Linear SVM + Variants）')
    ap.add_argument('--level', default='O3', help='优化级别：O2 / O3 / Os')
    ap.add_argument('--seed', type=int, default=42, help='随机种子')
    ap.add_argument(
        '--feature-mode',
        choices=['default', 'hier', 'o3', 'hybrid'],
        default='hybrid',
        help='特征模式：default（legacy）、hier（字节直方图）、o3（O3增强）、hybrid（三路融合）',
    )
    ap.add_argument('--hier-max-features', type=int, default=128, help='hier模式的特征上限')
    ap.add_argument('--hybrid-hier-max-features', type=int, default=128, help='hybrid模式中 HIER 子向量保留维度')
    # 注意：当前参数语义沿用原版：不带该参=开启 group_split，加上该参=关闭。
    ap.add_argument(
        '--group-split', action='store_false', help='按库 key 分组切分，避免泄漏（开=跨库泛化，关=库内泛化）'
    )
    args = ap.parse_args()
    main(args)
