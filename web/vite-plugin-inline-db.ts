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
        // 注意：sql.js 和 pako 会在构建时自动打包到 dbServiceWorker.js 中，不需要单独内联
        // 只需要内联 WASM 文件，因为 Worker 中需要用它来初始化 sql.js
        const wasmPath = findFile('sql.js/dist/sql-wasm.wasm');
        let wasmBase64 = '';
        if (wasmPath) {
          const wasmBuffer = fs.readFileSync(wasmPath);
          wasmBase64 = wasmBuffer.toString('base64');
        }

        // 构建内联脚本
        // 只内联 WASM 文件，sql.js 和 pako 已经在 dbServiceWorker.js 中打包
        // 将内联脚本插入到 </head> 之前
        html = html.replace('SQL_WASM_BASE64_PLACEHOLDER', wasmBase64);
        return html;
      },
    },
    
     closeBundle() {
       // 在所有构建完成后，替换 DB_WORKER_CODE_PLACEHOLDER
       // 这个钩子在 vite-plugin-singlefile 处理之后执行
       const outputDir = path.resolve(projectRoot, 'dist');
       const htmlFile = path.resolve(outputDir, 'index.html');
       
       console.log('[inline-db] closeBundle - checking HTML file:', htmlFile);
       console.log('[inline-db] closeBundle - HTML file exists:', fs.existsSync(htmlFile));
       
       if (fs.existsSync(htmlFile)) {
         let html = fs.readFileSync(htmlFile, 'utf-8');
         
         // 检查是否包含占位符
         const hasPlaceholder = html.includes('DB_WORKER_CODE_PLACEHOLDER');
         console.log('[inline-db] closeBundle - HTML contains DB_WORKER_CODE_PLACEHOLDER:', hasPlaceholder);
         
         if (hasPlaceholder) {
             // 如果 writeBundle 中没有保存，尝试从文件系统读取
             const dbWorkerFile = 'dbServiceWorker.js';
             const dbWorkerFilePath = path.resolve(outputDir, dbWorkerFile);
             
             if (fs.existsSync(dbWorkerFilePath)) {
               const code = fs.readFileSync(dbWorkerFilePath, 'utf-8');
               html = html.replace(
                 'DB_WORKER_CODE_PLACEHOLDER',
                 code
               );
               fs.writeFileSync(htmlFile, html, 'utf-8');
               console.log('[inline-db] closeBundle - ✅ 从文件系统读取并替换 DB_WORKER_CODE_PLACEHOLDER');
             } else {
               console.warn('[inline-db] closeBundle - ⚠️ dbServiceWorker.js 文件未找到，且 writeBundle 中未保存代码');
               console.warn('[inline-db] closeBundle - 文件路径:', dbWorkerFilePath);
               // 列出 dist 目录中的所有文件
               if (fs.existsSync(outputDir)) {
                 const files = fs.readdirSync(outputDir);
                 console.log('[inline-db] closeBundle - dist 目录中的文件:', files);
               }
             }
           
         } else {
           // 检查是否已经包含实际的代码（不是占位符）
           const hasActualCode = html.includes('window.__dbWorkerCode') && 
                                 !html.includes('DB_WORKER_CODE_PLACEHOLDER');
           if (hasActualCode) {
             console.log('[inline-db] closeBundle - __dbWorkerCode 已存在实际代码，跳过');
           } else {
             console.log('[inline-db] closeBundle - 未找到 DB_WORKER_CODE_PLACEHOLDER，可能已被其他插件处理');
           }
         }
       } else {
         console.warn('[inline-db] closeBundle - HTML 文件不存在:', htmlFile);
       }
     },
  };
}

