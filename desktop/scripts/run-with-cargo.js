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

const cmd = process.argv[2];
const args = process.argv.slice(3);
// Windows 上 node_modules\.bin\npx 为 npx.cmd，无 shell 时 spawn 可能找不到，故用 shell 执行
const opts = { stdio: "inherit", env };
let result;
if (process.platform === "win32" && (cmd === "npx" || cmd === "npx.cmd")) {
  const fullCmd = [cmd, ...args].map((a) => (a.includes(" ") ? `"${a}"` : a)).join(" ");
  result = spawnSync(fullCmd, { ...opts, shell: true });
} else {
  result = spawnSync(cmd, args, opts);
}
process.exit(result.status ?? 1);
