#!/usr/bin/env node
/**
 * 执行 release：merge_duplicates + zip。
 * macOS 上跳过（不做任何处理）。
 */
const { execSync } = require('child_process');
const path = require('path');

if (process.platform === 'darwin') {
  console.log('release: 在 macOS 上跳过，不执行 merge/zip');
  process.exit(0);
}

const root = path.resolve(__dirname, '..');
execSync('node scripts/merge_duplicates.js', { cwd: root, stdio: 'inherit' });
execSync('node scripts/zip.js ArkAnalyzer-HapRay', { cwd: root, stdio: 'inherit' });
