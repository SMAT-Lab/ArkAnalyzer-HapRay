#!/bin/bash

# macOS 代码签名脚本
# 用于签名 dist 目录中的所有二进制文件（.so, .dylib, 可执行文件）
#
# 签名方式：Ad-hoc 签名（临时签名，使用 --sign -）
# - 优点：不需要 Apple 开发者证书，可以免费使用
# - 限制：无法通过 Gatekeeper 验证，用户首次运行可能需要手动允许
# - 适用场景：内部使用、开源项目、本地分发
#
# 如果需要正式签名（需要开发者证书）：
# 1. 将 --sign - 改为 --sign "Developer ID Application: Your Name (TEAM_ID)"
# 2. 添加 --timestamp 选项（需要网络连接）
# 3. 使用 notarytool 进行公证（需要 Apple 开发者账号）

set -e

# 获取 dist 目录路径，如果没有提供则使用相对路径
DIST_DIR="${1:-../dist}"

# 如果提供的是相对路径，转换为绝对路径（基于脚本所在目录）
if [[ "$DIST_DIR" != /* ]]; then
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    DIST_DIR="$SCRIPT_DIR/$DIST_DIR"
fi

if [[ "$OSTYPE" != "darwin"* ]]; then
    echo "此脚本仅适用于 macOS"
    exit 0
fi

if [ ! -d "$DIST_DIR" ]; then
    echo "错误: 目录不存在: $DIST_DIR"
    exit 1
fi

echo "开始签名二进制文件..."

# 签名函数：先签名依赖项，再签名主文件
sign_file() {
    local file="$1"
    if [ ! -f "$file" ]; then
        return
    fi
    
    # 检查是否为 Mach-O 二进制文件
    if ! file "$file" 2>/dev/null | grep -q "Mach-O"; then
        return
    fi
    
    # 先签名所有依赖的库（如果有的话）
    # 对于 .so 和 .dylib 文件，直接签名
    # 对于可执行文件，使用 --deep 选项会自动签名嵌入的库
    
    if [[ "$file" == *.so ]] || [[ "$file" == *.dylib ]]; then
        echo "签名库文件: $file"
        codesign --sign - --force --timestamp=none "$file" 2>/dev/null || {
            echo "警告: 签名失败: $file"
        }
    else
        echo "签名可执行文件: $file"
        codesign --sign - --force --deep --timestamp=none "$file" 2>/dev/null || {
            echo "警告: 签名失败: $file"
        }
    fi
}

# 1. 先签名所有 .so 和 .dylib 文件
find "$DIST_DIR" -type f \( -name "*.so" -o -name "*.dylib" \) | while read -r file; do
    sign_file "$file"
done

# 2. 签名 Python3.framework（如果存在）
if [ -d "$DIST_DIR/_internal/Python3.framework" ]; then
    echo "签名 Python3.framework..."
    codesign --sign - --force --deep --timestamp=none "$DIST_DIR/_internal/Python3.framework" 2>/dev/null || {
        echo "警告: Python3.framework 签名失败"
    }
fi

# 3. 签名所有可执行文件（递归查找整个 dist 目录）
# 使用 file 命令检查 Mach-O 类型，而不是依赖文件权限，因为某些文件可能没有设置执行权限
find "$DIST_DIR" -type f ! -name "*.py" ! -name "*.pyc" ! -name "*.pyo" ! -name "*.json" ! -name "*.txt" ! -name "*.md" ! -name "*.log" ! -name "*.zip" ! -name "*.DS_Store" ! -path "*/Python3.framework/*" 2>/dev/null | while read -r file; do
    # 检查是否为 Mach-O 可执行文件（排除已签名的库文件）
    if file "$file" 2>/dev/null | grep -q "Mach-O" && [[ "$file" != *.so ]] && [[ "$file" != *.dylib ]]; then
        sign_file "$file"
    fi
done

# 4. 移除隔离属性（quarantine）
echo "移除隔离属性..."
xattr -cr "$DIST_DIR" 2>/dev/null || {
    echo "警告: 移除隔离属性失败"
}

echo "签名完成!"

