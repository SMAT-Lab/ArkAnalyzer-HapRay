#!/usr/bin/env node
/**
 * 构建脚本：在 macOS 上先构建 .app -> 再生成 .dmg
 *
 * 注意：tauri bundle --bundles dmg 会重新创建 .app，
 * 因此需先构建 .app 再直接调用 bundle_dmg.sh 生成 dmg，而非使用 tauri bundle。
 */
import { spawnSync, execSync } from "child_process";
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

function patchBundleDmgShDetachTimeout() {
  if (!fs.existsSync(bundleDmgSh)) return false;
  const sh = fs.readFileSync(bundleDmgSh, "utf8");

  // 已经打过补丁就跳过（确保幂等）
  if (sh.includes("DiskArbitration timeout")) return true;

  const oldFnRegex =
    /function hdiutil_detach_retry\(\) \{[\s\S]*?\n\s*unset unmounting_attempts\n\s*\}/m;

  if (!oldFnRegex.test(sh)) {
    console.error("错误: 未找到可替换的 hdiutil_detach_retry 函数块，无法修补 bundle_dmg.sh");
    return false;
  }

  const newFn = `function hdiutil_detach_retry() {
	# Unmount with retries; macOS (e.g. 15) may fail with DiskArbitration timeout.
	unmounting_attempts=0
	while :; do
		echo "Unmounting disk image..."
		(( unmounting_attempts++ ))
		set +e
		detach_output="$(hdiutil detach "$1" 2>&1)"
		exit_code=$?
		set -e

		# nothing goes wrong
		(( exit_code == 0 )) && break

		# Retry on busy (EBUSY) or known DiskArbitration timeout texts
		if (( exit_code == 16 )) || echo "$detach_output" | grep -Eqi 'timeout for DiskArbitration expired|drive not detached'; then
			if (( unmounting_attempts == MAXIMUM_UNMOUNTING_ATTEMPTS )); then
				echo "Unmount patience exhausted, trying force detach..."
				set +e
				hdiutil detach -force "$1" 2>&1
				force_code=$?
				set -e
				exit $force_code
			fi
			echo "Wait a moment..."
			sleep $(( 1 * (2 ** unmounting_attempts) ))
			continue
		fi

		# Other detach errors are not retryable.
		echo "$detach_output" >&2
		exit $exit_code
	done
	unset unmounting_attempts
}`;

  const patched = sh.replace(oldFnRegex, newFn);
  if (patched === sh) return false;
  fs.writeFileSync(bundleDmgSh, patched, "utf8");
  return true;
}

function run(cmd, args = [], options = {}) {
  const result = spawnSync(cmd, args, {
    stdio: "inherit",
    cwd: path.resolve(__dirname, ".."),
    ...options,
  });
  if (result.status !== 0) {
    const msg = [cmd, ...args].join(" ");
    console.error(`\n[build] 命令失败 (退出码 ${result.status ?? 1}): ${msg}`);
    if (result.error) console.error("[build] 子进程错误:", result.error.message);
    process.exit(result.status ?? 1);
  }
  return result;
}

/** 执行命令，失败时不退出，返回是否成功 */
function runOptional(cmd, args = [], options = {}) {
  const result = spawnSync(cmd, args, {
    stdio: "inherit",
    cwd: path.resolve(__dirname, ".."),
    ...options,
  });
  return result.status === 0;
}

/**
 * create-dmg / hdiutil 默认 zlib 等级往往低于 9，对 UDZO 再压一次可略减 DMG 体积（通常数 MB 级）。
 * 注意：-o 若不以 .dmg 结尾，hdiutil 会再追加 .dmg，导致实际路径与预期不一致。
 */
