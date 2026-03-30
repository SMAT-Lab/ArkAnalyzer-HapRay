#!/usr/bin/env node
/**
 * 将仓库根目录 dist/tools 同步到 desktop/src-tauri/tools（供 Tauri 打包嵌入）。
 * 使用相对脚本位置的路径，在 Windows / Unix 上均可运行。
 */
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const desktopRoot = path.resolve(__dirname, "..");
const srcTools = path.resolve(desktopRoot, "../dist/tools");
const destTools = path.join(desktopRoot, "src-tauri", "tools");

function copyDirSync(src, dest) {
  fs.mkdirSync(dest, { recursive: true });
  for (const entry of fs.readdirSync(src, { withFileTypes: true })) {
    const srcPath = path.join(src, entry.name);
    const destPath = path.join(dest, entry.name);
    if (entry.isSymbolicLink()) {
      const target = fs.readlinkSync(srcPath);
      fs.symlinkSync(target, destPath);
    } else if (entry.isDirectory()) {
      copyDirSync(srcPath, destPath);
    } else {
      fs.copyFileSync(srcPath, destPath);
    }
  }
}

function main() {
  if (!fs.existsSync(srcTools)) {
    console.error(`错误: 未找到工具目录，请先完成仓库根目录的构建以生成 dist/tools。\n  期望路径: ${srcTools}`);
    process.exit(1);
  }
  if (fs.existsSync(destTools)) {
    fs.rmSync(destTools, { recursive: true, force: true });
  }
  copyDirSync(srcTools, destTools);
  console.log(`✓ 已同步 dist/tools -> src-tauri/tools`);
}

main();
