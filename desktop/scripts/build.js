#!/usr/bin/env node
/**
 * macOS：tauri build --no-bundle 编译产物 → tauri bundle --bundles app,dmg 一次打出 .app 与 .dmg
 * → 再将 dmg 卷内 .app 拷入项目根 dist（本地测试）。
 */
import { spawnSync } from "child_process";
import path from "path";
import fs from "fs";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const desktopRoot = path.resolve(__dirname, "..");
const runWithCargo = path.resolve(__dirname, "run-with-cargo.js");
const releaseDir = path.resolve(__dirname, "../src-tauri/target/release");
const tauriConfPath = path.resolve(__dirname, "../src-tauri/tauri.conf.json");
const rootDistDir = path.resolve(__dirname, "../../dist");

const DEFAULT_PRODUCT_NAME = "ArkAnalyzer-HapRay";
const NOTARY_ENV_KEYS = [
  "APPLE_ID",
  "APPLE_PASSWORD",
  "APPLE_TEAM_ID",
  "APPLE_API_KEY",
  "APPLE_API_KEY_PATH",
  "APPLE_API_ISSUER",
];

function loadTauriConf() {
  return JSON.parse(fs.readFileSync(tauriConfPath, "utf-8"));
}

function getProductName() {
  const conf = loadTauriConf();
  return conf.productName || DEFAULT_PRODUCT_NAME;
}

/** 与 Cargo 一致：CI 常设 CARGO_BUILD_TARGET；tauri bundle 默认不读该变量，须传 --target。 */
function getRustTargetTriple() {
  const t = process.env.CARGO_BUILD_TARGET || process.env.CARGO_TARGET;
  return t && String(t).trim() ? String(t).trim() : null;
}

/** bundle/macos、dmg 位于 target/[triple]/release/bundle/（设了 CARGO_BUILD_TARGET 时）。 */
function getMacBundleDirs() {
  const triple = getRustTargetTriple();
  const bundleBase = triple
    ? path.resolve(__dirname, "../src-tauri/target", triple, "release", "bundle")
    : path.resolve(__dirname, "../src-tauri/target/release/bundle");
  return {
    bundleBase,
    macosDir: path.join(bundleBase, "macos"),
    dmgDir: path.join(bundleBase, "dmg"),
  };
}

function getMacBundleArtifacts() {
  const { macosDir, dmgDir } = getMacBundleDirs();
  const tauriConf = loadTauriConf();
  const productName = tauriConf.productName || DEFAULT_PRODUCT_NAME;
  const version = tauriConf.version;
  /** Tauri 2 dmg 后缀：Apple Silicon 为 aarch64；Intel 为 x64（与 Rust 三元组 x86_64 不同） */
  const dmgArchSuffix = process.arch === "arm64" ? "aarch64" : "x64";
  const appName = `${productName}.app`;
  const dmgName = `${productName}_${version}_${dmgArchSuffix}.dmg`;
  return {
    productName,
    appName,
    appPath: path.join(macosDir, appName),
    dmgName,
    dmgPath: path.join(dmgDir, dmgName),
  };
}

function logSpawnFailure(cmd, args, result) {
  const msg = [cmd, ...args].join(" ");
  console.error(`\n[build] 命令失败 (退出码 ${result.status ?? 1}): ${msg}`);
  if (result.error) console.error("[build] 子进程错误:", result.error.message);
}

function spawnInDesktop(cmd, args, options = {}) {
  return spawnSync(cmd, args, {
    stdio: "inherit",
    cwd: desktopRoot,
    ...options,
  });
}

function run(cmd, args = [], options = {}) {
  const result = spawnInDesktop(cmd, args, options);
  if (result.status !== 0) {
    logSpawnFailure(cmd, args, result);
    process.exit(result.status ?? 1);
  }
  return result;
}

function runOptional(cmd, args = [], options = {}) {
  return spawnInDesktop(cmd, args, options).status === 0;
}

function stripNotaryEnv(env = process.env) {
  const next = { ...env };
  for (const k of NOTARY_ENV_KEYS) {
    delete next[k];
  }
  return next;
}

function tauriTargetCliArgs() {
  const triple = getRustTargetTriple();
  return triple ? ["--target", triple] : [];
}

function tauriBuildNoBundleArgs() {
  return [runWithCargo, "npx", "tauri", "build", "--no-bundle", ...tauriTargetCliArgs()];
}

