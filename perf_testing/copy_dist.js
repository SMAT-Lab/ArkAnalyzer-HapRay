#!/usr/bin/env node
const fs = require("fs");
const path = require("path");

const perfTestingRoot = path.resolve(__dirname);
const repoRoot = path.resolve(perfTestingRoot, "..");
const srcDir = path.join(perfTestingRoot, "dist", "ArkAnalyzer-HapRay");
const destDir = path.join(repoRoot, "dist");

if (!fs.existsSync(srcDir)) {
  console.error(`Source directory not found: ${srcDir}`);
  process.exit(1);
}

fs.mkdirSync(destDir, { recursive: true });

for (const entry of fs.readdirSync(srcDir)) {
  const srcPath = path.join(srcDir, entry);
  const destPath = path.join(destDir, entry);
  fs.cpSync(srcPath, destPath, { recursive: true, force: true });
}

console.log(`Copied contents of ${srcDir} -> ${destDir}`);

