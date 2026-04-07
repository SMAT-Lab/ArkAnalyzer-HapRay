# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all
import os
import sys

datas = [('core/utils', 'core/utils'), ('core/analyzers', 'core/analyzers'), ('core/llm', 'core/llm')]
binaries = []
hiddenimports = ['core.utils', 'core.analyzers', 'core.llm']
IS_WIN = sys.platform.startswith('win')
IS_DARWIN = sys.platform == 'darwin'
# macOS：UPX + Mach-O 重签会导致公证报 Python 等 signature invalid（与 perf_testing 一致仅 Windows 用 UPX）
USE_UPX = IS_WIN
STRIP_BINARIES = (not IS_WIN) and (not IS_DARWIN)
_CODESIGN_IDENTITY = (os.environ.get("APPLE_SIGNING_IDENTITY", "").strip() or None) if IS_DARWIN else None
# 显式收集 numpy（pandas 的依赖）
tmp_ret = collect_all('numpy')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
# 添加 numpy 的关键隐藏导入
hiddenimports += [
    'numpy.core._multiarray_umath',
    'numpy.core._multiarray_tests',
    'numpy.linalg._umath_linalg',
    'numpy.fft._pocketfft_internal',
    'numpy.random._common',
    'numpy.random._bounded_integers',
    'numpy.random._mt19937',
    'numpy.random._philox',
    'numpy.random._pcg64',
    'numpy.random._sfc64',
    'numpy.random._generator',
]
tmp_ret = collect_all('pyelftools')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('capstone')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('pandas')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('openpyxl')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('r2pipe')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['pkg_resources'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    name='symbol-recovery',
    debug=False,
    bootloader_ignore_signals=False,
    strip=STRIP_BINARIES,
    upx=USE_UPX,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=_CODESIGN_IDENTITY,
    entitlements_file=None,
)