function tauriBundleAppDmgArgs() {
  return [runWithCargo, "npx", "tauri", "bundle", "--bundles", "app,dmg", ...tauriTargetCliArgs()];
}

/** node 调 tauri 子进程；公证失败时去掉 notary 环境变量后重试。extraEnv 如 { CI: "true" } */
function tryNodeTauriWithNotaryFallback(nodeArgs, logLabel, extraEnv = {}) {
  const env = { ...process.env, ...extraEnv };
  if (runOptional("node", nodeArgs, { env })) {
    return true;
  }
  const hadNotaryEnv = NOTARY_ENV_KEYS.some((k) => process.env[k] !== undefined);
  if (!hadNotaryEnv) return false;

  console.warn(`\n[build] ${logLabel} 失败，尝试跳过 notarization 后重试（保留签名）...`);
  const retryEnv = { ...stripNotaryEnv(process.env), ...extraEnv };
  return runOptional("node", nodeArgs, { env: retryEnv });
}

/** tauri build --no-bundle → tauri bundle --bundles app,dmg（需两步：bundle 依赖已编译产物） */
function buildMacAppAndDmg() {
  if (!tryNodeTauriWithNotaryFallback(tauriBuildNoBundleArgs(), "tauri build --no-bundle")) {
    console.error("错误: tauri build 失败（含跳过 notarization 重试）");
    return false;
  }
  console.log("正在执行 tauri bundle --bundles app,dmg …");
  if (!tryNodeTauriWithNotaryFallback(tauriBundleAppDmgArgs(), "tauri bundle", { CI: "true" })) {
    console.error("错误: tauri bundle 失败（含跳过 notarization 重试）");
    return false;
  }
  return true;
}

/**
 * 将 Windows/Linux 构建产物复制到项目根 ./dist。
 */
function copyToDist() {
  if (process.platform === "darwin") {
    return;
  }

  const productName = getProductName();
  fs.mkdirSync(rootDistDir, { recursive: true });

  const exeName = process.platform === "win32" ? `${productName}.exe` : productName;
  const srcExe = path.join(releaseDir, exeName);
  const destExe = path.join(rootDistDir, exeName);

  if (!fs.existsSync(srcExe)) {
    console.warn(`跳过 copyToDist: 未找到 ${srcExe}`);
    return;
  }
  fs.copyFileSync(srcExe, destExe);

  if (process.platform === "linux") {
    const srcLib = path.join(releaseDir, "lib");
    const destLib = path.join(rootDistDir, "lib");
    if (fs.existsSync(srcLib)) {
      if (fs.existsSync(destLib)) fs.rmSync(destLib, { recursive: true });
      copyDirSync(srcLib, destLib);
    }
  }

  console.log(`✓ 构建产物已复制到 ${rootDistDir}`);
}

function copyDirSync(src, dest) {
  fs.mkdirSync(dest, { recursive: true });
  for (const entry of fs.readdirSync(src, { withFileTypes: true })) {
    const srcPath = path.join(src, entry.name);
    const destPath = path.join(dest, entry.name);
    if (entry.isSymbolicLink()) {
      fs.symlinkSync(fs.readlinkSync(srcPath), destPath);
    } else if (entry.isDirectory()) {
      copyDirSync(srcPath, destPath);
    } else {
      fs.copyFileSync(srcPath, destPath);
    }
  }
}

/** 将 .app 目录复制到 dist，并创建与可执行文件同名的符号链接 */
function copyMacBundleToDistFromSource(appSrcDir, productName, appName) {
  const exeInApp = path.join(appSrcDir, "Contents", "MacOS", productName);
  if (!fs.existsSync(appSrcDir) || !fs.existsSync(exeInApp)) {
    console.warn(`跳过: .app 不完整: ${appSrcDir}`);
    return false;
  }
  fs.mkdirSync(rootDistDir, { recursive: true });
  const distAppPath = path.join(rootDistDir, appName);
  const distExePath = path.join(rootDistDir, productName);
  if (fs.existsSync(distAppPath)) {
    fs.rmSync(distAppPath, { recursive: true });
  }
  copyDirSync(appSrcDir, distAppPath);
  if (fs.existsSync(distExePath)) {
    fs.unlinkSync(distExePath);
  }
  fs.symlinkSync(path.join(appName, "Contents", "MacOS", productName), distExePath, "file");
  return true;
}

