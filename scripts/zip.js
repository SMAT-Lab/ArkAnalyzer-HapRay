const fs = require('fs');
const path = require('path');
const archiver = require('archiver');
const os = require('os');
const { execSync } = require('child_process');

const packageJson = require('../package.json');
const version = packageJson.version;

// 获取平台和架构信息
function getPlatformName() {
  const platform = os.platform();
  // 标准化平台名称
  const platformMap = {
    'darwin': 'darwin',
    'win32': 'win32',
    'linux': 'linux'
  };
  return platformMap[platform] || platform;
}

function getArchName() {
  const arch = os.arch();
  // 标准化架构名称
  const archMap = {
    'x64': 'x64',
    'arm64': 'arm64',
    'ia32': 'ia32',
    'arm': 'arm'
  };
  return archMap[arch] || arch;
}

// 获取命令行参数
const args = process.argv.slice(2);
const platform = getPlatformName();
const arch = getArchName();
const outputFilename = path.resolve(__dirname, `../${args[0] || 'dist'}-${platform}-${arch}-${version}.zip`);

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

async function signBinaries(distDir) {
  // 仅在 macOS 上执行代码签名
  if (os.platform() === 'darwin') {
    console.log('正在签名二进制文件...');
    const signScript = path.resolve(__dirname, 'sign_binaries.sh');
    try {
      // 传递 dist 目录的绝对路径给脚本
      execSync(`bash "${signScript}" "${distDir}"`, { stdio: 'inherit' });
      console.log('代码签名完成');
    } catch (error) {
      console.warn('警告: 代码签名失败，继续打包:', error.message);
    }
  }
}

async function zipDistDirectory(outputPath) {
  const sourceDir = path.resolve(__dirname, '../dist');
  
  // 在打包前执行代码签名（仅 macOS）
  await signBinaries(sourceDir);
  
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