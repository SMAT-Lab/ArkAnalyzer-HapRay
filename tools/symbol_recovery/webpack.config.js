const path = require('path');
const fs = require('fs');
const CopyPlugin = require('copy-webpack-plugin');
const archiver = require('archiver');
const AdmZip = require('adm-zip');
const version = require('./package.json').version;

/**
 * 打包插件：创建 zip 文件
 */
class PackPlugin {
    constructor(options) {
        this.options = {
            zipName: options.zipName || 'symbol-recovery',
            sourceDir: options.sourceDir || '../../dist/tools/symbol-recovery',
            additionalFiles: options.additionalFiles || [],
            ...options
        };
    }

    apply(compiler) {
        compiler.hooks.done.tap('PackPlugin', (stats) => {
            const sourcePath = path.resolve(__dirname, this.options.sourceDir);
            const zipName = `${this.options.zipName}-${version}.zip`;
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
                if (fs.statSync(realFile).isDirectory()) {
                    archive.directory(realFile, filename);
                } else {
                    archive.file(realFile, { name: filename });
                }
            });

            // 添加额外文件（按照原始 pack.js 的行为：目录内容直接添加到 zip 根目录）
            this.options.additionalFiles.forEach(file => {
                const filePath = path.resolve(__dirname, file);
                if (fs.existsSync(filePath)) {
                    const stats = fs.statSync(filePath);
                    if (stats.isDirectory()) {
                        // 目录内容直接添加到 zip 根目录（merge 行为，类似原始 pack.js）
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
                        archive.file(filePath, { name: path.basename(file) });
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
    target: 'node',
    mode: 'production',
    entry: './webpack-entry.js', // 虚拟入口文件
    output: {
        filename: 'bundle.js',
        path: path.resolve(__dirname, 'dist'),
    },
    plugins: [
        // 使用 CopyPlugin 拷贝文件到 dist/tools 目录
        new CopyPlugin({
            patterns: [
                {
                    from: path.resolve(__dirname, 'dist/symbol-recovery'),
                    to: path.resolve(__dirname, '../../dist/tools/symbol-recovery'),
                    noErrorOnMissing: true,
                },
                {
                    from: path.resolve(__dirname, 'README.md'),
                    to: path.resolve(__dirname, '../../dist/tools/symbol-recovery/README.md'),
                    noErrorOnMissing: true,
                },
            ],
        }),
        // 使用 PackPlugin 创建 zip 文件
        new PackPlugin({
            zipName: 'symbol-recovery',
            sourceDir: 'dist/symbol-recovery',
            additionalFiles: [
                '../../dist/tools/trace_streamer_binary',
                'README.md'
            ]
        }),
    ],
};

