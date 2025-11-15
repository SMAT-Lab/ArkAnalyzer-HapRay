const fs = require('fs');
const path = require('path');
const archiver = require('archiver');
const os = require('os');

const packageJson = require('../package.json');
const version = packageJson.version;

// 获取命令行参数
const args = process.argv.slice(2);
const outputFilename = path.resolve(__dirname, `../${args[0] || 'dist'}-${version}.zip`);

// 生成新的README内容
function generateNewReadme() {
    const readmePath = path.resolve(__dirname, '../README.md');
    const originalContent = fs.readFileSync(readmePath, 'utf8');
    const sections = [];

    // before ## Documentation
    const introEndIndex = originalContent.indexOf('## Documentation');
    if (introEndIndex !== -1) {
        sections.push(originalContent.substring(0, introEndIndex).trim());
    }

    // 2. "## Usage Guide"
    const usageStartIndex = originalContent.indexOf('## Usage Guide');
    const aboutFlameIndex = originalContent.indexOf('### Dependencies');
    if (usageStartIndex !== -1 && aboutFlameIndex !== -1) {
        sections.push(originalContent.substring(usageStartIndex, aboutFlameIndex).trim());
    }

    let newContent = sections.join('\n\n');
    const binaryName = os.platform() === 'win32' ? 'ArkAnalyzer-HapRay.exe' : './ArkAnalyzer-HapRay';
    newContent = newContent.replace(/python -m scripts\.main/g, binaryName);

    return newContent;
}

async function zipDistDirectory(outputPath) {
  const sourceDir = path.resolve(__dirname, '../dist');
  const output = fs.createWriteStream(outputPath);
  const archive = archiver('zip', { zlib: { level: 9 } });

  const newReadmeContent = generateNewReadme();
  const tempReadmePath = path.join(sourceDir, 'README.md');
  fs.writeFileSync(tempReadmePath, newReadmeContent);

  return new Promise((resolve, reject) => {
    output.on('error', reject);
    archive.on('error', reject);
    archive.on('warning', err => {
      if (err.code === 'ENOENT') console.warn('警告:', err);
      else reject(err);
    });

    output.on('close', () => {
      console.log(`打包完成! 输出文件: ${path.resolve(outputPath)}`);
      console.log(`文件大小: ${(archive.pointer() / 1024 / 1024).toFixed(2)} MB`);
      resolve();
    });

    archive.pipe(output);
    archive.directory(sourceDir, false); // 不包含dist目录本身
    archive.finalize();
  });
}

// 执行打包
zipDistDirectory(outputFilename)
  .catch(err => {
    console.error('打包失败:', err);
    process.exit(1); // 非零退出码表示错误
  });