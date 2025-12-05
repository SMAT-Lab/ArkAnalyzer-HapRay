const path = require('path');
const fs = require('fs');
const archiver = require('archiver');

/**
 * 保持文件权限插件：在文件拷贝后保持可执行权限
 */
class PreservePermissionsPlugin {
    constructor(options = {}) {
        this.options = {
            // 源目录到目标目录的映射
            mappings: options.mappings || [],
            ...options
        };
    }

    apply(compiler) {
        compiler.hooks.afterEmit.tapAsync('PreservePermissionsPlugin', (compilation, callback) => {
            // 处理每个映射
            this.options.mappings.forEach(mapping => {
                const { from: sourcePath, to: targetPath } = mapping;
                
                if (!fs.existsSync(sourcePath)) {
                    return;
                }

                const sourceStats = fs.statSync(sourcePath);
                
                if (sourceStats.isDirectory()) {
                    // 如果是目录，递归处理
                    if (!fs.existsSync(targetPath)) {
                        return;
                    }
                    
                    const processDirectory = (srcPath, dstPath) => {
                        if (!fs.existsSync(srcPath)) {
                            return;
                        }

                        let stats;
                        try {
                            // 使用 lstat 来检测符号链接（不跟随）
                            stats = fs.lstatSync(srcPath);
                        } catch (err) {
                            return;
                        }
                        
                        if (stats.isSymbolicLink()) {
                            // 如果是符号链接，确保目标目录中也有相同的符号链接
                            try {
                                // 读取源符号链接的目标
                                const linkTarget = fs.readlinkSync(srcPath);
                                
                                // 检查目标路径是否存在
                                if (fs.existsSync(dstPath)) {
                                    const targetStats = fs.lstatSync(dstPath);
                                    // 如果目标不是符号链接，或者目标不同，需要替换
                                    if (!targetStats.isSymbolicLink() || fs.readlinkSync(dstPath) !== linkTarget) {
                                        // 删除目标文件/目录
                                        const dstStats = fs.statSync(dstPath);
                                        if (dstStats.isDirectory()) {
                                            fs.rmSync(dstPath, { recursive: true, force: true });
                                        } else {
                                            fs.unlinkSync(dstPath);
                                        }
                                        // 创建符号链接
                                        fs.symlinkSync(linkTarget, dstPath);
                                        console.log(`Preserved symlink: ${path.relative(targetPath, dstPath)} -> ${linkTarget}`);
                                    }
                                } else {
                                    // 如果目标不存在，直接创建符号链接
                                    // 确保父目录存在
                                    const parentDir = path.dirname(dstPath);
                                    if (!fs.existsSync(parentDir)) {
                                        fs.mkdirSync(parentDir, { recursive: true });
                                    }
                                    fs.symlinkSync(linkTarget, dstPath);
                                    console.log(`Created symlink: ${path.relative(targetPath, dstPath)} -> ${linkTarget}`);
                                }
                            } catch (err) {
                                console.warn(`Failed to preserve symlink for ${dstPath}:`, err.message);
                            }
                        } else if (stats.isDirectory()) {
                            // 如果是目录，递归处理
                            if (fs.existsSync(dstPath) && fs.statSync(dstPath).isDirectory()) {
                                const entries = fs.readdirSync(srcPath);
                                entries.forEach(entry => {
                                    processDirectory(
                                        path.join(srcPath, entry),
                                        path.join(dstPath, entry)
                                    );
                                });
                            }
                        } else if (stats.isFile()) {
                            // 如果是文件，保持权限
                            if (fs.existsSync(dstPath)) {
                                try {
                                    const sourceMode = stats.mode;
                                    const targetStats = fs.lstatSync(dstPath);
                                    
                                    // 只有当权限不同时才设置（且目标不是符号链接）
                                    if (!targetStats.isSymbolicLink() && targetStats.mode !== sourceMode) {
                                        fs.chmodSync(dstPath, sourceMode);
                                        console.log(`Preserved permissions for: ${path.relative(targetPath, dstPath)} (mode: ${sourceMode.toString(8)})`);
                                    }
                                } catch (err) {
                                    console.warn(`Failed to preserve permissions for ${dstPath}:`, err.message);
                                }
                            }
                        }
                    };

                    // 开始处理目录
                    processDirectory(sourcePath, targetPath);
                } else if (sourceStats.isFile()) {
                    // 如果是单个文件，直接处理
                    if (fs.existsSync(targetPath)) {
                        try {
                            const sourceMode = sourceStats.mode;
                            const targetStats = fs.statSync(targetPath);
                            
                            // 只有当权限不同时才设置
                            if (targetStats.mode !== sourceMode) {
                                fs.chmodSync(targetPath, sourceMode);
                                console.log(`Preserved permissions for: ${path.basename(targetPath)} (mode: ${sourceMode.toString(8)})`);
                            }
                        } catch (err) {
                            console.warn(`Failed to preserve permissions for ${targetPath}:`, err.message);
                        }
                    }
                }
            });

            callback();
        });
    }
}

