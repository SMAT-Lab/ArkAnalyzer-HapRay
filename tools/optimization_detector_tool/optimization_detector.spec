# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for optimization-detector
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
    
    # 或者逐个添加文件
    # for model_file in models_path.rglob('*'):
    #     if model_file.is_file():
    #         rel_path = model_file.relative_to(project_root)
    #         datas.append((str(model_file), str(rel_path.parent)))

a = Analysis(
    ['optimization_detector/cli.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=[
        'optimization_detector',
        'optimization_detector.file_info',
        'optimization_detector.optimization_detector',
        'optimization_detector.lto_detector',
        'optimization_detector.resource_utils',
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
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='opt-detector',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,  # 使用 UPX 压缩（如果可用）
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # 控制台应用
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # 可以添加图标文件路径
)

