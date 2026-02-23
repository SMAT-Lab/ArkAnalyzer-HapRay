#!/usr/bin/env node
/**
 * 在 PATH 中包含 Cargo 的前提下执行命令（解决 npm run build 时找不到 cargo 的问题）
 */
import { spawnSync } from "child_process";
import path from "path";

const sep = process.platform === "win32" ? ";" : ":";
const cargoBin =
  process.platform === "win32"
    ? path.join(process.env.USERPROFILE || "", ".cargo", "bin")
    : path.join(process.env.HOME || "", ".cargo", "bin");
const nodeBin = path.join(process.cwd(), "node_modules", ".bin");

const env = { ...process.env };
// Windows 使用 "Path"（首字母大写），需沿用原键名否则子进程拿不到
const pathKey = Object.keys(process.env).find((k) => k.toLowerCase() === "path") || "PATH";
const pathParts = [cargoBin, nodeBin].filter(Boolean);
if (pathParts.length) {
  env[pathKey] = pathParts.join(sep) + sep + (env[pathKey] || env.PATH || "");
}

const result = spawnSync(process.argv[2], process.argv.slice(3), {
  stdio: "inherit",
  env,
});
process.exit(result.status ?? 1);
