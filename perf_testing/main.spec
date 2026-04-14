# -*- mode: python ; coding: utf-8 -*-
import pkg_resources
import os
import sys
import sysconfig
from PyInstaller.utils.hooks import (
    collect_dynamic_libs,
    collect_submodules,
    collect_data_files,
    copy_metadata,
)

venv_packages = [pkg.key for pkg in pkg_resources.working_set]
venv_packages.append('ohos')
venv_packages.append('devicetest')
venv_packages.append('xdevice')
venv_packages.append('hypium')
venv_packages.append('yaml')
venv_packages.append('telnetlib')
venv_packages.append('xml.dom')
venv_packages.append('xml.etree.ElementTree')

# 添加 numpy 和 pandas 的隐藏导入
numpy_hidden_imports = [
    'numpy',
    'numpy.core',
    'numpy.core.multiarray',
    'numpy.core.umath',
    'numpy.linalg',
    'numpy.linalg.lapack_lite',
    'numpy.random',
    'numpy.fft'
]
pandas_hidden_imports = [
    'pandas',
    'pandas.core',
    'pandas.core.arrays',
    'pandas.core.dtypes',
    'pandas.io'
]

venv_packages.extend(numpy_hidden_imports)
venv_packages.extend(pandas_hidden_imports)

# xdevice 在包内用 sys.path +「from _core.xxx」导入，PyInstaller 无法静态解析，必须显式收集子模块
try:
    venv_packages.extend(collect_submodules('xdevice'))
except Exception as e:
    print(f"Warning: collect_submodules('xdevice') failed: {e}")

# entry_points 会加载 devicetest.driver.device_test 等，Analysis 不会自动打入 devicetest 包
try:
    venv_packages.extend(collect_submodules('devicetest'))
except Exception as e:
    print(f"Warning: collect_submodules('devicetest') failed: {e}")

# gui-agent：Open-AutoGLM phone_agent（PyPI: phone-agent）；构建前需 pip install phone-agent，否则此处仅告警
try:
    venv_packages.extend(collect_submodules('phone_agent'))
except Exception as e:
    print(f"Warning: collect_submodules('phone_agent') failed: {e}")

# ohos 不用 collect_submodules：遍历 ohos.parser 等子包时会在 spec 执行阶段 import 失败，导致漏打包。
# 改为在下方把整个 site-packages/ohos 目录作为 datas 打入（见 copy_metadata 之后）。

IS_WIN = sys.platform.startswith("win")  
IS_DARWIN = sys.platform == "darwin"  
# macOS：PyInstaller 对 Mach-O strip 后，再经 Developer ID 重签，公证常报 Python / Python.framework signature invalid  
STRIP_BINARIES = (not IS_WIN) and (not IS_DARWIN)  
_CODESIGN_IDENTITY = (os.environ.get("APPLE_SIGNING_IDENTITY", "").strip() or None) if IS_DARWIN else None

# 直接打包 resource 目录（含 web、xvm 等）
_resource_dir = os.path.join(os.path.dirname(SPEC), 'resource')
datas = [
    ('hapray', 'hapray'),
]
if os.path.isdir(_resource_dir):
    datas.append((_resource_dir, 'resource'))

# xdevice 的默认 user_config.xml、报表模板等位于 _core/resource（非 .py），须随包一起收集
try:
    datas += collect_data_files('xdevice')
except Exception as e:
    print(f"Warning: collect_data_files('xdevice') failed: {e}")

# hypium 含 dfx/privacy_policy.md 等运行时按路径读取的资源
try:
    datas += collect_data_files('hypium')
except Exception as e:
    print(f"Warning: collect_data_files('hypium') failed: {e}")

# devicetest 的 uitest_agent *.so 等在 res/prototype/native（非 .py）；仅 collect_submodules 不会打入，frozen 下会缺文件导致 hdc push 失败
try:
    datas += collect_data_files('devicetest')
except Exception as e:
    print(f"Warning: collect_data_files('devicetest') failed: {e}")

# xdevice 在启动时用 importlib.metadata.entry_points 加载 driver（如 DeviceTest→device_test）等插件；
# 未打入 .dist-info 时 frozen 环境找不到 entry_points，报「驱动插件未安装」
for _dist_name in ("xdevice", "xdevice-devicetest", "xdevice-ohos", "phone-agent"):
    try:
        datas += copy_metadata(_dist_name)
    except Exception as e:
        print(f"Warning: copy_metadata({_dist_name!r}) failed: {e}")

# 完整打入 xdevice-ohos 的 ohos 包（含 parser/drivers 等全部 .py）
_ohos_pkg = os.path.join(sysconfig.get_path("purelib"), "ohos")
if os.path.isdir(_ohos_pkg):
    datas.append((_ohos_pkg, "ohos"))
else:
    print("Warning: site-packages/ohos 不存在，无法整包收集 ohos")

# 初始化 binaries 列表
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

# phone_agent（如 xctest/screenshot）依赖 Pillow（import PIL）；动态库在 PIL/.dylibs
try:
    binaries.extend(collect_dynamic_libs('PIL'))
except Exception as e:
    print(f"Warning: Could not collect PIL/Pillow dynamic libs: {e}")

# 不再把整份 site-packages 目录作为 datas 全量拷贝：会与 Analysis 已收集的依赖重复，
# 在 x86_64 上尤其会把 numpy/pandas 等 wheel 再拷一份，体积可接近翻倍。
# 依赖关系由下方 Analysis + hiddenimports 与 PyInstaller hooks 解析即可。

IS_WIN = sys.platform.startswith('win')

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
        'matplotlib',
        'tkinter',
        'IPython',
        'jupyter',
        'notebook',
        'pytest',
        'numpy.tests',
        'pandas.tests',
        'scipy.tests',
        'sklearn.tests',
    ],
    noarchive=False,
    # 不可使用 optimize=2（-OO）：会去掉 docstring，numpy 的 add_docstring 在运行时报 TypeError
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
    # Windows：不 strip PE/DLL；macOS：不 strip Mach-O（见 STRIP_BINARIES）；Linux 可 strip 减小体积
    strip=STRIP_BINARIES,
    upx=False,  # 禁用 UPX（Windows DLL / macOS Mach-O 与重签、公证）
    upx_exclude=[],
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=_CODESIGN_IDENTITY,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=STRIP_BINARIES,
    upx=False,  # 禁用 UPX（Windows DLL / macOS Mach-O 与重签、公证）
    upx_exclude=[],
    name='perf-testing',
)
