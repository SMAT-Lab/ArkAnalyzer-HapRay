# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for HapRay CMD
命令行版本
"""
from PyInstaller.utils.hooks import collect_all, collect_data_files
import os
from pathlib import Path

# 获取项目根目录
project_root = Path(SPECPATH)

# 收集数据文件
datas = [
    (str(project_root / 'plugins'), 'plugins'),  # 包含插件目录
]

# 收集项目模块
binaries = []

# 项目自身模块
hiddenimports = [
    'core',
    'core.base_tool',
    'core.config_manager',
    'core.tool_executor',
    'core.result_processor',
    'core.file_utils',
    'core.logger',
    'core.plugin_base',
    'core.plugin_loader',
]

# 收集其他可能需要的模块
additional_modules = [
    'json',
    'pathlib',
    'threading',
    'subprocess',
    'logging',
    'dataclasses',
    'typing',
    'abc',
    'argparse',
]

for module in additional_modules:
    try:
        tmp_ret = collect_all(module)
        datas += tmp_ret[0]
        binaries += tmp_ret[1]
        hiddenimports += tmp_ret[2]
    except Exception:
        pass

# 排除不需要的模块以减小体积
excludes = [
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
    'numpy.tests',
    'pandas.tests',
    'scipy.tests',
    'PySide6',  # 命令行版本不需要 GUI
    'PyQt5',
    'PyQt6',
    'PyQt4',
]

a = Analysis(
    ['cmd.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='hapray-cmd',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    console=True,  # 命令行应用，显示控制台窗口
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
    upx=True,
    upx_exclude=[],
    name='hapray-cmd',
)

