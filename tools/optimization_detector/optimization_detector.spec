# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for optimization-detector (onedir mode - 更快的启动速度)
使用目录模式而不是单文件模式，启动速度更快（但文件分散在目录中）
"""

import os
from pathlib import Path

block_cipher = None

# 获取项目根目录
project_root = Path(SPECPATH)
models_path = project_root / 'optimization_detector' / 'models'

# 收集模型文件
datas = []
if models_path.exists():
    # 添加整个 models 目录
    datas.append((str(models_path), 'optimization_detector/models'))

a = Analysis(
    ['optimization_detector/cli.py'],
    pathex=[],
    binaries=[],
    datas=datas,
hiddenimports=[
        # 项目自身模块
        'optimization_detector',
        'optimization_detector.cli',
        'optimization_detector.file_info',
        'optimization_detector.invoke_symbols',
        'optimization_detector.lto_detector',
        'optimization_detector.lto_feature_pipeline',
        'optimization_detector.optimization_detector',
        # 依赖库（确保在PyInstaller中正确打包）
        'tensorflow',
        'tensorflow.keras',
        'tensorflow.keras.models',
        'tensorflow.python',
        'tensorflow.python.keras',
        'tensorflow.python.keras.api',
        'tensorflow.python.keras.api._v2.keras',
        'tensorflow.python.keras.api._v2.keras.models',
        'numpy',
        'numpy.core',
        'numpy.core._multiarray_umath',
        'pandas',
        'pandas._libs',
        'pandas._libs.tslibs',
        'pandas.io',
        'pandas.io.excel',
        'pandas.io.excel._base',
        'pandas.io.excel._xlsxwriter',
        'tqdm',
        'elftools',
        'elftools.elf',
        'elftools.elf.elffile',
        'arpy',
        'joblib',
        'importlib.resources',
    ],
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
        'setuptools',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,  # 目录模式：不将所有文件打包到单个exe
    name='opt-detector',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='opt-detector',
)

