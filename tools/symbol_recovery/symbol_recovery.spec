# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all
import os
import sys

datas = [('core/utils', 'core/utils'), ('core/analyzers', 'core/analyzers'), ('core/llm', 'core/llm')]
binaries = []
hiddenimports = ['core.utils', 'core.analyzers', 'core.llm']

# 打包 radare2 二进制 + 反编译插件（r2dec/r2ghidra），由 _find_bundled_r2 在 sys._MEIPASS/r2/ 下查找
_r2_bundle = os.path.join(os.path.dirname(SPEC), '..', '..', 'dist', 'tools', 'bin', 'r2')
if os.path.isdir(_r2_bundle):
    for root, _dirs, files in os.walk(_r2_bundle):
        for f in files:
            src = os.path.join(root, f)
            # dst 使用父目录的相对路径，PyInstaller 会自动追加 basename → 得到 r2/r2.exe, r2/plugins/r2dec.dll 等
            dst = os.path.relpath(os.path.dirname(src), os.path.dirname(_r2_bundle))
            datas.append((src, dst.replace('\\', '/')))
    print(f'[symbol_recovery.spec] 已将 r2 打包进 frozen 应用（{_r2_bundle}）')
    # r2 的 dir.plugins 硬编码为 <binary>/../lib/plugins/
    # 二进制在 sys._MEIPASS/r2/radare2.exe，所以插件应在 sys._MEIPASS/lib/plugins/
    # 如构建机器安装了反编译插件（r2dec/r2ghidra），会自动打包
    _lib_plugins = os.path.normpath(os.path.join(_r2_bundle, '..', 'lib', 'plugins'))
    if os.path.isdir(_lib_plugins):
        for root, _dirs, files in os.walk(_lib_plugins):
            for f in files:
                src = os.path.join(root, f)
                datas.append((src, 'lib/plugins'))
        print(f'[symbol_recovery.spec] 已将 r2 反编译插件打包进 frozen 应用（{_lib_plugins}）')
    # 同时检查 r2/plugins/ (bundle_radare2.js 把插件放在 r2/plugins/)
    # r2 的 dir.plugins 硬编码为 <binary>/../lib/plugins/，所以目标路径固定为 lib/plugins/
    _r2_plugins = os.path.join(_r2_bundle, 'plugins')
    if os.path.isdir(_r2_plugins):
        for f in os.listdir(_r2_plugins):
            src = os.path.join(_r2_plugins, f)
            if os.path.isfile(src):
                datas.append((src, 'lib/plugins'))
        print(f'[symbol_recovery.spec] 已将 r2/plugins/ 插件映射到 lib/plugins/（{_r2_plugins}）')
else:
    print(f'[symbol_recovery.spec] 警告：未找到 r2 bundle 目录 {_r2_bundle}，跳过 r2 打包')
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
