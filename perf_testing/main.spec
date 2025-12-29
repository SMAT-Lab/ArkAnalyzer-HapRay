# -*- mode: python ; coding: utf-8 -*-
import pkg_resources
import sys
import os
from PyInstaller.utils.hooks import collect_dynamic_libs, collect_data_files, collect_all

venv_packages = [pkg.key for pkg in pkg_resources.working_set]
venv_packages.append('ohos')
venv_packages.append('devicetest')
venv_packages.append('xdevice')
venv_packages.append('hypium')
venv_packages.append('yaml')
venv_packages.append('telnetlib')
venv_packages.append('xml.dom')
venv_packages.append('xml.etree.ElementTree')

# 显式收集 numpy（pandas 的依赖）
tmp_ret = collect_all('numpy')
datas = tmp_ret[0]
binaries = tmp_ret[1]
hiddenimports = tmp_ret[2]
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

# 收集 pandas
tmp_ret = collect_all('pandas')
datas += tmp_ret[0]
binaries += tmp_ret[1]
hiddenimports += tmp_ret[2]

# 添加项目特定的数据
datas.append(('hapray', 'hapray'))

# 合并所有隐藏导入
all_hiddenimports = venv_packages + hiddenimports

# 查找有效的 site-packages 目录
site_packages_dir = None
for path in sys.path:
    if 'site-packages' in path and os.path.isdir(path):
        site_packages_dir = path
        break

if site_packages_dir and os.path.exists(site_packages_dir):
    for item in os.listdir(site_packages_dir):
        item_path = os.path.join(site_packages_dir, item)
        if os.path.isdir(item_path) and not item.startswith('__'):
            datas.append((item_path, item))

a = Analysis(
    ['scripts/main.py'],
    pathex=['./'],
    binaries=binaries,
    datas=datas,
    hiddenimports=all_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib',
        'PIL',
        'Pillow',
        'tkinter',
        'IPython',
        'jupyter',
        'notebook',
        'pytest',
        'sphinx',
        'numpy.tests',
        'pandas.tests',
        'pkg_resources',  # 排除已弃用的 pkg_resources，使用 importlib.metadata 和 importlib.resources 替代
    ],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    [],
    exclude_binaries=True,
    name='perf-testing',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # 禁用 UPX 以避免 DLL 加载问题
    upx_exclude=[],
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,  # 禁用 UPX 以避免 DLL 加载问题
    upx_exclude=[],
    name='perf-testing',
)
