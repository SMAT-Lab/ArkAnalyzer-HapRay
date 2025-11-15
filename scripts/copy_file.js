#!/usr/bin/env node
const fs = require("fs");
const path = require("path");

const [,, srcArg, destArg] = process.argv;

if (!srcArg || !destArg) {
  console.error("Usage: node scripts/copy_file.js <src> <dest>");
  process.exit(1);
}

const repoRoot = path.resolve(__dirname, "..");
const src = path.resolve(repoRoot, srcArg);
const dest = path.resolve(repoRoot, destArg);
const destDir = path.dirname(dest);

if (!fs.existsSync(src)) {
  console.error(`Source file not found: ${src}`);
  process.exit(1);
}

fs.mkdirSync(destDir, { recursive: true });
fs.copyFileSync(src, dest);

console.log(`Copied ${src} -> ${dest}`);