function recompressDmgUdzoZlib9(dmgPath) {
  const tmpDmg = dmgPath.replace(/\.dmg$/i, ".udzo9-tmp.dmg");
  if (fs.existsSync(tmpDmg)) fs.unlinkSync(tmpDmg);
  const r = spawnSync(
    "hdiutil",
    ["convert", dmgPath, "-format", "UDZO", "-imagekey", "zlib-level=9", "-o", tmpDmg],
    { stdio: "inherit" },
  );
  if (r.status !== 0) {
    if (fs.existsSync(tmpDmg)) fs.unlinkSync(tmpDmg);
    console.warn(`[build] DMG zlib-level=9 重压缩跳过（hdiutil 退出码 ${r.status ?? 1}）`);
    return;
  }
  let produced = tmpDmg;
  if (!fs.existsSync(produced)) {
    // 兼容：旧逻辑曾用 *.dmg.udzo9，hdiutil 生成 *.dmg.udzo9.dmg
    const legacy = `${dmgPath}.udzo9.dmg`;
    if (fs.existsSync(legacy)) produced = legacy;
  }
  if (!fs.existsSync(produced)) {
    console.error("[build] DMG 重压缩后未找到输出文件:", tmpDmg);
    return;
  }
  try {
    fs.unlinkSync(dmgPath);
    fs.renameSync(produced, dmgPath);
    console.log("  ✓ DMG 已用 zlib-level=9 重新压缩");
  } catch (e) {
    console.error("[build] 替换 DMG 失败:", e.message);
    if (fs.existsSync(tmpDmg) && tmpDmg !== dmgPath) fs.unlinkSync(tmpDmg);
  }
}

function createDmgWithBundleScript() {
  // 读取 tauri 配置
  const tauriConfPath = path.resolve(__dirname, "../src-tauri/tauri.conf.json");
  const tauriConf = JSON.parse(fs.readFileSync(tauriConfPath, "utf-8"));
  const productName = tauriConf.productName || "ArkAnalyzer-HapRay";
  const version = tauriConf.version || "1.5.1";
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
  const result = spawnSync("bash", [bundleDmgSh, ...args], {
    stdio: "inherit",
    cwd: path.resolve(__dirname, ".."),
    env: { ...process.env, CI: "true" },
  });
  if (result.status !== 0) {
    const msg = ["bash", bundleDmgSh, ...args].join(" ");
    console.error(`\n[build] 命令失败 (退出码 ${result.status ?? 1}): ${msg}`);
    if (result.error) console.error("[build] 子进程错误:", result.error.message);
    return false;
  }
  recompressDmgUdzoZlib9(dmgPath);
  return true;
}

const releaseDir = path.resolve(__dirname, "../src-tauri/target/release");

/**
 * 将 desktop 构建产物复制到项目根目录 ./dist，供 e2e 测试和 release 使用
 * macOS: dist/ArkAnalyzer-HapRay.app/, dist/ArkAnalyzer-HapRay -> .app/...（不覆盖 dist/tools/）
 * Windows/Linux: dist/ArkAnalyzer-HapRay.exe 或 dist/ArkAnalyzer-HapRay
 */
