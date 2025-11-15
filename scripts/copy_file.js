#!/usr/bin/env node
const fs = require("fs");
const path = require("path");

/**
 * 复制文件函数
 * @param {string} src - 源文件路径（相对于仓库根目录或绝对路径）
 * @param {string} dest - 目标文件路径（相对于仓库根目录或绝对路径）
 * @param {string} repoRoot - 仓库根目录，默认为当前脚本所在目录的上一级
 * @returns {boolean} 是否复制成功
 */
function copyFile(src, dest, repoRoot = path.resolve(__dirname, "..")) {
  const srcPath = path.isAbsolute(src) ? src : path.resolve(repoRoot, src);
  const destPath = path.isAbsolute(dest) ? dest : path.resolve(repoRoot, dest);
  const destDir = path.dirname(destPath);

  if (!fs.existsSync(srcPath)) {
    console.error(`Source file not found: ${srcPath}`);
    return false;
  }

  try {
    fs.mkdirSync(destDir, { recursive: true });
    fs.copyFileSync(srcPath, destPath);
    console.log(`Copied ${srcPath} -> ${destPath}`);
    return true;
  } catch (error) {
    console.error(`Failed to copy file: ${error.message}`);
    return false;
  }
}

// 如果作为脚本直接运行，则执行命令行接口
if (require.main === module) {
  const [,, srcArg, destArg] = process.argv;

  if (!srcArg || !destArg) {
    console.error("Usage: node scripts/copy_file.js <src> <dest>");
    process.exit(1);
  }

  const success = copyFile(srcArg, destArg);
  process.exit(success ? 0 : 1);
}

module.exports = copyFile;