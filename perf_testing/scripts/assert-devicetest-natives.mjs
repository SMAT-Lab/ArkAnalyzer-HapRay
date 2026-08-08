/**
 * 构建后静态校验：perf-testing 发布包必须包含全部 uitest_agent native，
 * 否则 macOS/Linux 上 arm64 真机 UI RPC 会因 Push file failed 初始化失败。
 * （collect_data_files 在 Unix 上会排除 .so，故用整目录打包后必须在此兜底。）
 */
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const nativeDir = path.resolve(
  __dirname,
  "..",
  "..",
  "dist",
  "tools",
  "perf-testing",
  "_internal",
  "devicetest",
  "res",
  "prototype",
  "native",
);
const recorderDir = path.resolve(nativeDir, "..", "..", "recorder");

const REQUIRED_AGENTS = [
  "uitest_agent_v1.2.2.so",
  "uitest_agent_v1.1.9.x86_64_so",
];

function fail(msg) {
  console.error(`[assert-devicetest-natives] ${msg}`);
  process.exit(1);
}

function main() {
  if (!fs.existsSync(nativeDir)) {
    fail(`native 目录不存在: ${nativeDir}`);
  }

  const files = fs.readdirSync(nativeDir).filter((name) => {
    const full = path.join(nativeDir, name);
    return fs.statSync(full).isFile();
  });

  if (files.length < 5) {
    fail(
      `prototype/native 文件数应为 >= 5，实际 ${files.length}: ${files.join(", ") || "(空)"}`,
    );
  }

  for (const name of REQUIRED_AGENTS) {
    if (!files.includes(name)) {
      fail(`缺少必需 agent: ${name}（目录内容: ${files.join(", ")}）`);
    }
  }

  const agents = files.filter((name) => name.startsWith("uitest_agent"));
  if (agents.length < 5) {
    fail(`uitest_agent* 数量应为 >= 5，实际 ${agents.length}: ${agents.join(", ")}`);
  }

  if (fs.existsSync(recorderDir)) {
    const scrcpy = fs
      .readdirSync(recorderDir)
      .filter((name) => name.startsWith("libscrcpy_server") && name.endsWith(".z.so"));
    if (scrcpy.length < 1) {
      fail(`recorder 下缺少 libscrcpy_server*.z.so（目录: ${recorderDir}）`);
    }
  } else {
    fail(`recorder 目录不存在: ${recorderDir}`);
  }

  console.log(
    `✓ devicetest natives OK: ${agents.length} uitest_agent* under ${nativeDir}`,
  );
}

main();
