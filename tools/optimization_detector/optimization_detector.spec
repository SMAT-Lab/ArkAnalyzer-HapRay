# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all
import os
import platform
from pathlib import Path

# 获取项目根目录
project_root = Path(SPECPATH)
models_path = project_root / 'optimization_detector' / 'models'

# 收集模型文件
datas = []
if models_path.exists():
    datas.append((str(models_path), 'optimization_detector/models'))

binaries = []

# 项目自身模块
hiddenimports = [
    'optimization_detector',
    'optimization_detector.cli',
    'optimization_detector.file_info',
    'optimization_detector.invoke_symbols',
    'optimization_detector.lto_detector',
    'optimization_detector.lto_feature_pipeline',
    'optimization_detector.optimization_detector',
    'optimization_detector.excel_utils',
    # TensorFlow 相关模块
    'tensorflow',
    'tensorflow.keras',
    'tensorflow.keras.models',
    'tensorflow.python.keras.api._v2.keras',
    'tensorflow.python.keras.api._v2.keras.models',
]

# 显式收集 numpy（pandas 的依赖）
tmp_ret = collect_all('numpy')
datas += tmp_ret[0]
binaries += tmp_ret[1]
hiddenimports += tmp_ret[2]
# 添加 numpy 的关键隐藏导入
hiddenimports += [
    'numpy.core._multiarray_umath',
    'numpy.core._multiarray_tests',
    'numpy.linalg._umath_linalg',
    'numpy.fft._pocketfft_internal',
    'numpy.random._common',
    'numpy.random._bounded_integers',
    'numpy.random._mt19937',
    'numpy.random._philox',
    'numpy.random._pcg64',
    'numpy.random._sfc64',
    'numpy.random._generator',
]

# 收集 pandas
tmp_ret = collect_all('pandas')
datas += tmp_ret[0]
binaries += tmp_ret[1]
hiddenimports += tmp_ret[2]

# 收集其他依赖
# 收集 tensorflow-macos 和 tensorflow-metal (macOS 特定)
if platform.system() == 'Darwin':
    # 收集 tensorflow-macos
    tmp_ret = collect_all('tensorflow_macos')
    datas += tmp_ret[0]
    binaries += tmp_ret[1]
    hiddenimports += tmp_ret[2]
    
    # 收集 tensorflow-metal
    tmp_ret = collect_all('tensorflow_metal')
    datas += tmp_ret[0]
    binaries += tmp_ret[1]
    hiddenimports += tmp_ret[2]
    
    # 添加 tensorflow-metal 的关键隐藏导入
    hiddenimports += [
        'tensorflow_metal',
        'tensorflow_metal.python',
        'tensorflow_metal.python.gpu',
        'tensorflow_metal.python.gpu.device',
    ]
else:
    tmp_ret = collect_all('tensorflow')
    datas += tmp_ret[0]
    binaries += tmp_ret[1]
    hiddenimports += tmp_ret[2]


tmp_ret = collect_all('arpy')
datas += tmp_ret[0]
binaries += tmp_ret[1]
hiddenimports += tmp_ret[2]

tmp_ret = collect_all('joblib')
datas += tmp_ret[0]
binaries += tmp_ret[1]
hiddenimports += tmp_ret[2]

# 不再收集 pkg_resources（已弃用，使用 importlib.metadata 和 importlib.resources 替代）
# 如果某些依赖需要 pkg_resources，PyInstaller 会自动处理

# 收集 scipy - sklearn 的依赖
tmp_ret = collect_all('scipy')
datas += tmp_ret[0]
binaries += tmp_ret[1]
hiddenimports += tmp_ret[2]
# 添加 scipy 的关键隐藏导入（特别是 Cython 扩展模块）
hiddenimports += [
    'scipy._cyutility',  # 关键：Cython 工具模块
    'scipy._lib',
    'scipy._lib._ccallback',
    'scipy._lib._testutils',
    'scipy.sparse',  # sklearn 需要
    'scipy.sparse._csparsetools',  # Cython 扩展
    'scipy.sparse._lil',
    'scipy.sparse._csr',
    'scipy.sparse._csc',
    'scipy.sparse._coo',
    'scipy.sparse._base',
    'scipy.sparse._sputils',
    'scipy.linalg',
    'scipy.linalg._flinalg',
    'scipy.special',
]

# 收集 sklearn (scikit-learn) - LTO 检测器需要
tmp_ret = collect_all('sklearn')
datas += tmp_ret[0]
binaries += tmp_ret[1]
hiddenimports += tmp_ret[2]
# 添加 sklearn 的关键隐藏导入
hiddenimports += [
    'sklearn.ensemble',
    'sklearn.ensemble._forest',
    'sklearn.ensemble._gradient_boosting',
    'sklearn.ensemble._base',
    'sklearn.linear_model',
    'sklearn.linear_model._logistic',
    'sklearn.linear_model._base',
    'sklearn.svm',
    'sklearn.svm._libsvm',
    'sklearn.svm._base',
    'sklearn.neural_network',
    'sklearn.neural_network._multilayer_perceptron',
    'sklearn.preprocessing',
    'sklearn.preprocessing._data',
    'sklearn.feature_selection',
    'sklearn.feature_selection._univariate_selection',
    'sklearn.metrics',
    'sklearn.metrics._ranking',
    'sklearn.model_selection',
    'sklearn.model_selection._split',
    'sklearn.model_selection._search',
    'sklearn.utils',
    'sklearn.utils._param_validation',
    'sklearn.utils.validation',
    'sklearn.utils.multiclass',
    'sklearn.utils.extmath',
    'sklearn._loss',
    'sklearn.tree',
    'sklearn.tree._tree',
    'sklearn.tree._classes',
]

runtime_hooks = []

a = Analysis(
    ['cli.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=runtime_hooks,
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
        'numpy.tests',
        'pandas.tests',
        'pkg_resources',  # 排除已弃用的 pkg_resources，使用 importlib.metadata 和 importlib.resources 替代
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
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
    runtime_tmpdir=None,
    append_pkg=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='opt-detector',
)
