const path = require('path');
const fs = require('fs');
const CopyPlugin = require('copy-webpack-plugin');
const archiver = require('archiver');
const { arch } = require('os');
const version = require('./package.json').version;

class PackPlugin {
    apply(compiler) {
        compiler.hooks.done.tap('PackPlugin', (stats) => {
            let dist = path.resolve(__dirname, '../perf_testing/hapray-toolbox');
            if (!fs.existsSync(dist)) {
                return;
            }

            const outputName = path.resolve(__dirname, `hapray-toolbox_v${version}.zip`);
            const outpuZipStream = fs.createWriteStream(outputName);
            const archive = archiver('zip');
            archive.pipe(outpuZipStream);

            fs.readdirSync(dist).forEach((filename) => {
                const realFile = path.resolve(dist, filename);
                if (fs.statSync(realFile).isDirectory()) {
                    archive.directory(realFile, filename);
                } else {
                    archive.file(realFile, { name: filename });
                }
            });

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
        },
        {
            'bjc': 'commonjs bjc'
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
        filename: 'hapray-cmd.js',
        path: path.resolve(__dirname, '../perf_testing/hapray-toolbox'),
    },
    plugins: [
        new CopyPlugin({
            patterns: [
                { from: 'res', to: 'res' },
                { from: '../node_modules/arkanalyzer/config/', to: 'config' },
                { from: 'README.md', to: 'README.md' },
                { from: '../third-party/trace_streamer_binary', to: 'third-party/trace_streamer_binary' },
                { from: '../third-party/xvm', to: 'third-party/xvm' },
                { from: '../third-party/report.html', to: 'res/hiperf_report_template.html' },
                {
                    from: '../web/dist/index.html',
                    to: 'res/report_template.html',
                },
                {
                    from: 'src/core/elf/demangle-wasm.wasm',
                    to: 'demangle-wasm.wasm'
                },
                // bjc
                { from: '../node_modules/bjc', to: 'node_modules/bjc'},
                { from: '../node_modules/vue', to: 'node_modules/vue'},
                { from: '../node_modules/element-plus', to: 'node_modules/element-plus'},
                { from: '../node_modules/code-prettify', to: 'node_modules/code-prettify'},
                // sql.js
                {
                    from: '../node_modules/sql.js/package.json',
                    to: 'node_modules/sql.js/package.json',
                },
                {
                    from: '../node_modules/sql.js/dist/sql-wasm.js',
                    to: 'node_modules/sql.js/dist/sql-wasm.js',
                },
                {
                    from: '../node_modules/sql.js/dist/sql-wasm.wasm',
                    to: 'node_modules/sql.js/dist/sql-wasm.wasm',
                },
                {
                    from: '../node_modules/sql.js/dist/worker.sql-wasm.js',
                    to: 'node_modules/sql.js/dist/worker.sql-wasm.js',
                },
            ],
        }),

        new PackPlugin(),
    ],
};
