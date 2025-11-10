import { resolve } from 'path';

import { defineConfig, PluginOption } from 'vite';
import vue from '@vitejs/plugin-vue';
import vueDevTools from 'vite-plugin-vue-devtools';
import inlineDb from './vite-plugin-inline-db';
import { viteSingleFile } from 'vite-plugin-singlefile';
import injectData from './vite-plugin-inject-data';

// https://vite.dev/config/
export default defineConfig({
  base: './',
  plugins: [
    vue() as PluginOption,
    vueDevTools() as PluginOption,
    viteSingleFile() as PluginOption, // Process single file first (inline all assets)
    inlineDb() as PluginOption, // Then replace placeholders (must be after viteSingleFile)
    injectData() as PluginOption, // Finally inject data in development
  ],
  resolve: {
    alias: {
      '@': resolve('src'),
    },
  },
  build: {
    minify: process.env.NODE_ENV === 'development' ? false : 'esbuild',
    assetsInlineLimit: 100000000,
    chunkSizeWarningLimit: 100000000,
    cssCodeSplit: false,
    reportCompressedSize: false,
    rollupOptions: {
      output: {
        inlineDynamicImports: true,
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
