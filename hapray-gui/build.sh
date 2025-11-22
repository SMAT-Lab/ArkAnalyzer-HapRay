#!/bin/bash
# HapRay GUI 打包脚本
# 包含后处理步骤：共享 Python 运行时

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
DIST_DIR="$ROOT_DIR/dist"

echo "=========================================="
echo "HapRay GUI 打包脚本"
echo "=========================================="
echo "项目根目录: $ROOT_DIR"
echo "输出目录: $DIST_DIR"
echo ""

# 检查虚拟环境
if [ -d "$SCRIPT_DIR/.venv" ]; then
    PYINSTALLER="$SCRIPT_DIR/.venv/bin/pyinstaller"
elif [ -d "$SCRIPT_DIR/venv" ]; then
    PYINSTALLER="$SCRIPT_DIR/venv/bin/pyinstaller"
else
    PYINSTALLER="pyinstaller"
fi

echo "使用 PyInstaller: $PYINSTALLER"
echo ""

# 进入 hapray-gui 目录
cd "$SCRIPT_DIR"

# 打包 GUI
echo "正在打包 GUI..."
$PYINSTALLER -y main.spec

# 移动可执行文件到根目录的 dist
GUI_BUILD_DIR="$SCRIPT_DIR/dist/hapray-gui"
GUI_EXE="$GUI_BUILD_DIR/HapRay-GUI"
ROOT_DIST_GUI="$DIST_DIR/HapRay-GUI"

if [ -f "$GUI_EXE" ] || [ -d "$GUI_EXE" ]; then
    echo ""
    echo "移动 GUI 可执行文件到根目录 dist..."
    mkdir -p "$DIST_DIR"
    if [ -e "$ROOT_DIST_GUI" ]; then
        rm -rf "$ROOT_DIST_GUI"
    fi
    mv "$GUI_EXE" "$ROOT_DIST_GUI"
    echo "✓ 已移动: $ROOT_DIST_GUI"
else
    echo "警告: 未找到 GUI 可执行文件: $GUI_EXE"
fi

# 打包 CMD
echo ""
echo "正在打包 CMD..."
$PYINSTALLER -y cmd.spec

# 移动可执行文件到根目录的 dist
CMD_BUILD_DIR="$SCRIPT_DIR/dist/hapray-cmd"
CMD_EXE="$CMD_BUILD_DIR/hapray-cmd"
ROOT_DIST_CMD="$DIST_DIR/hapray-cmd"

if [ -f "$CMD_EXE" ] || [ -d "$CMD_EXE" ]; then
    echo ""
    echo "移动 CMD 可执行文件到根目录 dist..."
    mkdir -p "$DIST_DIR"
    if [ -e "$ROOT_DIST_CMD" ]; then
        rm -rf "$ROOT_DIST_CMD"
    fi
    mv "$CMD_EXE" "$ROOT_DIST_CMD"
    echo "✓ 已移动: $ROOT_DIST_CMD"
else
    echo "警告: 未找到 CMD 可执行文件: $CMD_EXE"
fi

# 运行后处理脚本：共享 Python 运行时
echo ""
echo "正在共享 Python 运行时..."
PYTHON_CMD="python3"
if [ -d "$SCRIPT_DIR/.venv" ]; then
    PYTHON_CMD="$SCRIPT_DIR/.venv/bin/python"
elif [ -d "$SCRIPT_DIR/venv" ]; then
    PYTHON_CMD="$SCRIPT_DIR/venv/bin/python"
fi

$PYTHON_CMD "$SCRIPT_DIR/share_python_runtime.py" "$DIST_DIR"

echo ""
echo "=========================================="
echo "✓ 打包完成！"
echo "=========================================="
echo "GUI 位置: $ROOT_DIST_GUI"
echo "CMD 位置: $ROOT_DIST_CMD"
echo "工具目录: $DIST_DIR/tools"
echo "共享 Python 运行时: $DIST_DIR/_shared_python/Python3.framework"
echo ""

