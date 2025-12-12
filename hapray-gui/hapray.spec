# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for HapRay
合并版本：同时编译 GUI 和 CMD，共用一个 _internal 目录
"""
from PyInstaller.utils.hooks import collect_all, collect_data_files
import os
from pathlib import Path

# 获取项目根目录
project_root = Path(SPECPATH)

# 收集数据文件（合并两个版本的数据）
datas = [
    (str(project_root / 'resources'), 'resources'),  # GUI 资源文件（图标等）
    (str(project_root / 'plugins'), 'plugins'),  # CMD 插件目录
]

# 收集项目模块
binaries = []

# 项目自身模块（合并两个版本的模块）
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
    'gui',
    'gui.main_window',
    'gui.tool_pages',
    'gui.result_viewer',
    'gui.settings_dialog',
]

# 收集 PySide6 相关模块（GUI 需要）
print('Collecting PySide6 modules...')
try:
    # 只收集必要的 PySide6 数据文件，避免框架符号链接问题
    import PySide6
    pyside6_path = PySide6.__path__[0]
    
    # 只添加必要的 Qt 插件和资源
    pyside6_path_obj = Path(pyside6_path)
    
    # 添加 Qt 插件（不包括所有插件）
    plugins_dir = pyside6_path_obj / 'Qt' / 'plugins'
    if plugins_dir.exists():
        # 只收集必要的插件
        essential_plugins = ['platforms', 'imageformats', 'iconengines']
        for plugin in essential_plugins:
            plugin_path = plugins_dir / plugin
            if plugin_path.exists():
                datas.append((str(plugin_path), f'PySide6/Qt/plugins/{plugin}'))
    
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
            # 过滤掉 framework 文件，避免符号链接问题
            filtered_datas = [d for d in tmp_ret[0] if 'framework' not in str(d).lower() or 'Versions' not in str(d)]
            datas += filtered_datas
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
    'argparse',  # CMD 需要
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
    # 排除不需要的 PySide6 模块
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
    # 排除其他 GUI 框架（我们使用 PySide6）
    'PyQt5',
    'PyQt6',
    'PyQt4',
]

# 创建统一的 Analysis（同时分析两个入口点，收集所有依赖）
print('Analyzing main.py and cmd.py...')
a = Analysis(
    ['main.py', 'cmd.py'],  # 同时分析两个入口点
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

# 创建统一的 PYZ
pyz = PYZ(a.pure, a.zipped_data, cipher=None)

# 从 a.scripts 中筛选出对应的脚本
# PyInstaller 的脚本对象是 TOC 对象，格式为 (name, path, typecode)
# 或者可能是有 name 属性的对象
gui_scripts = []
cmd_scripts = []

for script in a.scripts:
    # 尝试多种方式获取脚本名称
    script_name = None
    if isinstance(script, tuple) and len(script) > 0:
        # TOC 格式：(name, path, typecode)
        script_name = script[0] if isinstance(script[0], str) else str(script[0])
    elif hasattr(script, 'name'):
        script_name = script.name
    elif hasattr(script, '__str__'):
        script_name = str(script)
    
    # 根据脚本名称分类
    if script_name:
        if 'main.py' in script_name or 'main' in script_name.lower():
            gui_scripts.append(script)
        elif 'cmd.py' in script_name or 'cmd' in script_name.lower():
            cmd_scripts.append(script)

# 如果筛选失败，使用索引作为备选方案
if not gui_scripts or not cmd_scripts:
    if len(a.scripts) >= 2:
        if not gui_scripts:
            gui_scripts = [a.scripts[0]]
        if not cmd_scripts:
            cmd_scripts = [a.scripts[1]]
    elif len(a.scripts) == 1:
        # 如果只有一个脚本，可能需要重新检查
        print(f'Warning: Only found {len(a.scripts)} script(s), expected 2')

# 创建 GUI 可执行文件
exe_gui = EXE(
    pyz,
    gui_scripts,
    [],
    exclude_binaries=True,
    name='ArkAnalyzer-HapRay-GUI',
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
    icon=str(project_root / 'resources' / 'icon.ico') if (project_root / 'resources' / 'icon.ico').exists() else None
)

# 创建 CMD 可执行文件
exe_cmd = EXE(
    pyz,
    cmd_scripts,
    [],
    exclude_binaries=True,
    name='ArkAnalyzer-HapRay',
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
    icon=str(project_root / 'resources' / 'icon.ico') if (project_root / 'resources' / 'icon.ico').exists() else None
)

# 使用一个 COLLECT 收集所有内容到一个目录（共用一个 _internal）
# name 设置为空字符串或 None，使输出直接到 distpath 指定的目录
coll = COLLECT(
    exe_gui,
    exe_cmd,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='',  # 空名称，使输出直接到 distpath 目录
    copy_metadata=False,
)

