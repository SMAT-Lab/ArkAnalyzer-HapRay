#!/usr/bin/env node
/**
 * Package given files/directories into a zip file
 * Usage: node pack.js <zip-name> <file-or-directory> [more files/dirs]
 */

const fs = require('fs');
const path = require('path');
const archiver = require('archiver');
const os = require('os');

// Validate arguments
const args = process.argv.slice(2);
if (args.length < 2) {
  console.error('Usage: node pack.js <zip-name> <file-or-directory> [more files/dirs]');
  process.exit(1);
}

// First argument is the base name of the output file
const zipBase = args[0].replace(/\.zip$/, '');
const targets = args.slice(1);

// Read version from package.json (current working directory)
let version = '1.0.0';
try {
  const packageJsonPath = path.join(process.cwd(), 'package.json');
  if (fs.existsSync(packageJsonPath)) {
    const packageJson = JSON.parse(fs.readFileSync(packageJsonPath, 'utf8'));
    if (packageJson.version) {
      version = packageJson.version;
    }
  } else {
    console.warn('Warning: package.json not found, using version 1.0.0');
  }
} catch (err) {
  console.warn('Warning: failed to read version from package.json, fallback to 1.0.0');
}

const zipName = `${zipBase}-${version}.zip`;
const zipPath = path.join(process.cwd(), zipName);

// Ensure targets exist
for (const target of targets) {
  const targetPath = path.resolve(process.cwd(), target);
  if (!fs.existsSync(targetPath)) {
    console.error(`Error: target ${target} not found`);
    process.exit(1);
  }
}

// Create dist directory
const distDir = path.join(process.cwd(), 'dist');
fs.mkdirSync(distDir, { recursive: true });

// Remove existing zip if present
if (fs.existsSync(zipPath)) {
  fs.unlinkSync(zipPath);
}

// Create zip archive directly from targets (no temp directory to avoid file locking issues)
async function createZip() {
  return new Promise((resolve, reject) => {
    const output = fs.createWriteStream(zipPath);
    const archive = archiver('zip', { zlib: { level: 9 } });

    output.on('error', (err) => {
      reject(err);
    });

    archive.on('error', (err) => {
      reject(err);
    });

    archive.on('warning', (err) => {
      if (err.code === 'ENOENT') {
        console.warn('Warning:', err);
      } else {
        reject(err);
      }
    });

    output.on('close', () => {
      const fileSize = archive.pointer();
      const fileSizeMB = (fileSize / 1024 / 1024).toFixed(2);
      const fileSizeKB = (fileSize / 1024).toFixed(2);

      console.log(`Creating ${zipName} with targets: ${targets.join(', ')}`);
      console.log('');
      console.log('Packaging complete!');
      console.log(`File: ${zipPath}`);
      console.log(`Size: ${fileSizeMB} MB (${fileSizeKB} KB)`);
      
      resolve();
    });

    archive.pipe(output);
    
    // Add targets directly to archive
    for (const target of targets) {
      const targetPath = path.resolve(process.cwd(), target);
      const stats = fs.statSync(targetPath);
      
      if (stats.isDirectory()) {
        // Add directory contents directly (merge behavior like pack.sh)
        const entries = fs.readdirSync(targetPath);
        for (const entry of entries) {
          const entryPath = path.join(targetPath, entry);
          const entryStats = fs.statSync(entryPath);
          if (entryStats.isDirectory()) {
            archive.directory(entryPath, entry);
          } else {
            archive.file(entryPath, { name: entry });
          }
        }
      } else {
        // Add file directly
        const targetName = path.basename(targetPath);
        archive.file(targetPath, { name: targetName });
      }
    }
    
    archive.finalize();
  });
}

// Execute packaging
(async () => {
  try {
    await createZip();
  } catch (err) {
    console.error('Packaging failed:', err);
    process.exit(1);
  }
})();

