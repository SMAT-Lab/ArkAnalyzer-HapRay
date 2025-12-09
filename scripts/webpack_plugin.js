const path = require('path');
const fs = require('fs');
const archiver = require('archiver');

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
    PackPlugin
};

