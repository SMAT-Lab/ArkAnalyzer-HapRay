#!/bin/bash
# 构建优化检测器工具包

set -e

echo "构建 optimization-detector 工具包..."

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

# 检查并安装构建工具
echo "检查构建工具..."
if ! $PYTHON_CMD -m pip list 2>/dev/null | grep -q "^build "; then
    echo "安装构建工具..."
    $PYTHON_CMD -m pip install --quiet build wheel
fi

# 清理旧的构建文件
echo "清理旧的构建文件..."
rm -rf build/ dist/ *.egg-info

# 构建包
echo "开始构建包..."
$PYTHON_CMD -m build

echo ""
echo "构建完成！"
echo "安装包位置:"
ls -lh dist/
echo ""
echo "安装命令:"
echo "  pip install dist/optimization_detector-*.whl"
echo ""
echo "或安装为开发版本:"
echo "  pip install -e ."

