import { Plugin } from 'vite';
import fs from 'fs';
import path from 'path';

/**
 * Vite 插件：将 sql.js、pako 和 dbWorker 内联到 HTML 中
 */
export default function inlineDbPlugin(): Plugin {
  // 获取项目根目录（web 目录）
  const projectRoot = path.resolve(__dirname);
  // node_modules 在项目根目录（web 的父目录）
  const rootNodeModules = path.resolve(projectRoot, '../node_modules');
  const localNodeModules = path.resolve(projectRoot, 'node_modules');
  
  // 辅助函数：查找文件，优先在根目录的 node_modules，其次在本地 node_modules
  function findFile(...relativePaths: string[]): string | null {
    for (const relativePath of relativePaths) {
      const rootPath = path.resolve(rootNodeModules, relativePath);
      if (fs.existsSync(rootPath)) {
        return rootPath;
      }
      const localPath = path.resolve(localNodeModules, relativePath);
      if (fs.existsSync(localPath)) {
        return localPath;
      }
    }
    return null;
  }
  
  return {
    name: 'inline-db',
    transformIndexHtml: {
      order: 'post',
      handler(html, ctx) {
        // 读取 sql.js WASM 文件并转为 base64
        const wasmPath = findFile('sql.js/dist/sql-wasm.wasm');
        let wasmBase64 = '';
        if (wasmPath) {
          const wasmBuffer = fs.readFileSync(wasmPath);
          wasmBase64 = wasmBuffer.toString('base64');
        }

        // 读取 sql.js worker 文件
        const workerPath = findFile('sql.js/dist/worker.sql-wasm.js');
        let sqlWorkerCode = '';
        if (workerPath) {
          sqlWorkerCode = fs.readFileSync(workerPath, 'utf-8');
        }

        // 读取 sql.js 主文件
        const sqlJsPath = findFile('sql.js/dist/sql-wasm.js');
        let sqlJsCode = '';
        if (sqlJsPath) {
          sqlJsCode = fs.readFileSync(sqlJsPath, 'utf-8');
        }

        // 读取 pako 文件（UMD 版本）
        const pakoPath = findFile('pako/dist/pako.min.js', 'pako/dist/pako.js', 'pako/pako.min.js');
        let pakoCode = '';
        if (pakoPath) {
          pakoCode = fs.readFileSync(pakoPath, 'utf-8');
        }

        // 读取编译后的 dbWorker（需要在构建后读取）
        // 这里我们将在 generateBundle 阶段处理

        // 构建内联脚本
        let inlineScripts = `
  <script>
    // 内联 sql.js WASM 文件（base64）
    window.__sqlWasmBase64 = '${wasmBase64}';
    
    // 内联 sql.js worker 代码
    (function() {
      const sqlWorkerCode = ${JSON.stringify(sqlWorkerCode)};
      // 修改 locateFile 以使用内联的 WASM
      const modifiedCode = sqlWorkerCode.replace(
        /locateFile:\s*function\s*\([^)]*\)\s*\{[^}]*\}/,
        \`locateFile: function(file) {
          if (file === 'sql-wasm.wasm') {
            const wasmBase64 = window.__sqlWasmBase64;
            const binaryString = atob(wasmBase64);
            const bytes = new Uint8Array(binaryString.length);
            for (let i = 0; i < binaryString.length; i++) {
              bytes[i] = binaryString.charCodeAt(i);
            }
            return URL.createObjectURL(new Blob([bytes], { type: 'application/wasm' }));
          }
          return 'https://sql.js.org/dist/' + file;
        }\`
      );
      window.__sqlWorkerCode = modifiedCode;
    })();
    
    // 内联 sql.js 主文件
    window.__sqlJsCode = ${JSON.stringify(sqlJsCode)};
    
    // 内联 pako
    window.__pakoCode = ${JSON.stringify(pakoCode)};
  </script>`;

        // 将内联脚本插入到 </head> 之前
        html = html.replace('</head>', `${inlineScripts}\n</head>`);

        // 添加 db 文件占位符（如果还没有）
        if (!html.includes('DB_DATA_PLACEHOLDER')) {
          const scriptMatch = html.match(/<script[^>]*>([\s\S]*?window\.compareMark[^;]*;[\s\S]*?)<\/script>/);
          if (scriptMatch) {
            html = html.replace(
              scriptMatch[0],
              scriptMatch[0].replace(
                'window.compareMark',
                `window.dbData = 'DB_DATA_PLACEHOLDER';\n    window.compareMark`
              )
            );
          }
        }

        return html;
      },
    },
    generateBundle(options, bundle) {
      // 在构建完成后，查找 dbServiceWorker 的 bundle 并内联
      const dbWorkerFile = Object.keys(bundle).find((fileName) => 
        (fileName.includes('dbServiceWorker') || fileName.includes('dbWorker')) && fileName.endsWith('.js')
      );
      
      if (dbWorkerFile && bundle[dbWorkerFile].type === 'chunk') {
        const dbWorkerCode = (bundle[dbWorkerFile] as any).code;
        // 将 dbWorker 代码存储到全局变量中
        const dbWorkerScript = `
  <script>
    // 内联 dbWorker 代码
    window.__dbWorkerCode = ${JSON.stringify(dbWorkerCode)};
  </script>`;
        
        // 这里需要在 HTML 生成后添加，所以我们在 transformIndexHtml 中处理
        // 但 transformIndexHtml 在 generateBundle 之前执行
        // 所以我们需要在 writeBundle 阶段处理
      }
    },
    writeBundle(options, bundle) {
      // 在文件写入后，修改 HTML 文件
      // 注意：如果使用了 vite-plugin-singlefile，HTML 文件可能已经被处理
      // 我们需要找到最终输出的 HTML 文件
      const outputDir = options.dir || path.resolve(projectRoot, 'dist');
      const htmlFile = path.resolve(outputDir, 'index.html');
      
      if (fs.existsSync(htmlFile)) {
        let html = fs.readFileSync(htmlFile, 'utf-8');
        
        // 查找 dbServiceWorker bundle
        const dbWorkerFile = Object.keys(bundle).find((fileName) => 
          (fileName.includes('dbServiceWorker') || fileName.includes('dbWorker')) && fileName.endsWith('.js')
        );
        
        if (dbWorkerFile && bundle[dbWorkerFile].type === 'chunk') {
          // 读取编译后的 dbWorker 文件内容
          const dbWorkerFilePath = path.resolve(outputDir, dbWorkerFile);
          let dbWorkerCode = '';
          
          if (fs.existsSync(dbWorkerFilePath)) {
            dbWorkerCode = fs.readFileSync(dbWorkerFilePath, 'utf-8');
            
            // 将 dbWorker 代码内联到 HTML
            const dbWorkerScript = `
  <script>
    // 内联 dbWorker 代码
    window.__dbWorkerCode = ${JSON.stringify(dbWorkerCode)};
  </script>`;
            
            // 在 </head> 之前插入（如果还没有）
            if (!html.includes('__dbWorkerCode')) {
              html = html.replace('</head>', `${dbWorkerScript}\n</head>`);
            }
            
            // 删除 dbWorker 的 script 标签引用（如果存在）
            html = html.replace(new RegExp(`<script[^>]*src=["'].*${dbWorkerFile.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}["'][^>]*></script>`, 'g'), '');
            
            fs.writeFileSync(htmlFile, html, 'utf-8');
            
            // 可选：删除 dbWorker.js 文件（因为已经内联到 HTML）
            // fs.unlinkSync(dbWorkerFilePath);
          }
        }
      }
    },
  };
}

