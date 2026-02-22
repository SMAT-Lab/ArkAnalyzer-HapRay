#!/usr/bin/env node
/**
 * 构建脚本：在 macOS 上先构建 .app -> merge-bundle-resources -> 再生成 .dmg
 * 确保 .dmg 包含 merge 后的 Resources/tools 硬链接去重结果
 *
 * 注意：tauri bundle --bundles dmg 会重新创建 .app 并覆盖 merge 结果，
 * 因此必须 merge 后直接调用 bundle_dmg.sh 生成 dmg，而非使用 tauri bundle。
 */
import { spawnSync } from "child_process";
import path from "path";
import fs from "fs";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const runWithCargo = path.resolve(__dirname, "run-with-cargo.js");
const mergeScript = path.resolve(__dirname, "merge-bundle-resources.js");
const bundleBase = path.resolve(__dirname, "../src-tauri/target/release/bundle");
const macosDir = path.join(bundleBase, "macos");
const dmgDir = path.join(bundleBase, "dmg");
const bundleDmgSh = path.join(dmgDir, "bundle_dmg.sh");
// 项目根目录的 dist（desktop 的祖父目录）
const rootDistDir = path.resolve(__dirname, "../../dist");

function run(cmd, args = [], options = {}) {
  const result = spawnSync(cmd, args, {
    stdio: "inherit",
    cwd: path.resolve(__dirname, ".."),
    ...options,
  });
  if (result.status !== 0) {
    process.exit(result.status ?? 1);
  }
}

function createDmgWithBundleScript() {
  // 读取 tauri 配置
  const tauriConfPath = path.resolve(__dirname, "../src-tauri/tauri.conf.json");
  const tauriConf = JSON.parse(fs.readFileSync(tauriConfPath, "utf-8"));
  const productName = tauriConf.productName || "ArkAnalyzer-HapRay";
  const version = tauriConf.version || "1.5.0";
  const arch = process.arch === "arm64" ? "aarch64" : "x86_64";
  const dmgName = `${productName}_${version}_${arch}.dmg`;
  const dmgPath = path.join(dmgDir, dmgName);
  const appName = `${productName}.app`;
  const appPath = path.join(macosDir, appName);

  if (!fs.existsSync(appPath)) {
    console.error(`错误: 未找到 .app: ${appPath}`);
    process.exit(1);
  }

  // 使用与 tauri 相同的 dmg 配置（参考 bundle.macOS.dmg 默认值）
  const args = [
    "--skip-jenkins", // CI/无 GUI 环境跳过 AppleScript
    "--window-size", "660", "400",
    "--icon", appName, "180", "170",
    "--app-drop-link", "480", "170",
    "--volicon", path.join(dmgDir, "icon.icns"),
    dmgPath,
    macosDir,
  ];

  if (!fs.existsSync(path.join(dmgDir, "icon.icns"))) {
    args.splice(args.indexOf("--volicon"), 2); // 移除 volicon 参数
  }

  // hdiutil convert 不会覆盖已存在文件，需先删除
  if (fs.existsSync(dmgPath)) {
    fs.unlinkSync(dmgPath);
  }

  console.log("正在调用 bundle_dmg.sh 生成 .dmg...");
  run("bash", [bundleDmgSh, ...args], {
    env: { ...process.env, CI: "1" },
  });
}

/**
 * 将 desktop 构建产物复制到项目根目录 ./dist，供 e2e 测试和 release 使用
 * 结构: dist/ArkAnalyzer-HapRay.app/, dist/ArkAnalyzer-HapRay -> .app/Contents/MacOS/ArkAnalyzer-HapRay, dist/tools/
 */
function copyToDist() {
  const tauriConf = JSON.parse(fs.readFileSync(path.resolve(__dirname, "../src-tauri/tauri.conf.json"), "utf-8"));
  const productName = tauriConf.productName || "ArkAnalyzer-HapRay";
  const appName = `${productName}.app`;
  const appPath = path.join(macosDir, appName);
  const exeInApp = path.join(appPath, "Contents", "MacOS", "ArkAnalyzer-HapRay");
  const toolsInApp = path.join(appPath, "Contents", "Resources", "tools");

  if (!fs.existsSync(appPath) || !fs.existsSync(exeInApp)) {
    console.warn("跳过 copyToDist: .app 或可执行文件不存在");
    return;
  }

  fs.mkdirSync(rootDistDir, { recursive: true });

  const distAppPath = path.join(rootDistDir, appName);
  const distExePath = path.join(rootDistDir, productName);
  const distToolsPath = path.join(rootDistDir, "tools");

  if (fs.existsSync(distAppPath)) {
    fs.rmSync(distAppPath, { recursive: true });
  }
  copyDirSync(appPath, distAppPath);

  if (fs.existsSync(distExePath)) {
    fs.unlinkSync(distExePath);
  }
  fs.symlinkSync(path.join(appName, "Contents", "MacOS", "ArkAnalyzer-HapRay"), distExePath, "file");

  if (fs.existsSync(toolsInApp)) {
    if (fs.existsSync(distToolsPath)) {
      fs.rmSync(distToolsPath, { recursive: true });
    }
    copyDirSync(toolsInApp, distToolsPath);
  }

  console.log(`✓ 构建产物已复制到 ${rootDistDir}`);
}

function copyDirSync(src, dest) {
  fs.mkdirSync(dest, { recursive: true });
  for (const entry of fs.readdirSync(src, { withFileTypes: true })) {
    const srcPath = path.join(src, entry.name);
    const destPath = path.join(dest, entry.name);
    if (entry.isDirectory()) {
      copyDirSync(srcPath, destPath);
    } else {
      fs.copyFileSync(srcPath, destPath);
    }
  }
}

function main() {
  if (process.platform === "darwin") {
    // macOS: app -> merge -> dmg，确保 dmg 包含 merge 后的内容
    console.log("Step 1: 构建 .app bundle...");
    run("node", [runWithCargo, "npx", "tauri", "build", "--bundles", "app"]);

    console.log("\nStep 2: 对 bundle 内 tools 做硬链接合并...");
    run("node", [mergeScript]);

    console.log("\nStep 3: 生成 .dmg...");
    if (!fs.existsSync(bundleDmgSh)) {
      // 首次构建：tauri bundle 会创建 dmg 目录和 bundle_dmg.sh，但会清理 .app
      console.log("bundle_dmg.sh 不存在，先运行 tauri bundle 以创建 dmg 工具...");
      run("node", [runWithCargo, "npx", "tauri", "bundle", "--bundles", "dmg"]);
      // tauri bundle 会清理 .app，需重新构建 .app 才能继续
      console.log("\n重新构建 .app（tauri bundle 已清理）...");
      run("node", [runWithCargo, "npx", "tauri", "build", "--bundles", "app"]);
      console.log("\n重新执行 merge...");
      run("node", [mergeScript]);
    }
    createDmgWithBundleScript();
    console.log("\nStep 4: 复制产物到 ./dist...");
    copyToDist();
  } else {
    // 其他平台：保持原有流程
    console.log("构建应用...");
    run("node", [runWithCargo, "npx", "tauri", "build"]);

    console.log("\n对 bundle 内 tools 做硬链接合并...");
    run("node", [mergeScript]);

    console.log("\n复制产物到 ./dist...");
    copyToDist();
  }
}

main();
