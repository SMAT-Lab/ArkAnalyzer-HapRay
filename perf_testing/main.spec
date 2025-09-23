# -*- mode: python ; coding: utf-8 -*-
import pkg_resources
import sys
import os
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
    ('hapray-toolbox', 'hapray-toolbox'),
    ('hapray-staticanalyzer', 'hapray-staticanalyzer'),
    ]
site_packages_dir = sys.path[-1]
for item in os.listdir(site_packages_dir):
    item_path = os.path.join(site_packages_dir, item)
    if os.path.isdir(item_path):
        datas.append((item_path, item))

a = Analysis(
    ['scripts/main.py'],
    pathex=['./'],
    binaries=[],
    datas=datas,
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
    a.binaries,
    a.datas,
    [],
    name='ArkAnalyzer-HapRay',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
