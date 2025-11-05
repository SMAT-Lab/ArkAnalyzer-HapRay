import { resolve } from 'path';

import { defineConfig, PluginOption } from 'vite';
import vue from '@vitejs/plugin-vue';
import vueDevTools from 'vite-plugin-vue-devtools';
import injectJson from './vite-plugin-inject-json';
import inlineDb from './vite-plugin-inline-db';
import { viteSingleFile } from 'vite-plugin-singlefile';

// https://vite.dev/config/
export default defineConfig({
  base: './',
  plugins: [vue() as PluginOption, vueDevTools() as PluginOption, injectJson, inlineDb() as PluginOption, viteSingleFile() as PluginOption],
  resolve: {
    alias: {
      '@': resolve('src'),
    },
  },
  build: {
    assetsInlineLimit: 100000000,
    chunkSizeWarningLimit: 100000000,
    cssCodeSplit: false,
    reportCompressedSize: false,
    rollupOptions: {
      input: {
        main: resolve(__dirname, 'index.html'),
        dbWorker: resolve(__dirname, 'src/dbWorker.ts'),
      },
      output: {
        inlineDynamicImports: (chunkInfo) => {
          // dbWorker 不内联，其他都内联
          return chunkInfo.name !== 'dbWorker';
        },
        entryFileNames: (chunkInfo) => {
          return chunkInfo.name === 'dbWorker' ? 'dbWorker.js' : 'assets/[name]-[hash].js';
        },
      },
    },
  },
  worker: {
    format: 'es',
    rollupOptions: {
      output: {
        entryFileNames: 'dbWorker.js',
      },
    },
  },
});
