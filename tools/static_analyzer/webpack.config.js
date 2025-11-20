const path = require('path');
const fs = require('fs');
const CopyPlugin = require('copy-webpack-plugin');
const archiver = require('archiver');
const AdmZip = require('adm-zip');
const { arch } = require('os');
const version = require('./package.json').version;

class PackPlugin {
    apply(compiler) {
        compiler.hooks.done.tap('PackPlugin', (stats) => {
            let dist = path.resolve(__dirname, '../../dist/tools/sa-cmd');
            if (!fs.existsSync(dist)) {
                return;
            }

            const outputName = path.resolve(__dirname, `hapray-sa_v${version}.zip`);
            const outpuZipStream = fs.createWriteStream(outputName);
            const archive = archiver('zip');
            archive.pipe(outpuZipStream);

            // 打包 sa-cmd 目录内容到根目录
            fs.readdirSync(dist).forEach((filename) => {
                const realFile = path.resolve(dist, filename);
                if (fs.statSync(realFile).isDirectory()) {
                    archive.directory(realFile, filename);
                } else {
                    archive.file(realFile, { name: filename });
                }
            });

            // 解压 trace_streamer_binary.zip 并打包到 tools 目录
            const traceStreamerZipPath = path.resolve(__dirname, '../../third-party/trace_streamer_binary.zip');
            if (fs.existsSync(traceStreamerZipPath)) {
                try {
                    const zip = new AdmZip(traceStreamerZipPath);
                    const zipEntries = zip.getEntries();
                    
                    zipEntries.forEach((entry) => {
                        if (!entry.isDirectory) {
                            const entryPath = entry.entryName;
                            const content = zip.readFile(entry);
                            // 将文件添加到 tools/ 目录下
                            archive.append(content, { name: `tools/${entryPath}` });
                        }
                    });
                } catch (error) {
                    console.error('Failed to extract trace_streamer_binary.zip:', error);
                }
            }

            archive.finalize();
        });
    }
}

module.exports = {
    target: 'node',
    mode: 'production',
    externals: [
        {
            'sql.js': 'commonjs sql.js',
        }
    ],
    entry: './src/cli/index.ts',
    module: {
        rules: [
            {
                test: /\.tsx?$/,
                use: 'ts-loader',
                exclude: /node_modules/,
            },
        ],
    },
    resolve: {
        extensions: ['.tsx', '.ts', '.js'],
    },
    output: {
        filename: 'hapray-sa-cmd.js',
        path: path.resolve(__dirname, '../../dist/tools/sa-cmd'),
    },
    plugins: [
        new CopyPlugin({
            patterns: [
                { from: 'res', to: 'res' },
                { from: '../../node_modules/bjc/res', to: 'res'},
                { from: '../../node_modules/arkanalyzer/config/', to: 'config' },
                { from: 'README.md', to: 'README.md' },
                {
                    from: 'src/core/elf/demangle-wasm.wasm',
                    to: 'demangle-wasm.wasm'
                },
                // sql.js
                {
                    from: '../../node_modules/sql.js/package.json',
                    to: 'node_modules/sql.js/package.json',
                },
                {
                    from: '../../node_modules/sql.js/dist/sql-wasm.js',
                    to: 'node_modules/sql.js/dist/sql-wasm.js',
                },
                {
                    from: '../../node_modules/sql.js/dist/sql-wasm.wasm',
                    to: 'node_modules/sql.js/dist/sql-wasm.wasm',
                },
                {
                    from: '../../node_modules/sql.js/dist/worker.sql-wasm.js',
                    to: 'node_modules/sql.js/dist/worker.sql-wasm.js',
                },
            ],
        }),

        new PackPlugin(),
    ],
};
