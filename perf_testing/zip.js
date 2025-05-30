const fs = require('fs');
const path = require('path');
const archiver = require('archiver');

// 获取命令行参数
const args = process.argv.slice(2);
const outputFilename = args[0] || 'dist.zip'; // 使用参数或默认文件名

async function zipDistDirectory(outputPath) {
  const sourceDir = 'dist';
  const output = fs.createWriteStream(outputPath);
  const archive = archiver('zip', { zlib: { level: 9 } });

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