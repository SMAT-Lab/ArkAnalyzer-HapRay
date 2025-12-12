#!/bin/bash

# macOS 隔离属性移除脚本
# 用于移除当前目录下所有文件的隔离属性
#
# 使用方法:
#   ./run_macos.sh

set -e

# 获取脚本所在目录（即 dist 目录）
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 检查是否为 macOS
if [[ "$OSTYPE" != "darwin"* ]]; then
    echo "错误: 此脚本仅适用于 macOS"
    exit 1
fi

echo "=========================================="
echo "macOS 隔离属性移除脚本"
echo "=========================================="
echo "当前目录: $SCRIPT_DIR"
echo ""

# 移除当前目录的隔离属性
echo "正在移除隔离属性..."
if sudo xattr -r -d com.apple.quarantine "$SCRIPT_DIR" 2>/dev/null; then
    echo "✓ 隔离属性已移除"
    echo ""
    echo "✓ 处理完成"
else
    echo "警告: 移除隔离属性失败，可能需要管理员权限"
    echo "请手动执行: sudo xattr -r -d com.apple.quarantine $SCRIPT_DIR"
    exit 1
fi
