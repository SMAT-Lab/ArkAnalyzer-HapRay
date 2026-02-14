#!/usr/bin/env node
/**
 * 跨平台 Rust 安装脚本
 * 根据当前系统自动选择 macOS/Linux 或 Windows 安装方式
 */

import { execSync, spawnSync } from "child_process";
import { fileURLToPath } from "url";
import path from "path";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const platform = process.platform;

// 检测时先加上默认 Cargo 路径，避免 PATH 未包含时误判为未安装
const cargoBin =
  platform === "win32"
    ? path.join(process.env.USERPROFILE || "", ".cargo", "bin")
    : path.join(process.env.HOME || "", ".cargo", "bin");
const sep = platform === "win32" ? ";" : ":";
const envWithCargo = { ...process.env, PATH: `${cargoBin}${sep}${process.env.PATH || ""}` };

// 已安装则直接返回
try {
  execSync("rustc --version", { encoding: "utf8", env: envWithCargo });
  console.log("Rust 已安装，跳过。");
  process.exit(0);
} catch {}

if (platform === "win32") {
  const psScript = path.join(__dirname, "install-rust.ps1");
  const result = spawnSync(
    "powershell",
    ["-ExecutionPolicy", "Bypass", "-File", psScript],
    { stdio: "inherit" }
  );
  process.exit(result.status ?? 1);
} else if (platform === "darwin" || platform === "linux") {
  const shScript = path.join(__dirname, "install-rust.sh");
  execSync(`sh "${shScript}"`, { stdio: "inherit" });
} else {
  console.error(`不支持的平台: ${platform}`);
  console.error("请手动访问 https://rustup.rs/ 安装 Rust");
  process.exit(1);
}