function parseHdiutilAttachMountPoint(stdout) {
  for (const line of stdout.trim().split("\n")) {
    const tabParts = line.split("\t").filter(Boolean);
    if (tabParts.length >= 2) {
      const c = tabParts[tabParts.length - 1].trim();
      if (c.startsWith("/Volumes/")) return c;
    }
    const words = line.trim().split(/\s+/);
    const last = words[words.length - 1];
    if (last?.startsWith("/Volumes/")) return last;
  }
  return null;
}

function findAppBundleInDir(dir) {
  if (!fs.existsSync(dir)) return null;
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    if (entry.isDirectory() && entry.name.endsWith(".app")) {
      return path.join(dir, entry.name);
    }
  }
  return null;
}

/**
 * dmg 生成后：优先从挂载卷复制 .app（与安装包一致）；失败则使用 bundle/macos（同源）。
 */
function copyMacAppToDistAfterDmg() {
  const { appName, appPath, dmgPath } = getMacBundleArtifacts();
  const productName = getProductName();

  function fallback(msg) {
    if (msg) console.warn(msg);
    if (!copyMacBundleToDistFromSource(appPath, productName, appName)) {
      process.exit(1);
    }
    console.log(`✓ 已复制 ${appName} → ${rootDistDir}（bundle 目录，与 dmg 内应用一致）`);
  }

  if (!fs.existsSync(dmgPath)) {
    console.error(`错误: 未找到 .dmg: ${dmgPath}`);
    process.exit(1);
  }

  const attached = spawnSync("hdiutil", ["attach", dmgPath, "-nobrowse"], {
    encoding: "utf8",
  });
  if (attached.status !== 0) {
    fallback("[build] hdiutil attach 失败，使用 bundle 目录");
    return;
  }

  const mountPoint = parseHdiutilAttachMountPoint(attached.stdout || "");
  if (!mountPoint) {
    fallback("[build] 无法解析 dmg 挂载点，使用 bundle 目录");
    return;
  }

  let srcApp = path.join(mountPoint, appName);
  if (!fs.existsSync(srcApp)) {
    srcApp = findAppBundleInDir(mountPoint);
  }

  try {
    if (!srcApp || !fs.existsSync(srcApp)) {
      fallback(`[build] 卷内未找到 ${appName}，使用 bundle 目录`);
      return;
    }
    if (!copyMacBundleToDistFromSource(srcApp, productName, appName)) {
      process.exit(1);
    }
    console.log(`✓ 已从 dmg 卷复制 ${appName} → ${rootDistDir}（本地测试）`);
  } finally {
    const det = spawnSync("hdiutil", ["detach", mountPoint], { stdio: "pipe" });
    if (det.status !== 0) {
      console.warn(`[build] hdiutil detach 未成功，可手动卸载: ${mountPoint}`);
    }
  }
}

function signDistToolsDeveloperId() {
  if (!process.env.APPLE_SIGNING_IDENTITY) return;

  const toolsDir = path.join(rootDistDir, "tools");
  if (!fs.existsSync(toolsDir)) {
    console.warn(`[build] 跳过 dist/tools Developer ID 签名：目录不存在 ${toolsDir}`);
    return;
  }
  const signScript = path.resolve(__dirname, "../../scripts/sign_dist_tools_developer_id.sh");
  if (!fs.existsSync(signScript)) {
    console.warn(`[build] 未找到 ${signScript}`);
    return;
  }
  console.log("\nStep 0: Developer ID 签名 dist/tools（嵌套二进制，满足公证）...");
  run("bash", [signScript, toolsDir], { env: { ...process.env } });
}

function buildMacos() {
  signDistToolsDeveloperId();
  console.log("Step 1: tauri build --no-bundle → tauri bundle --bundles app,dmg …");
  if (!buildMacAppAndDmg()) {
    process.exit(1);
  }

  console.log("\nStep 2: 将 dmg 中的应用复制到 ./dist（本地测试）...");
  copyMacAppToDistAfterDmg();
}

function buildNonMacos() {
  console.log("构建应用...");
  run("node", [runWithCargo, "npx", "tauri", "build"]);

  if (process.platform === "linux") {
    console.log("\n捆绑 Linux 动态库到 lib/（免装 libwebkit2gtk）...");
    run("node", [path.resolve(__dirname, "bundle-linux-libs.js")]);
  }

  console.log("\n复制产物到 ./dist...");
  copyToDist();
}

function main() {
  if (process.platform === "darwin") {
    buildMacos();
  } else {
    buildNonMacos();
  }
}

main();
