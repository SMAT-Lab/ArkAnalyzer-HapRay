const path = require('path');
const fs = require('fs');
const CopyPlugin = require('copy-webpack-plugin');
const archiver = require('archiver');
const { arch } = require('os');
const version = require('./package.json').version;

class PackPlugin {
    apply(compiler) {
        compiler.hooks.done.tap('PackPlugin', (stats) => {
            let dist = path.resolve(__dirname, 'dist');
            if (!fs.existsSync(dist)) {
                return;
            }

            const outputName = path.resolve(__dirname, `Hapray-Toolbox_V${version}.zip`);
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
        path: path.resolve(__dirname, 'dist'),
    },
    plugins: [
        new CopyPlugin({
            patterns: [
                { from: 'res', to: 'res' },
                { from: 'README.md', to: 'README.md' },
                { from: '../third-party/trace_streamer_binary', to: 'third-party/trace_streamer_binary' },
                { from: '../node_modules/arkanalyzer/config/', to: 'config' },
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
                {
                    from: '../web/dist/index.html',
                    to: 'res/report_template.html',
                },
            ],
        }),

        new PackPlugin(),
    ],
};
