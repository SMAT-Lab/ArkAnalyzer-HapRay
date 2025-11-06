import { resolve } from 'path';

import { defineConfig, PluginOption } from 'vite';
import vue from '@vitejs/plugin-vue';
import vueDevTools from 'vite-plugin-vue-devtools';
import inlineDb from './vite-plugin-inline-db';
import resolveNodeModules from './vite-plugin-resolve-node-modules';
import { viteSingleFile } from 'vite-plugin-singlefile';
import injectData from './vite-plugin-inject-data';

// https://vite.dev/config/
export default defineConfig({
  base: './',
  // 插件执行顺序：injectData 必须在最后执行（在 vite-plugin-singlefile 之后）
  plugins: [
    vue() as PluginOption,
    vueDevTools() as PluginOption,
    resolveNodeModules() as PluginOption,
    inlineDb() as PluginOption,
    viteSingleFile() as PluginOption,
    injectData() as PluginOption, // 最后执行，替换占位符
  ],
  resolve: {
    alias: {
      '@': resolve('src'),
    },
  },
  build: {
    // 仅在开发环境关闭 minify，生产环境启用压缩
    minify: process.env.NODE_ENV === 'development' ? false : 'esbuild',
    assetsInlineLimit: 100000000,
    chunkSizeWarningLimit: 100000000,
    cssCodeSplit: false,
    reportCompressedSize: false,
    rollupOptions: {
      input: resolve(__dirname, 'index.html'),
      output: {
        entryFileNames: 'assets/[name]-[hash].js',
      },
    },
  },
  worker: {
    format: 'es',
    rollupOptions: {
      output: {
        entryFileNames: 'dbServiceWorker.js',
      },
    },
  },
});
