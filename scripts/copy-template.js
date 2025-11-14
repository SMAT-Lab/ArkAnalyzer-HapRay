#!/usr/bin/env node
const path = require('path');
const { access, constants, mkdir, cp, stat } = require('fs/promises');

const ROOT_DIR = path.resolve(__dirname, '..');
const args = process.argv.slice(2);

if (args.length !== 2) {
  console.error('参数错误：请提供源路径和目标路径，例如 node build/copy-template.js <源> <目标>');
  process.exit(1);
}

const sourcePath = path.resolve(ROOT_DIR, args[0]);
const targetPath = path.resolve(ROOT_DIR, args[1]);

async function ensureSourceExists(filePath) {
  try {
    await access(filePath, constants.F_OK);
  } catch {
    throw new Error(`未找到源路径：${filePath}，请确认已生成该文件或目录。`);
  }
}

async function copyEntry(src, dest) {
  const srcStat = await stat(src);
  await mkdir(path.dirname(dest), { recursive: true });

  if (srcStat.isDirectory()) {
    await cp(src, dest, { recursive: true });
  } else {
    await cp(src, dest);
  }
}

async function main() {
  await ensureSourceExists(sourcePath);
  await copyEntry(sourcePath, targetPath);
  console.log(`已将 ${sourcePath} 复制到 ${targetPath}`);
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});