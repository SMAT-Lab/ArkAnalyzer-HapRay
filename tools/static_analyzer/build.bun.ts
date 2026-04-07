#!/usr/bin/env bun
/**
 * Bun 构建脚本 - 替代 webpack 构建 static_analyzer
 * 使用 bun build 进行打包，并复制所需资源文件
 */
import { join } from "path";
import { existsSync, mkdirSync, cpSync, readdirSync, statSync, renameSync } from "fs";
import archiver from "archiver";
import AdmZip from "adm-zip";
import { createWriteStream } from "fs";

const __dirname = import.meta.dir;
const rootDir = join(__dirname, "../..");
const distDir = join(rootDir, "dist/tools/sa-cmd");
const pkg = await Bun.file(join(__dirname, "package.json")).json();
const version = (pkg as { version: string }).version;

async function build() {
  if (isBinary) {
    return buildBinary();
  }

  console.log("Building static_analyzer with Bun...");

  // 0. 确保输出目录存在
  if (!existsSync(distDir)) {
    mkdirSync(distDir, { recursive: true });
  }

  // 1. Bun build (outdir 输出为 index.js，需重命名为 hapray-sa-cmd.js)
  const result = await Bun.build({
    entrypoints: [join(__dirname, "src/cli/index.ts")],
    outdir: distDir,
    target: "node",
    format: "cjs",
    minify: true,
    sourcemap: "none",
    external: ["sql.js"],
  });

  if (!result.success) {
    console.error("Bun build failed:", result.logs);
    process.exit(1);
  }

  // 重命名 index.js -> hapray-sa-cmd.js
  const indexJs = join(distDir, "index.js");
  const outputFile = join(distDir, "hapray-sa-cmd.js");
  if (existsSync(indexJs)) {
    renameSync(indexJs, outputFile);
  }

  // 2. 确保输出目录存在并复制资源文件
  if (!existsSync(distDir)) {
    mkdirSync(distDir, { recursive: true });
  }

  const copyPatterns: Array<{ from: string; to: string; isDir?: boolean }> = [
    { from: join(__dirname, "res"), to: join(distDir, "res"), isDir: true },
    {
      from: join(rootDir, "node_modules/bjc/res"),
      to: join(distDir, "res"),
      isDir: true,
    },
    { from: join(__dirname, "plugin.json"), to: join(distDir, "plugin.json") },
    { from: join(__dirname, "README.md"), to: join(distDir, "README.md") },
    {
      from: join(__dirname, "src/core/elf/demangle-wasm.wasm"),
      to: join(distDir, "demangle-wasm.wasm"),
    },
    {
      from: join(rootDir, "node_modules/sql.js/package.json"),
      to: join(distDir, "node_modules/sql.js/package.json"),
    },
    {
      from: join(rootDir, "node_modules/sql.js/dist/sql-wasm.js"),
      to: join(distDir, "node_modules/sql.js/dist/sql-wasm.js"),
    },
    {
      from: join(rootDir, "node_modules/sql.js/dist/sql-wasm.wasm"),
      to: join(distDir, "node_modules/sql.js/dist/sql-wasm.wasm"),
    },
    {
      from: join(rootDir, "node_modules/sql.js/dist/worker.sql-wasm.js"),
      to: join(distDir, "node_modules/sql.js/dist/worker.sql-wasm.js"),
    },
  ];

  for (const { from, to, isDir } of copyPatterns) {
    if (!existsSync(from)) {
      console.warn(`Skip (not found): ${from}`);
      continue;
    }
    mkdirSync(join(to, ".."), { recursive: true });
    const stat = statSync(from);
    if (stat.isDirectory() || isDir) {
      cpSync(from, to, { recursive: true });
    } else {
      cpSync(from, to);
    }
  }

  // 3. 打包 zip (与 webpack PackPlugin 逻辑一致)
  const outputZip = join(__dirname, `hapray-sa_v${version}.zip`);
  await createZip(distDir, outputZip, rootDir);
  console.log(`Build completed. Output: ${distDir}`);
  console.log(`Zip: ${outputZip}`);
}

