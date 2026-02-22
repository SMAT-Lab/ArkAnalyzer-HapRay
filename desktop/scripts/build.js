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

function main() {
  if (process.platform === "darwin") {
    // macOS: app -> merge -> dmg，确保 dmg 包含 merge 后的内容
    console.log("Step 1: 构建 .app bundle...");
    run("node", [runWithCargo, "npx", "tauri", "build", "--bundles", "app"]);

    console.log("\nStep 2: 对 bundle 内 tools 做硬链接合并...");
    run("node", [mergeScript]);

    console.log("\nStep 3: 生成 .dmg...");
    if (!fs.existsSync(bundleDmgSh)) {
      // 首次构建：tauri bundle 会创建 dmg 目录和 bundle_dmg.sh
      console.log("bundle_dmg.sh 不存在，先运行 tauri bundle 以创建 dmg 工具...");
      run("node", [runWithCargo, "npx", "tauri", "bundle", "--bundles", "dmg"]);
      // 此时 dmg 已生成但包含未 merge 的 .app，需重新 merge 后覆盖
      console.log("\n重新执行 merge...");
      run("node", [mergeScript]);
    }
    createDmgWithBundleScript();
  } else {
    // 其他平台：保持原有流程
    console.log("构建应用...");
    run("node", [runWithCargo, "npx", "tauri", "build"]);

    console.log("\n对 bundle 内 tools 做硬链接合并...");
    run("node", [mergeScript]);
  }
}

main();