/**
 * 打包插件：创建 zip 文件
 */
class PackPlugin {
    constructor(options) {
        this.options = {
            zipName: options.zipName || 'pack',
            sourceDir: options.sourceDir || '',
            additionalFiles: options.additionalFiles || [],
            shouldSkipFile: options.shouldSkipFile || null, // 可选的跳过文件函数
            mergeAdditionalDirectories: options.mergeAdditionalDirectories || false, // 是否合并目录内容到 zip 根目录
            ...options
        };
    }

    apply(compiler) {
        compiler.hooks.done.tap('PackPlugin', (stats) => {
            const sourcePath = path.resolve(__dirname, this.options.sourceDir);
            const zipName = `${this.options.zipName}-${this.options.version}.zip`;
            const zipPath = path.resolve(__dirname, zipName);

            // 检查源目录是否存在
            if (!fs.existsSync(sourcePath)) {
                console.warn(`Warning: Source directory not found: ${sourcePath}`);
                return;
            }

            // 创建 zip 文件
            this.createZip(sourcePath, zipPath, zipName);
        });
    }

    createZip(sourcePath, zipPath, zipName) {
        return new Promise((resolve, reject) => {
            // 删除已存在的 zip 文件
            if (fs.existsSync(zipPath)) {
                fs.unlinkSync(zipPath);
            }

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

                console.log(`\nPackaging complete!`);
                console.log(`File: ${zipPath}`);
                console.log(`Size: ${fileSizeMB} MB (${fileSizeKB} KB)`);
                resolve();
            });

            archive.pipe(output);

            // 添加源目录内容到 zip 根目录
            fs.readdirSync(sourcePath).forEach((filename) => {
                const realFile = path.resolve(sourcePath, filename);
                if (this.options.shouldSkipFile && this.options.shouldSkipFile(realFile)) {
                    return;
                }
                if (fs.statSync(realFile).isDirectory()) {
                    archive.directory(realFile, filename);
                } else {
                    archive.file(realFile, { name: filename });
                }
            });

            // 添加额外文件
            this.options.additionalFiles.forEach(file => {
                const filePath = path.resolve(__dirname, file);
                if (fs.existsSync(filePath)) {
                    const stats = fs.statSync(filePath);
                    if (stats.isDirectory()) {
                        if (this.options.mergeAdditionalDirectories) {
                            // 目录内容直接添加到 zip 根目录（merge 行为）
                            const entries = fs.readdirSync(filePath);
                            for (const entry of entries) {
                                const entryPath = path.join(filePath, entry);
                                const entryStats = fs.statSync(entryPath);
                                if (entryStats.isDirectory()) {
                                    archive.directory(entryPath, entry);
                                } else {
                                    archive.file(entryPath, { name: entry });
                                }
                            }
                        } else {
                            // 保持目录结构
                            archive.directory(filePath, path.basename(file));
                        }
                    } else {
                        if (!this.options.shouldSkipFile || !this.options.shouldSkipFile(filePath)) {
                            archive.file(filePath, { name: path.basename(file) });
                        }
                    }
                }
            });

            archive.finalize();
        }).catch(err => {
            console.error('Packaging failed:', err);
        });
    }
}

module.exports = {
    PreservePermissionsPlugin,
    PackPlugin
};

