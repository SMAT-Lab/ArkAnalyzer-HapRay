# -*- mode: python ; coding: utf-8 -*-
import pkg_resources
import sys
import os
from PyInstaller.utils.hooks import collect_dynamic_libs, collect_data_files

venv_packages = [pkg.key for pkg in pkg_resources.working_set]
venv_packages.append('ohos')
venv_packages.append('devicetest')
venv_packages.append('xdevice')
venv_packages.append('hypium')
venv_packages.append('yaml')
venv_packages.append('telnetlib')
venv_packages.append('xml.dom')
venv_packages.append('xml.etree.ElementTree')

datas = [
    ('hapray', 'hapray'),
]

# 收集 numpy 的数据文件和 DLL
try:
    numpy_datas = collect_data_files('numpy', include_py_files=False)
    datas.extend(numpy_datas)
except Exception as e:
    print(f"Warning: Could not collect numpy data files: {e}")

# 收集 numpy 的动态库
binaries = []
try:
    numpy_libs = collect_dynamic_libs('numpy')
    binaries.extend(numpy_libs)
except Exception as e:
    print(f"Warning: Could not collect numpy dynamic libs: {e}")

# 收集 pandas 的动态库
try:
    pandas_libs = collect_dynamic_libs('pandas')
    binaries.extend(pandas_libs)
except Exception as e:
    print(f"Warning: Could not collect pandas dynamic libs: {e}")

# 查找有效的 site-packages 目录
site_packages_dir = None
for path in sys.path:
    if 'site-packages' in path and os.path.isdir(path):
        site_packages_dir = path
        break

# 定义需要排除的目录和文件模式
exclude_patterns = {
    'tests', 'test', 'testing',
    'docs', 'doc', 'documentation',
    'examples', 'example', 'samples',
    'benchmarks', 'benchmark',
}

def should_exclude(name):
    """判断是否应该排除某个包"""
    name_lower = name.lower()
    # 排除测试、文档、示例等目录
    if any(pattern in name_lower for pattern in exclude_patterns):
        return True
    # 排除特定的大型测试包
    if name.startswith('test'):
        return True
    return False

if site_packages_dir and os.path.exists(site_packages_dir):
    for item in os.listdir(site_packages_dir):
        item_path = os.path.join(site_packages_dir, item)
        if os.path.isdir(item_path) and not item.startswith('__') and not should_exclude(item):
            datas.append((item_path, item))

a = Analysis(
    ['scripts/main.py'],
    pathex=['./'],
    binaries=binaries,
    datas=datas,
    hiddenimports=venv_packages,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # 排除测试模块
        'pytest', 'unittest', 'nose', '_pytest',
        'test', 'tests', 'testing',
        # 排除文档和示例
        'sphinx', 'doctest',
        # 排除不需要的numpy测试模块
        'numpy.testing', 'numpy.tests',
        'numpy.f2py.tests',
        # 排除pandas测试模块
        'pandas.tests', 'pandas.testing',
        # 排除开发工具
        'IPython', 'jupyter', 'notebook',
        'pip', 'setuptools', 'wheel',
        # 排除其他不需要的模块
        'tkinter', 'turtle',
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
