import { Plugin } from 'vite';
import { resolve } from 'path';

/**
 * Vite 插件：替换浏览器环境中不需要的 Node.js 模块
 * 用于消除 sql.js 等库在浏览器环境中的警告
 */
export default function resolveNodeModulesPlugin(): Plugin {
  const emptyModulePath = resolve(__dirname, 'src/utils/empty-module.ts');
  
  return {
    name: 'resolve-node-modules',
    resolveId(id) {
      // 当 sql.js 或其他库尝试导入 Node.js 内置模块时，替换为空模块
      if (id === 'fs' || id === 'path' || id === 'crypto') {
        return emptyModulePath;
      }
    },
  };
}