async function createZip(
  distDir: string,
  outputPath: string,
  rootDir: string
): Promise<void> {
  return new Promise((resolve, reject) => {
    const output = createWriteStream(outputPath);
    const archive = archiver("zip", { zlib: { level: 9 } });
    archive.pipe(output);

    // 打包 sa-cmd 目录内容
    for (const filename of readdirSync(distDir)) {
      const fullPath = join(distDir, filename);
      const stat = statSync(fullPath);
      if (stat.isDirectory()) {
        archive.directory(fullPath, filename);
      } else {
        archive.file(fullPath, { name: filename });
      }
    }

    // 解压 trace_streamer_binary.zip 并打包到 tools 目录
    const traceStreamerZip = join(rootDir, "third-party/trace_streamer_binary.zip");
    if (existsSync(traceStreamerZip)) {
      try {
        const zip = new AdmZip(traceStreamerZip);
        for (const entry of zip.getEntries()) {
          if (!entry.isDirectory) {
            const flat = entry.entryName.replace(/^trace_streamer_binary[/\\]?/i, "");
            archive.append(zip.readFile(entry), { name: `tools/bin/${flat}` });
          }
        }
      } catch (err) {
        console.error("Failed to extract trace_streamer_binary.zip:", err);
      }
    }

    archive.finalize();
    output.on("close", () => resolve());
    archive.on("error", reject);
    output.on("error", reject);
  });
}

const isBinary = process.argv.includes("--binary");

async function buildBinary() {
  console.log("Building static_analyzer binary with Bun...");

  if (!existsSync(distDir)) {
    mkdirSync(distDir, { recursive: true });
  }

  const platform = process.platform;
  const ext = platform === "win32" ? ".exe" : "";
  const outfile = join(distDir, `hapray-sa-cmd${ext}`);

  // 二进制需打包 sql.js，否则运行时找不到（external 的模块无法随二进制分发）
  const result = await Bun.build({
    entrypoints: [join(__dirname, "src/cli/index.ts")],
    target: "bun",
    minify: true,
    sourcemap: "none",
    compile: { outfile },
  });

  if (!result.success) {
    console.error("Bun compile failed:", result.logs);
    process.exit(1);
  }

  copyResources(distDir);

  console.log(`Binary: ${outfile}`);
}

function copyResources(dir: string) {
  const copyPatterns: Array<{ from: string; to: string; isDir?: boolean }> = [
    { from: join(__dirname, "res"), to: join(dir, "res"), isDir: true },
    { from: join(rootDir, "node_modules/bjc/res"), to: join(dir, "res"), isDir: true },
    { from: join(__dirname, "plugin.json"), to: join(dir, "plugin.json") },
    { from: join(__dirname, "README.md"), to: join(dir, "README.md") },
    { from: join(__dirname, "src/core/elf/demangle-wasm.wasm"), to: join(dir, "demangle-wasm.wasm") },
    { from: join(rootDir, "node_modules/sql.js/package.json"), to: join(dir, "node_modules/sql.js/package.json") },
    { from: join(rootDir, "node_modules/sql.js/dist/sql-wasm.js"), to: join(dir, "node_modules/sql.js/dist/sql-wasm.js") },
    { from: join(rootDir, "node_modules/sql.js/dist/sql-wasm.wasm"), to: join(dir, "node_modules/sql.js/dist/sql-wasm.wasm") },
    { from: join(rootDir, "node_modules/sql.js/dist/worker.sql-wasm.js"), to: join(dir, "node_modules/sql.js/dist/worker.sql-wasm.js") },
  ];

  for (const { from, to, isDir } of copyPatterns) {
    if (!existsSync(from)) continue;
    mkdirSync(join(to, ".."), { recursive: true });
    if (statSync(from).isDirectory() || isDir) cpSync(from, to, { recursive: true });
    else cpSync(from, to);
  }
}

build().catch((err) => {
  console.error(err);
  process.exit(1);
});
