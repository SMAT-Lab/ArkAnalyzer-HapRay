# -*- mode: python ; coding: utf-8 -*-
import pkg_resources
venv_packages = [pkg.key for pkg in pkg_resources.working_set]
venv_packages.append('ohos')
venv_packages.append('devicetest')
venv_packages.append('xdevice')
venv_packages.append('hypium')

a = Analysis(
    ['scripts\\main.py'],
    binaries=[],
    datas=[
        ('.venv\\Lib\\site-packages\\xdevice', 'xdevice'),
        ('.venv\\Lib\\site-packages\\devicetest', 'devicetest'),
        ('.venv\\Lib\\site-packages\\hypium', 'hypium'),
        ('.venv\\Lib\\site-packages\\ohos', 'ohos'),
        ('hapray', 'hapray')
    ],
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
    name='main',
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
