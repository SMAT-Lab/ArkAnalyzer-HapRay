# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for HapRay GUI
"""
from PyInstaller.utils.hooks import collect_all, collect_data_files
import os
from pathlib import Path

# 获取项目根目录
project_root = Path(SPECPATH)

# 收集数据文件
datas = [
    (str(project_root / 'resources'), 'resources'),  # 包含资源文件（图标等）
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
    'gui',
    'gui.main_window',
    'gui.tool_pages',
    'gui.result_viewer',
    'gui.settings_dialog',
]

# 收集 PySide6 相关模块
print('Collecting PySide6 modules...')
try:
    pyside6_data = collect_data_files('PySide6')
    datas += pyside6_data
    
    # PySide6 核心模块
    pyside6_modules = [
        'PySide6.QtCore',
        'PySide6.QtGui',
        'PySide6.QtWidgets',
        'PySide6.QtOpenGL',
        'PySide6.QtOpenGLWidgets',
        'PySide6.QtPrintSupport',
        'PySide6.QtSvg',
        'PySide6.QtSvgWidgets',
        'PySide6.QtTest',
        'PySide6.QtUiTools',
        'PySide6.QtXml',
    ]
    
    for module in pyside6_modules:
        try:
            tmp_ret = collect_all(module)
            datas += tmp_ret[0]
            binaries += tmp_ret[1]
            hiddenimports += tmp_ret[2]
        except Exception as e:
            print(f'Warning: Failed to collect {module}: {e}')
    
    # 添加 PySide6 的隐藏导入
    hiddenimports += [
        'PySide6',
        'PySide6.QtCore',
        'PySide6.QtGui',
        'PySide6.QtWidgets',
        'PySide6.sip',
    ]
except Exception as e:
    print(f'Warning: Failed to collect PySide6: {e}')

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
    'PySide6.QtWebEngine',
    'PySide6.QtWebEngineCore',
    'PySide6.QtWebEngineWidgets',
    'PySide6.QtBluetooth',
    'PySide6.QtDBus',
    'PySide6.QtDesigner',
    'PySide6.QtHelp',
    'PySide6.QtLocation',
    'PySide6.QtMultimedia',
    'PySide6.QtMultimediaWidgets',
    'PySide6.QtNfc',
    'PySide6.QtPositioning',
    'PySide6.QtQml',
    'PySide6.QtQuick',
    'PySide6.QtQuickWidgets',
    'PySide6.QtRemoteObjects',
    'PySide6.QtSensors',
    'PySide6.QtSerialPort',
    'PySide6.QtSql',
    'PySide6.QtWebChannel',
    'PySide6.QtWebSockets',
]

a = Analysis(
    ['main.py'],
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
    name='HapRay-GUI',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    console=False,  # GUI应用，不显示控制台窗口
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(project_root / 'resources' / 'icon.ico')
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='hapray-gui',
)

