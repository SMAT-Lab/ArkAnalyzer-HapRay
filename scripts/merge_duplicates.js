const fs = require("fs");
const path = require("path");
const crypto = require("crypto");

/**
 * 计算文件的 MD5 哈希值，支持符号链接
 */
function calculateFileHash(filePath) {
  try {
    const stat = fs.lstatSync(filePath);
    if (stat.isSymbolicLink()) {
      // 对于符号链接，读取链接目标的内容
      const targetPath = fs.readlinkSync(filePath);
      const resolvedPath = path.resolve(path.dirname(filePath), targetPath);
      const buffer = fs.readFileSync(resolvedPath);
      return crypto.createHash("md5").update(buffer).digest("hex");
    } else {
      // 对于普通文件，直接读取内容
      const buffer = fs.readFileSync(filePath);
      return crypto.createHash("md5").update(buffer).digest("hex");
    }
  } catch (error) {
    throw new Error(`无法读取文件 ${filePath}: ${error.message}`);
  }
}

/**
 * 递归获取目录下所有文件的路径，包括符号链接
 */
function getAllFiles(dirPath, arrayOfFiles = []) {
  try {
    const files = fs.readdirSync(dirPath);

    files.forEach((file) => {
      const filePath = path.join(dirPath, file);

      try {
        const stat = fs.lstatSync(filePath); // 使用 lstat 而不是 stat 来获取符号链接本身的状态

        if (stat.isDirectory()) {
          // 跳过一些不需要处理的目录
          if (!file.startsWith(".") && file !== "node_modules") {
            getAllFiles(filePath, arrayOfFiles);
          }
        } else if (stat.isFile() || stat.isSymbolicLink()) {
          // 处理普通文件和符号链接，但跳过空文件（大小为0）
          if (stat.size > 0) {
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
  console.log("开始扫描文件...");
  const allFiles = getAllFiles(sourceDir);
  console.log(`找到 ${allFiles.length} 个文件`);

  if (allFiles.length === 0) {
    console.log("没有找到需要处理的文件");
    return;
  }

  // 使用 Map 存储文件哈希 -> 文件路径数组
  const hashToFiles = new Map();

  // 计算所有文件的哈希值
  console.log("正在计算文件哈希值...");
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

  console.log("开始合并重复文件...");
  let totalSaved = 0;
  let linksCreated = 0;
  let duplicateGroups = 0;

  // 处理每个哈希值对应的文件组
  for (const [hash, files] of hashToFiles) {
    if (files.length > 1) {
      duplicateGroups++;

      // 分类文件：符号链接和普通文件
      const symlinks = [];
      const regularFiles = [];

      for (const file of files) {
        try {
          const stat = fs.lstatSync(file);
          if (stat.isSymbolicLink()) {
            symlinks.push(file);
          } else {
            regularFiles.push(file);
          }
        } catch (error) {
          console.warn(`无法获取文件类型 ${file}:`, error.message);
        }
      }

      // 选择源文件：优先选择普通文件，其次选择符号链接
      let sourceFile;
      if (regularFiles.length > 0) {
        // 在普通文件中选择路径较短的
        sourceFile = regularFiles[0];
        for (const file of regularFiles) {
          if (file.length < sourceFile.length) {
            sourceFile = file;
          }
        }
      } else if (symlinks.length > 0) {
        // 在符号链接中选择路径较短的
        sourceFile = symlinks[0];
        for (const file of symlinks) {
          if (file.length < sourceFile.length) {
            sourceFile = file;
          }
        }
      } else {
        continue; // 没有有效文件
      }

      let sourceStat;
      try {
        sourceStat = fs.statSync(sourceFile);
      } catch (error) {
        console.warn(`无法访问源文件 ${sourceFile}:`, error.message);
        continue;
      }

      const fileSize = sourceStat.size;

      // 将其余文件替换为硬链接或更新符号链接
      for (const targetFile of files) {
        if (targetFile === sourceFile) {
          continue; // 跳过源文件本身
        }

        try {
          // 检查目标文件是否存在
          if (!fs.existsSync(targetFile)) {
            continue;
          }

          // 获取目标文件的状态信息
          const targetStat = fs.lstatSync(targetFile);

          // 统一使用硬链接处理所有文件（包括符号链接）

          // 检查目标文件是否已经是源文件的硬链接
          let targetIno;
          if (targetStat.isSymbolicLink()) {
            // 对于符号链接，解析到实际文件并检查其inode
            const targetLink = fs.readlinkSync(targetFile);
            const resolvedTarget = path.resolve(path.dirname(targetFile), targetLink);
            try {
              const resolvedStat = fs.statSync(resolvedTarget);
              targetIno = resolvedStat.ino;
            } catch (error) {
              // 如果解析失败，使用符号链接本身的inode
              targetIno = targetStat.ino;
            }
          } else {
            // 对于普通文件，直接使用其inode
            targetIno = fs.statSync(targetFile).ino;
          }

          if (targetIno === sourceStat.ino) {
            // 已经是同一个文件的硬链接
            console.log(`[跳过] ${targetFile} 已是 ${sourceFile} 的硬链接`);
            continue;
          }

          // 删除原文件（包括符号链接）并创建硬链接
          const originalType = targetStat.isSymbolicLink() ? '符号链接' : '普通文件';
          fs.unlinkSync(targetFile);
          fs.linkSync(sourceFile, targetFile);
          console.log(`[硬链接] 创建硬链接: ${targetFile}`);
          console.log(`  └─ 原类型: ${originalType}`);
          console.log(`  └─ 指向: ${sourceFile}`);
          console.log(`  └─ 节省: ${fileSize} 字节`);
          console.log(`  └─ inode: ${sourceStat.ino}`);
          linksCreated++;
          totalSaved += fileSize;
        } catch (error) {
          console.error(`[错误] 无法创建硬链接 ${targetFile}:`, error.message);
          console.error(`[错误] 源文件: ${sourceFile}`);
          // 尝试恢复原文件
          try {
            if (!fs.existsSync(targetFile)) {
              fs.copyFileSync(sourceFile, targetFile);
              console.warn(`[恢复] 已通过复制恢复文件 ${targetFile}`);
            } else {
              console.warn(`[跳过] 文件 ${targetFile} 仍然存在，无需恢复`);
            }
          } catch (copyError) {
            console.error(`[恢复失败] 无法恢复文件 ${targetFile}:`, copyError.message);
          }
        }
      }
    }
  }

  console.log(`\n合并完成！`);
  console.log(`- 发现 ${duplicateGroups} 组重复文件`);
  console.log(`- 创建了 ${linksCreated} 个硬链接`);
  console.log(
    `- 节省了约 ${(totalSaved / 1024 / 1024).toFixed(2)} MB 的磁盘空间`
  );
}

// 执行合并
const distDir = path.resolve(__dirname, "../dist");
if (!fs.existsSync(distDir)) {
  console.error(`错误: dist 目录不存在: ${distDir}`);
  process.exit(1);
}

console.log(`正在处理目录: ${distDir}\n`);
mergeDuplicateFiles(distDir);
