#!/usr/bin/env node
const path = require('path');
const { access, constants, mkdir, cp, stat } = require('fs/promises');

const ROOT_DIR = path.resolve(__dirname, '..');
const args = process.argv.slice(2);

if (args.length !== 2) {
  console.error('Invalid arguments. Usage: node build/copy.js <source> <target>');
  process.exit(1);
}

const sourcePath = path.resolve(ROOT_DIR, args[0]);
const targetPath = path.resolve(ROOT_DIR, args[1]);

async function ensureSourceExists(filePath) {
  try {
    await access(filePath, constants.F_OK);
  } catch {
    throw new Error(`Source path not found: ${filePath}. Please ensure the file or directory exists.`);
  }
}

async function copyEntry(src, dest) {
  const srcStat = await stat(src);
  await mkdir(path.dirname(dest), { recursive: true });

  if (srcStat.isDirectory()) {
    await cp(src, dest, { recursive: true });
  } else {
    await cp(src, dest);
  }
}

async function main() {
  await ensureSourceExists(sourcePath);
  await copyEntry(sourcePath, targetPath);
console.log(`Copied ${sourcePath} to ${targetPath}`);
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});