function copyToDist() {
  const tauriConf = JSON.parse(fs.readFileSync(path.resolve(__dirname, "../src-tauri/tauri.conf.json"), "utf-8"));
  const productName = tauriConf.productName || "ArkAnalyzer-HapRay";
  fs.mkdirSync(rootDistDir, { recursive: true });

  if (process.platform === "darwin") {
    const appName = `${productName}.app`;
    const appPath = path.join(macosDir, appName);
    const exeInApp = path.join(appPath, "Contents", "MacOS", productName);

    if (!fs.existsSync(appPath) || !fs.existsSync(exeInApp)) {
      console.warn("跳过 copyToDist: .app 或可执行文件不存在");
      return;
    }

    const distAppPath = path.join(rootDistDir, appName);
    const distExePath = path.join(rootDistDir, productName);

    if (fs.existsSync(distAppPath)) {
      fs.rmSync(distAppPath, { recursive: true });
    }
    copyDirSync(appPath, distAppPath);

    if (fs.existsSync(distExePath)) {
      fs.unlinkSync(distExePath);
    }
    fs.symlinkSync(path.join(appName, "Contents", "MacOS", productName), distExePath, "file");
  } else {
    // Windows: .exe；Linux: 无后缀
    const exeName = process.platform === "win32" ? `${productName}.exe` : productName;
    const srcExe = path.join(releaseDir, exeName);
    const destExe = path.join(rootDistDir, exeName);

    if (!fs.existsSync(srcExe)) {
      console.warn(`跳过 copyToDist: 未找到 ${srcExe}`);
      return;
    }
    fs.copyFileSync(srcExe, destExe);

    // Linux: 复制 lib/ 下的 .so，使目标机无需安装 libwebkit2gtk 等
    if (process.platform === "linux") {
      const srcLib = path.join(releaseDir, "lib");
      const destLib = path.join(rootDistDir, "lib");
      if (fs.existsSync(srcLib)) {
        if (fs.existsSync(destLib)) fs.rmSync(destLib, { recursive: true });
        copyDirSync(srcLib, destLib);
      }
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
  if (process.platform === "darwin") {
    // macOS: app -> dmg
    console.log("Step 1: 构建 .app bundle...");
    run("node", [runWithCargo, "npx", "tauri", "build", "--bundles", "app"]);

    // Tauri bundle.resources 使用 fs::copy 会解析软连接，导致 opt-detector 等 PyInstaller 产物的符号链接丢失。
    // 用保留软连接的复制覆盖 tools。
    console.log("\nStep 1.5: 恢复 tools 软连接...");
    run("node", [path.resolve(__dirname, "copy-tools-with-symlinks.js")]);
    run("node", [mergeScript]);

    console.log("\nStep 2: 生成 .dmg...");
    if (!fs.existsSync(bundleDmgSh)) {
      // 首次构建：tauri bundle 会创建 dmg 目录和 bundle_dmg.sh
      // 注意：tauri bundle 内部运行 bundle_dmg.sh 时可能因 AppleScript 权限失败，
      // 但我们只需要 bundle_dmg.sh 文件，后续用 --skip-jenkins 自行调用即可
      console.log("bundle_dmg.sh 不存在，先运行 tauri bundle 以创建 dmg 工具...");
      const bundleOk = runOptional("node", [runWithCargo, "npx", "tauri", "bundle", "--bundles", "dmg"], {
        env: { ...process.env, CI: "true" },
      });
      if (!fs.existsSync(bundleDmgSh)) {
        console.error("错误: tauri bundle 未生成 bundle_dmg.sh，无法继续");
        process.exit(1);
      }
      if (!bundleOk) {
        console.log("(tauri bundle 因 AppleScript 权限失败，但 bundle_dmg.sh 已创建，继续用 --skip-jenkins 生成 dmg)");
      }
      // tauri bundle 会清理 .app，需重新构建 .app 才能继续
      console.log("\n重新构建 .app（tauri bundle 可能已清理）...");
      run("node", [runWithCargo, "npx", "tauri", "build", "--bundles", "app"]);
    }

    // tauri bundle 生成的 create-dmg 脚本在 macOS 15 的 CI 环境可能遇到 detach 超时
    // （例如 "timeout for DiskArbitration expired"），导致脚本返回码非 0 进而让 npm 构建失败。
    const patched = patchBundleDmgShDetachTimeout();
    if (!patched) {
      console.error("错误: 修补 bundle_dmg.sh 的 detach 逻辑失败");
      process.exit(1);
    }
    const dmgOk = createDmgWithBundleScript();
    if (!dmgOk) {
      process.exit(1);
    }
    console.log("\nStep 3: 复制产物到 ./dist...");
    copyToDist();
  } else {
    // 其他平台：保持原有流程
    console.log("构建应用...");
    run("node", [runWithCargo, "npx", "tauri", "build"]);

    // 恢复 tools 软连接（Tauri bundle.resources 会解析软连接）
    console.log("\n恢复 tools 软连接...");
    run("node", [path.resolve(__dirname, "copy-tools-with-symlinks.js")]);
    run("node", [mergeScript]);

    if (process.platform === "linux") {
      console.log("\n捆绑 Linux 动态库到 lib/（免装 libwebkit2gtk）...");
      run("node", [path.resolve(__dirname, "bundle-linux-libs.js")]);
    }

    console.log("\n复制产物到 ./dist...");
    copyToDist();
  }
}

main();
