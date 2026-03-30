/**
 * 将 hapray/testcases 目录「内部」的包名子目录与文件，直接放到 dist/tools/perf-testing/testcases/ 下。
 * 目标路径为：.../perf-testing/testcases/<各应用目录>/...
 * 不得出现 .../testcases/testcases/ 或 .../testcases/hapray/testcases/ 等重复嵌套。
 * （若用 fs.cpSync 整目录拷贝到同名 testcases 目标，Node 会在目标下再建一层 testcases，需避免。）
 */
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const perfTestingRoot = path.resolve(__dirname, "..");
const srcRoot = path.join(perfTestingRoot, "hapray", "testcases");
const destRoot = path.resolve(perfTestingRoot, "..", "dist", "tools", "perf-testing", "testcases");

/** 只复制 fromDir 下的子项到 toDir，不包含 fromDir 这一层目录名 */
function copyDirectoryContents(fromDir, toDir) {
  fs.mkdirSync(toDir, { recursive: true });
  for (const entry of fs.readdirSync(fromDir, { withFileTypes: true })) {
    const from = path.join(fromDir, entry.name);
    const to = path.join(toDir, entry.name);
    if (entry.isDirectory()) {
      copyDirectoryContents(from, to);
    } else {
      fs.copyFileSync(from, to);
    }
  }
}

function main() {
  if (!fs.existsSync(srcRoot)) {
    console.error(`[copy-testcases] 源目录不存在: ${srcRoot}`);
    process.exit(1);
  }
  if (fs.existsSync(destRoot)) {
    fs.rmSync(destRoot, { recursive: true, force: true });
  }
  copyDirectoryContents(srcRoot, destRoot);
  console.log(`✓ 已复制 hapray/testcases 内容 -> ${destRoot}`);
}

main();
