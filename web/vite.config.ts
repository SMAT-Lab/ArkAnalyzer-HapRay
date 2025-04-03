import { resolve } from 'path';

import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';
import vueDevTools from 'vite-plugin-vue-devtools';
import injectJson from './vite-plugin-inject-json';
import { viteSingleFile } from 'vite-plugin-singlefile';

// https://vite.dev/config/
export default defineConfig({
  base: './',
  plugins: [vue(), vueDevTools(), injectJson, viteSingleFile()],
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
      output: {
        inlineDynamicImports: true
      }
    }
  },
});
