import { resolve } from 'path';

import { defineConfig, PluginOption } from 'vite';
import vue from '@vitejs/plugin-vue';
import vueDevTools from 'vite-plugin-vue-devtools';
import injectJson from './vite-plugin-inject-json';
import inlineDb from './vite-plugin-inline-db';
import resolveNodeModules from './vite-plugin-resolve-node-modules';
import { viteSingleFile } from 'vite-plugin-singlefile';

// https://vite.dev/config/
export default defineConfig({
  base: './',
  plugins: [vue() as PluginOption, vueDevTools() as PluginOption, resolveNodeModules() as PluginOption, injectJson, inlineDb() as PluginOption, viteSingleFile() as PluginOption],
  resolve: {
    alias: {
      '@': resolve('src'),
    },
  },
  optimizeDeps: {
    exclude: ['sql.js'],
  },
  build: {
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
