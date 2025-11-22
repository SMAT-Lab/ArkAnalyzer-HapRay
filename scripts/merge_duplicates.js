const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

/**
 * 计算文件的 MD5 哈希值
 */
function calculateFileHash(filePath) {
  try {
    const buffer = fs.readFileSync(filePath);
    return crypto.createHash('md5').update(buffer).digest('hex');
  } catch (error) {
    throw new Error(`无法读取文件 ${filePath}: ${error.message}`);
  }
}

/**
 * 递归获取目录下所有文件的路径
 */
function getAllFiles(dirPath, arrayOfFiles = []) {
  try {
    const files = fs.readdirSync(dirPath);

    files.forEach(file => {
      const filePath = path.join(dirPath, file);
      
      try {
        const stat = fs.statSync(filePath);

        if (stat.isDirectory()) {
          // 跳过一些不需要处理的目录
          if (!file.startsWith('.') && file !== 'node_modules') {
            getAllFiles(filePath, arrayOfFiles);
          }
        } else if (stat.isFile()) {
          // 跳过符号链接，只处理普通文件
          // 同时跳过空文件（大小为0）
          if (!stat.isSymbolicLink() && stat.size > 0) {
            arrayOfFiles.push(filePath);
          }
        }
      } catch (statError) {
        // 如果无法获取文件状态，跳过该文件
        console.warn(`无法获取文件状态 ${filePath}:`, statError.message);
      }
    });
  } catch (error) {
    console.warn(`无法读取目录 ${dirPath}:`, error.message);
  }

  return arrayOfFiles;
}

/**
 * 合并相同的文件，使用硬链接
 */
function mergeDuplicateFiles(sourceDir) {
  console.log('开始扫描文件...');
  const allFiles = getAllFiles(sourceDir);
  console.log(`找到 ${allFiles.length} 个文件`);

  if (allFiles.length === 0) {
    console.log('没有找到需要处理的文件');
    return;
  }

  // 使用 Map 存储文件哈希 -> 文件路径数组
  const hashToFiles = new Map();

  // 计算所有文件的哈希值
  console.log('正在计算文件哈希值...');
  let processed = 0;
  for (const filePath of allFiles) {
    try {
      const hash = calculateFileHash(filePath);
      if (!hashToFiles.has(hash)) {
        hashToFiles.set(hash, []);
      }
      hashToFiles.get(hash).push(filePath);
      processed++;
      if (processed % 100 === 0) {
        console.log(`已处理 ${processed}/${allFiles.length} 个文件...`);
      }
    } catch (error) {
      console.warn(`无法处理文件 ${filePath}:`, error.message);
    }
  }

  console.log('开始合并重复文件...');
  let totalSaved = 0;
  let linksCreated = 0;
  let duplicateGroups = 0;

  // 处理每个哈希值对应的文件组
  for (const [hash, files] of hashToFiles) {
    if (files.length > 1) {
      duplicateGroups++;
      // 找到第一个文件作为源文件
      let sourceFile = files[0];
      
      // 选择路径较短的作为源文件（通常更稳定）
      for (const file of files) {
        if (file.length < sourceFile.length) {
          sourceFile = file;
        }
      }

      let sourceStat;
      try {
        sourceStat = fs.statSync(sourceFile);
      } catch (error) {
        console.warn(`无法访问源文件 ${sourceFile}:`, error.message);
        continue;
      }
      
      const fileSize = sourceStat.size;

      // 将其余文件替换为硬链接
      for (const targetFile of files) {
        if (targetFile === sourceFile) {
          continue; // 跳过源文件本身
        }
        
        try {
          // 检查目标文件是否存在且可写
          if (!fs.existsSync(targetFile)) {
            continue;
          }
          
          // 获取目标文件的 inode，如果已经是指向源文件的硬链接，跳过
          const targetStat = fs.statSync(targetFile);
          if (targetStat.ino === sourceStat.ino) {
            // 已经是同一个文件的硬链接
            continue;
          }

          // 删除原文件
          fs.unlinkSync(targetFile);
          // 创建硬链接
          fs.linkSync(sourceFile, targetFile);
          linksCreated++;
          totalSaved += fileSize;
        } catch (error) {
          // 在某些系统上硬链接可能失败（跨文件系统等），尝试恢复原文件
          if (!fs.existsSync(targetFile)) {
            try {
              fs.copyFileSync(sourceFile, targetFile);
              console.warn(`无法为 ${targetFile} 创建硬链接，已恢复原文件:`, error.message);
            } catch (copyError) {
              console.error(`无法恢复文件 ${targetFile}:`, copyError.message);
            }
          }
        }
      }
    }
  }

  console.log(`\n合并完成！`);
  console.log(`- 发现 ${duplicateGroups} 组重复文件`);
  console.log(`- 创建了 ${linksCreated} 个硬链接`);
  console.log(`- 节省了约 ${(totalSaved / 1024 / 1024).toFixed(2)} MB 的磁盘空间`);
}

// 执行合并
const distDir = path.resolve(__dirname, '../dist');
if (!fs.existsSync(distDir)) {
  console.error(`错误: dist 目录不存在: ${distDir}`);
  process.exit(1);
}

console.log(`正在处理目录: ${distDir}\n`);
mergeDuplicateFiles(distDir);

