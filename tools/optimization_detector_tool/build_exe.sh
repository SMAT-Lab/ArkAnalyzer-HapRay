#!/bin/bash
# 构建优化检测器可执行文件

set -e

echo "构建 optimization-detector 可执行文件..."

# 检查 Python 命令
if command -v python3 &> /dev/null; then
    PYTHON_CMD=python3
elif command -v python &> /dev/null; then
    PYTHON_CMD=python
else
    echo "错误: 未找到 Python 命令"
    exit 1
fi

echo "使用 Python: $($PYTHON_CMD --version)"

# 检查并安装依赖
echo "检查项目依赖..."
if ! $PYTHON_CMD -c "import pandas, numpy, tensorflow" 2>/dev/null; then
    echo "安装项目依赖..."
    $PYTHON_CMD -m pip install --quiet -e . || $PYTHON_CMD -m pip install --quiet numpy pandas tensorflow tqdm pyelftools arpy joblib
fi

# 检查并安装 PyInstaller
echo "检查 PyInstaller..."
if ! $PYTHON_CMD -m pip list 2>/dev/null | grep -q "^pyinstaller "; then
    echo "安装 PyInstaller..."
    $PYTHON_CMD -m pip install --quiet pyinstaller
fi

# 清理旧的构建文件（保留 spec 文件）
echo "清理旧的构建文件..."
rm -rf build/ dist/ *.egg-info

# 创建构建目录
BUILD_DIR="build_exe"
rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"

# 使用 PyInstaller 打包
echo "开始打包可执行文件..."
echo "注意: 由于包含 TensorFlow，打包可能需要较长时间（可能需要10-30分钟）..."

# 检查是否使用目录模式（更快启动，但文件分散）
ONEDIR_MODE=${ONEDIR_MODE:-false}
if [ "$ONEDIR_MODE" = "true" ]; then
    echo "使用目录模式（onedir）打包（启动更快）..."
    SPEC_FILE="optimization_detector_onedir.spec"
    EXE_NAME="opt-detector/opt-detector"
else
    echo "使用单文件模式（onefile）打包..."
    echo "注意: 生成的可执行文件会比较大（可能超过500MB）..."
    SPEC_FILE="optimization_detector.spec"
    EXE_NAME="opt-detector"
fi

# 使用 spec 文件打包（如果存在）
if [ -f "$SPEC_FILE" ]; then
    echo "使用 spec 文件打包: $SPEC_FILE"
    $PYTHON_CMD -m PyInstaller "$SPEC_FILE" --clean --noconfirm
elif [ -f "optimization_detector.spec" ]; then
    echo "使用默认 spec 文件打包..."
    $PYTHON_CMD -m PyInstaller optimization_detector.spec --clean --noconfirm
else
    # 动态创建打包命令
    $PYTHON_CMD -m PyInstaller \
        --name="opt-detector" \
        --onefile \
        --console \
        --add-data="optimization_detector/models:optimization_detector/models" \
        --hidden-import="optimization_detector" \
        --hidden-import="optimization_detector.file_info" \
        --hidden-import="optimization_detector.optimization_detector" \
        --hidden-import="optimization_detector.lto_detector" \
        --hidden-import="tensorflow" \
        --hidden-import="tensorflow.keras" \
        --hidden-import="numpy" \
        --hidden-import="pandas" \
        --hidden-import="tqdm" \
        --hidden-import="elftools" \
        --hidden-import="arpy" \
        --hidden-import="joblib" \
        --hidden-import="sklearn" \
        --collect-all="tensorflow" \
        --collect-all="numpy" \
        --exclude-module="matplotlib" \
        --exclude-module="PIL" \
        --exclude-module="tkinter" \
        --noconfirm \
        --clean \
        optimization_detector/cli.py
fi

# 将产物同步到仓库根目录的 dist/tools
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$PROJECT_DIR/../.." && pwd)"
ROOT_DIST_DIR="$ROOT_DIR/dist/tools"
TARGET_DIR="$ROOT_DIST_DIR/opt_detector"

echo ""
echo "同步构建产物到: $TARGET_DIR"
if [ -d "dist/opt-detector" ]; then
    mkdir -p "$ROOT_DIST_DIR"
    rm -rf "$TARGET_DIR"
    cp -R "dist/opt-detector" "$TARGET_DIR"
    echo "✓ 目录模式产物已同步到根目录 dist/tools"
else
    echo "⚠ 未找到 dist/opt-detector*，无法同步到根目录"
fi

echo ""
echo "构建完成！"
echo "本地可执行文件位置:"
if [ "$ONEDIR_MODE" = "true" ]; then
    ls -lh dist/opt-detector/opt-detector 2>/dev/null || ls -lh dist/opt-detector/ 2>/dev/null || ls -lh dist/
else
    ls -lh dist/opt-detector* 2>/dev/null || ls -lh dist/
fi

