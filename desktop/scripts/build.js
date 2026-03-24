#!/usr/bin/env node
/**
 * 构建脚本：在 macOS 上先构建 .app -> 再生成 .dmg
 *
 * 注意：tauri bundle --bundles dmg 会重新创建 .app，
 * 因此需先构建 .app 再直接调用 bundle_dmg.sh 生成 dmg，而非使用 tauri bundle。
 */
import { spawnSync } from "child_process";
import path from "path";
import fs from "fs";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const desktopRoot = path.resolve(__dirname, "..");
const runWithCargo = path.resolve(__dirname, "run-with-cargo.js");
const bundleBase = path.resolve(__dirname, "../src-tauri/target/release/bundle");
const macosDir = path.join(bundleBase, "macos");
const dmgDir = path.join(bundleBase, "dmg");
const bundleDmgSh = path.join(dmgDir, "bundle_dmg.sh");
const tauriConfPath = path.resolve(__dirname, "../src-tauri/tauri.conf.json");
// 项目根目录的 dist（desktop 的祖父目录）
const rootDistDir = path.resolve(__dirname, "../../dist");

function loadTauriConf() {
  return JSON.parse(fs.readFileSync(tauriConfPath, "utf-8"));
}

function getMacBundleArtifacts() {
  const tauriConf = loadTauriConf();
  const productName = tauriConf.productName || "ArkAnalyzer-HapRay";
  const version = tauriConf.version;
  const arch = process.arch === "arm64" ? "aarch64" : "x86_64";
  const appName = `${productName}.app`;
  const dmgName = `${productName}_${version}_${arch}.dmg`;
  return {
    productName,
    appName,
    appPath: path.join(macosDir, appName),
    dmgName,
    dmgPath: path.join(dmgDir, dmgName),
  };
}

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
    cwd: desktopRoot,
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
    cwd: desktopRoot,
    ...options,
  });
  return result.status === 0;
}

function createDmgWithBundleScript() {
  const { appName, appPath, dmgPath } = getMacBundleArtifacts();

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
    cwd: desktopRoot,
    env: { ...process.env, CI: "true" },
  });
  if (result.status !== 0) {
    const msg = ["bash", bundleDmgSh, ...args].join(" ");
    console.error(`\n[build] 命令失败 (退出码 ${result.status ?? 1}): ${msg}`);
    if (result.error) console.error("[build] 子进程错误:", result.error.message);
    return false;
  }
  return true;
}

const releaseDir = path.resolve(__dirname, "../src-tauri/target/release");

/**
 * 将 desktop 构建产物复制到项目根目录 ./dist，供 e2e 测试和 release 使用
 * macOS: dist/ArkAnalyzer-HapRay.app/, dist/ArkAnalyzer-HapRay -> .app/...（不覆盖 dist/tools/）
 * Windows/Linux: dist/ArkAnalyzer-HapRay.exe 或 dist/ArkAnalyzer-HapRay
 */
function copyToDist() {
  const tauriConf = loadTauriConf();
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

/**
 * 公证要求 Resources/tools 内嵌的 PyInstaller 等 Mach-O 也使用 Developer ID；
 * 仅在设置 APPLE_SIGNING_IDENTITY 时对 dist/tools 递归签名（于 tauri build 之前）。
 */
function signDistToolsDeveloperId() {
  const identity = process.env.APPLE_SIGNING_IDENTITY;
  if (!identity) return;
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

function main() {
  if (process.platform === "darwin") {
    // macOS: app -> dmg
    signDistToolsDeveloperId();
    console.log("Step 1: 构建 .app bundle...");
    run("node", [runWithCargo, "npx", "tauri", "build", "--bundles", "app"]);

    console.log("\nStep 2: 生成 .dmg...");
    let reuseExistingDmg = false;
    if (!fs.existsSync(bundleDmgSh)) {
      const { appPath, dmgPath } = getMacBundleArtifacts();
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
      // tauri bundle 首次成功后若已产出 dmg，则直接复用，避免再生成一次 dmg。
      if (bundleOk && fs.existsSync(dmgPath)) {
        console.log("\n检测到 tauri bundle 已生成 dmg，直接复用该产物。");
        reuseExistingDmg = true;
      }
      // tauri bundle 可能清理 .app；后续 copyToDist 仍需要 .app，缺失时补构建一次。
      if (!fs.existsSync(appPath)) {
        console.log("\n重新构建 .app（tauri bundle 可能已清理）...");
        run("node", [runWithCargo, "npx", "tauri", "build", "--bundles", "app"]);
      }
    }

    if (!reuseExistingDmg) {
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
    }
    console.log("\nStep 3: 复制产物到 ./dist...");
    copyToDist();
  } else {
    // 其他平台：保持原有流程
    console.log("构建应用...");
    run("node", [runWithCargo, "npx", "tauri", "build"]);

    if (process.platform === "linux") {
      console.log("\n捆绑 Linux 动态库到 lib/（免装 libwebkit2gtk）...");
      run("node", [path.resolve(__dirname, "bundle-linux-libs.js")]);
    }

    console.log("\n复制产物到 ./dist...");
    copyToDist();
  }
}

main();
