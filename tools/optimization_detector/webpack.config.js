const path = require('path');
<<<<<<< HEAD
const fs = require('fs');
const CopyPlugin = require('copy-webpack-plugin');
const archiver = require('archiver');
const version = require('./package.json').version;

/**
 * 打包插件：创建 zip 文件
 */
class PackPlugin {
    constructor(options) {
        this.options = {
            zipName: options.zipName || 'opt-detector',
            sourceDir: options.sourceDir || '../../dist/tools/opt-detector',
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
                if (this.shouldSkipFile(realFile)) {
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
                        archive.directory(filePath, path.basename(file));
                    } else if (!this.shouldSkipFile(filePath))  {
                        archive.file(filePath, { name: path.basename(file) });
                    }
                }
            });

            archive.finalize();
        }).catch(err => {
            console.error('Packaging failed:', err);
        });
    }

    shouldSkipFile(filePath) {
        const skipExtensions = ['.inc', '.h', '.hpp', '.txt', '.md'];
        const skipPatterns = [
            /_internal[\\/]tensorflow[\\/]include/,
            /test|doc|example/i
        ];
        
        const ext = path.extname(filePath).toLowerCase();
        const shouldSkip = skipExtensions.includes(ext) || 
                          skipPatterns.some(pattern => pattern.test(filePath));
        
        return shouldSkip;
    }
=======
const CopyPlugin = require('copy-webpack-plugin');
const { PreservePermissionsPlugin, PackPlugin } = require('../../scripts/webpack_plugin');
const version = require('./package.json').version;

/**
 * 跳过文件的函数：用于 opt-detector 的打包过滤
 */
function shouldSkipFile(filePath) {
    const skipExtensions = ['.inc', '.h', '.hpp', '.txt', '.md'];
    const skipPatterns = [
        /_internal[\\/]tensorflow[\\/]include/,
        /test|doc|example/i
    ];
    
    const ext = path.extname(filePath).toLowerCase();
    const shouldSkip = skipExtensions.includes(ext) || 
                      skipPatterns.some(pattern => pattern.test(filePath));
    
    return shouldSkip;
>>>>>>> 685286851b1330e907ed8464027736fa2b10949e
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
                    from: path.resolve(__dirname, 'dist/opt-detector'),
                    to: path.resolve(__dirname, '../../dist/tools/opt-detector'),
                    noErrorOnMissing: true,
                },
                {
                    from: path.resolve(__dirname, 'README.md'),
                    to: path.resolve(__dirname, '../../dist/tools/opt-detector/README.md'),
                    noErrorOnMissing: true,
                },
            ],
        }),
<<<<<<< HEAD
        // 使用 PackPlugin 创建 zip 文件
        new PackPlugin({
            zipName: 'opt-detector',
            sourceDir: '../../dist/tools/opt-detector',
            additionalFiles: [
                'README.md'
            ]
=======
        // 保持文件权限插件：在文件拷贝后保持可执行权限
        new PreservePermissionsPlugin({
            mappings: [
                {
                    from: path.resolve(__dirname, 'dist/opt-detector/opt-detector'),
                    to: path.resolve(__dirname, '../../dist/tools/opt-detector/opt-detector'),
                },
            ],
        }),
        // 使用 PackPlugin 创建 zip 文件
        new PackPlugin({
            zipName: 'opt-detector',
            version: version,
            sourceDir: '../../dist/tools/opt-detector',
            additionalFiles: [
                'README.md'
            ],
            shouldSkipFile: shouldSkipFile // opt-detector 需要跳过某些文件
>>>>>>> 685286851b1330e907ed8464027736fa2b10949e
        }),
    ],
};

