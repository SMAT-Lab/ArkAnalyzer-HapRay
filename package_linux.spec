# -*- mode: python ; coding: utf-8 -*-

import pkg_resources
import os
import sys

# 获取当前 Python 解释器的版本，用于构建 site-packages 路径
# 例如： 'python3.8', 'python3.9'
python_version_slug = f"python{sys.version_info.major}.{sys.version_info.minor}"

# 虚拟环境的 site-packages 基础路径
# 假设 .venv 目录与 spec 文件在同一级或 PyInstaller 从项目根目录运行
# 如果 .venv 目录不在当前工作目录，你可能需要调整这个路径
# 或者使用更动态的方式来定位 site-packages
venv_site_packages_base = os.path.join('.venv', 'lib', python_version_slug, 'site-packages')

# 动态获取虚拟环境中的包，用于 hiddenimports
try:
    venv_packages = [pkg.key for pkg in pkg_resources.working_set]
except Exception as e:
    print(f"Warning: Could not retrieve packages from pkg_resources.working_set: {e}")
    print("Falling back to an empty list for venv_packages. Ensure hiddenimports are correctly specified if needed.")
    venv_packages = []

# 手动添加的包，确保它们在 hiddenimports 中
# 这些通常是 PyInstaller 静态分析可能遗漏的，或者是动态导入的
additional_hidden_imports = ['ohos', 'devicetest', 'xdevice', 'hypium']
for pkg_name in additional_hidden_imports:
    if pkg_name not in venv_packages:
        venv_packages.append(pkg_name)

# 构建 datas 列表
# (源路径, 打包后在应用内的目标路径)
datas_list = [
    (os.path.join(venv_site_packages_base, 'xdevice'), 'xdevice'),
    (os.path.join(venv_site_packages_base, 'devicetest'), 'devicetest'),
    (os.path.join(venv_site_packages_base, 'hypium'), 'hypium'),
    (os.path.join(venv_site_packages_base, 'ohos'), 'ohos'),
    ('hapray', 'hapray') # 假设 'hapray' 是一个与 spec 文件同级的目录
]

# 检查 datas 中的源路径是否存在
for src_path, _ in datas_list:
    if not os.path.exists(src_path):
        print(f"WARNING: Data source path does not exist: {src_path}")
        print(f"         Check your virtual environment structure and the path: {venv_site_packages_base}")
        print(f"         Ensure packages like 'xdevice', 'devicetest', etc., are installed in:")
        print(f"         {os.path.abspath(venv_site_packages_base)}")


a = Analysis(
    [os.path.join('scripts', 'main.py')], # 使用 os.path.join 保证路径正确
    binaries=[],
    datas=datas_list,
    hiddenimports=venv_packages,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='main', # 在 Linux 上会生成名为 'main' 的可执行文件
    debug=True,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
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
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='main',
)