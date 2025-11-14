#!/bin/bash
# 压缩 onedir 模式的输出为 zip 文件

set -e

# 检查 dist/opt-detector 目录是否存在
if [ ! -d "dist/opt-detector" ]; then
    echo "错误: dist/opt-detector 目录不存在"
    echo "请先运行: npm run build:onedir (不包含压缩) 或 ONEDIR_MODE=true ./build_exe.sh"
    exit 1
fi

# 从 package.json 读取版本号
VERSION=$(node -p "require('./package.json').version" 2>/dev/null || grep -o '"version"[[:space:]]*:[[:space:]]*"[^"]*"' package.json | grep -o '[0-9.]\+' | head -1)

if [ -z "$VERSION" ]; then
    echo "警告: 无法从 package.json 读取版本号，使用默认版本号 1.0.0"
    VERSION="1.0.0"
fi

# 压缩文件名
ZIP_NAME="opt-detector-${VERSION}.zip"
ZIP_PATH="dist/${ZIP_NAME}"

echo "压缩 onedir 输出为 zip 文件..."
echo "源目录: dist/opt-detector"
echo "输出文件: ${ZIP_PATH}"

# 进入 dist 目录并压缩
cd dist

# 压缩 opt-detector 目录和 README.md
if command -v zip &> /dev/null; then
    # 压缩 opt-detector 目录
    zip -rq "${ZIP_NAME}" opt-detector
    
    # 如果 README.md 存在，添加到 zip 文件中（在zip根目录下）
    if [ -f "../README.md" ]; then
        # 使用 -j 选项去除路径，只保留文件名，使其在zip根目录
        (cd .. && zip -j dist/"${ZIP_NAME}" README.md -q) || zip "${ZIP_NAME}" ../README.md -j -q
        echo "已包含 README.md"
    fi
    
    echo ""
    echo "压缩完成！"
    ls -lh "${ZIP_NAME}"
    echo ""
    echo "文件大小:"
    du -sh "${ZIP_NAME}"
    echo ""
    echo "包含内容:"
    echo "  - opt-detector/ (可执行文件目录)"
    if [ -f "../README.md" ]; then
        echo "  - README.md (使用说明)"
    fi
    echo ""
    echo "使用命令:"
    echo "  解压: unzip ${ZIP_NAME}"
    echo "  运行: cd opt-detector && ./opt-detector --help"
    echo "  查看说明: cat README.md"
else
    echo "错误: 未找到 zip 命令"
    echo "macOS: 应该自带 zip 命令"
    echo "Linux: sudo apt-get install zip 或 sudo yum install zip"
    exit 1
fi

