/**
 * Vite Plugin: Inline sql.js WASM and dbWorker code into HTML
 * 
 * This plugin inlines database-related assets into the HTML file:
 * - Converts sql.js WASM file to base64 and replaces SQL_WASM_BASE64_PLACEHOLDER
 * - Reads dbServiceWorker.js, encodes it as base64, and replaces DB_WORKER_CODE_PLACEHOLDER
 * 
 * Execution order: This plugin runs after viteSingleFile to ensure all assets are inlined first.
 */

import { Plugin } from 'vite';
import fs from 'fs';
import path from 'path';

/**
 * Plugin name for logging and identification
 */
const PLUGIN_NAME = 'inline-db';

/**
 * File paths and configuration constants
 */
const WASM_FILE_PATH = 'sql.js/dist/sql-wasm.wasm';
const DB_WORKER_FILE = 'dbServiceWorker.js';
const HTML_FILE_NAME = 'index.html';
const DIST_DIR_NAME = 'dist';

/**
 * Placeholder strings in HTML that need to be replaced
 */
const PLACEHOLDERS = {
    WASM: 'SQL_WASM_BASE64_PLACEHOLDER',
    WORKER_CODE: 'DB_WORKER_CODE_PLACEHOLDER',
} as const;

/**
 * Vite plugin to inline database-related files into HTML
 * @returns Vite plugin configuration
 */
export default function inlineDbPlugin(): Plugin {
  const projectRoot = path.resolve(__dirname);
  const rootNodeModules = path.resolve(projectRoot, '../node_modules');
  const localNodeModules = path.resolve(projectRoot, 'node_modules');

  /**
   * Finds a file in node_modules directories
   * Searches root node_modules first, then local node_modules
   * @param relativePath - Relative path to search for
   * @returns Absolute path if found, null otherwise
   */
  function findFileInNodeModules(relativePath: string): string | null {
    const rootPath = path.resolve(rootNodeModules, relativePath);
    if (fs.existsSync(rootPath)) {
      return rootPath;
    }

    const localPath = path.resolve(localNodeModules, relativePath);
    if (fs.existsSync(localPath)) {
      return localPath;
    }

    return null;
  }

  /**
   * Reads the sql.js WASM file and converts it to base64
   * @returns Base64 encoded WASM file content, or empty string if not found or error occurs
   */
  function readWasmAsBase64(): string {
    const wasmPath = findFileInNodeModules(WASM_FILE_PATH);
    if (!wasmPath) {
      console.warn(`[${PLUGIN_NAME}] WASM file not found at ${WASM_FILE_PATH}`);
      return '';
    }

    try {
      const wasmBuffer = fs.readFileSync(wasmPath);
      return wasmBuffer.toString('base64');
    } catch (error) {
      console.error(`[${PLUGIN_NAME}] Failed to read WASM file:`, error);
      return '';
    }
  }

  /**
   * Reads the dbServiceWorker.js file from the output directory and encodes it as base64
   * @param outputDir - Output directory path (typically 'dist')
   * @returns Base64 encoded worker code content, or empty string if not found or error occurs
   */
  function readDbWorkerCodeAsBase64(outputDir: string): string {
    const dbWorkerFilePath = path.resolve(outputDir, DB_WORKER_FILE);
    
    if (!fs.existsSync(dbWorkerFilePath)) {
      console.warn(`[${PLUGIN_NAME}] Worker file not found at ${dbWorkerFilePath}`);
      return '';
    }

    try {
      const workerCode = fs.readFileSync(dbWorkerFilePath, 'utf-8');
      const base64Code = Buffer.from(workerCode, 'utf-8').toString('base64');
      return base64Code;
    } catch (error) {
      console.error(`[${PLUGIN_NAME}] Failed to read or encode worker file:`, error);
      return '';
    }
  }

  /**
   * Replaces placeholders in HTML with actual base64-encoded content
   * @param html - Original HTML content
   * @param wasmBase64 - Base64 encoded WASM file content
   * @param workerCodeBase64 - Base64 encoded worker code content
   * @returns HTML with placeholders replaced, or original HTML if replacement fails
   */
  function replacePlaceholders(html: string, wasmBase64: string, workerCodeBase64: string): string {
    let result = html;

    // Replace WASM placeholder
    if (html.includes(PLACEHOLDERS.WASM)) {
      if (wasmBase64) {
        result = result.replace(new RegExp(PLACEHOLDERS.WASM, 'g'), wasmBase64);
      } else {
        console.warn(`[${PLUGIN_NAME}] WASM base64 is empty, placeholder '${PLACEHOLDERS.WASM}' will remain`);
      }
    }

    // Replace worker code placeholder
    if (html.includes(PLACEHOLDERS.WORKER_CODE)) {
      if (workerCodeBase64) {
        result = result.replace(new RegExp(PLACEHOLDERS.WORKER_CODE, 'g'), workerCodeBase64);
      } else {
        console.warn(`[${PLUGIN_NAME}] Worker code base64 is empty, placeholder '${PLACEHOLDERS.WORKER_CODE}' will remain`);
      }
    }

    return result;
  }

  /**
   * Checks if HTML file contains any placeholders that need to be replaced
   * @param html - HTML content to check
   * @returns True if placeholders are found, false otherwise
   */
  function hasPlaceholders(html: string): boolean {
    return html.includes(PLACEHOLDERS.WORKER_CODE) || html.includes(PLACEHOLDERS.WASM);
  }

  /**
   * Processes the HTML file by replacing placeholders with actual content
   * Reads WASM and worker files, encodes them, and replaces placeholders in HTML
   * @param htmlFilePath - Path to the HTML file to process
   * @param outputDir - Output directory path
   */
  function processHtmlFile(htmlFilePath: string, outputDir: string): void {
    try {
      const html = fs.readFileSync(htmlFilePath, 'utf-8');

      // Skip processing if no placeholders are found
      if (!hasPlaceholders(html)) {
        return;
      }

      // Read and encode WASM file
      // Note: sql.js and pako are automatically bundled into dbServiceWorker.js during build
      // Only the WASM file needs to be inlined separately for sql.js initialization
      const wasmBase64 = readWasmAsBase64();

      // Read and encode worker code
      const workerCodeBase64 = readDbWorkerCodeAsBase64(outputDir);
      if (!workerCodeBase64) {
        console.error(`[${PLUGIN_NAME}] Worker code is empty, cannot replace placeholder`);
        return;
      }

      // Replace placeholders and write back to file
      const modifiedHtml = replacePlaceholders(html, wasmBase64, workerCodeBase64);
      if (modifiedHtml !== html) {
        fs.writeFileSync(htmlFilePath, modifiedHtml, 'utf-8');
      }
    } catch (error) {
      console.error(`[${PLUGIN_NAME}] Failed to process HTML file:`, error);
    }
  }

  /**
   * Gets the output directory path
   * @returns Absolute path to the output directory
   */
  function getOutputDir(): string {
    return path.resolve(projectRoot, DIST_DIR_NAME);
  }

  /**
   * Gets the HTML file path in the output directory
   * @param outputDir - Output directory path
   * @returns Absolute path to the HTML file
   */
  function getHtmlFilePath(outputDir: string): string {
    return path.resolve(outputDir, HTML_FILE_NAME);
  }

  /**
   * Checks if required files exist for processing
   * @param outputDir - Output directory path
   * @returns True if both HTML and worker files exist, false otherwise
   */
  function canProcessFiles(outputDir: string): boolean {
    const htmlPath = getHtmlFilePath(outputDir);
    const workerPath = path.resolve(outputDir, DB_WORKER_FILE);
    return fs.existsSync(htmlPath) && fs.existsSync(workerPath);
  }

  return {
    name: PLUGIN_NAME,
    enforce: 'post',
    closeBundle() {
      // closeBundle runs after all bundles are closed
      // Since inlineDb is registered after viteSingleFile in vite.config.ts,
      // and both use enforce: 'post', this closeBundle executes after viteSingleFile's closeBundle
      // This ensures we process HTML after viteSingleFile has finished inlining all assets
      const outputDir = getOutputDir();
      const htmlFilePath = getHtmlFilePath(outputDir);

      if (!canProcessFiles(outputDir)) {
        console.warn(`[${PLUGIN_NAME}] Required files not found, skipping processing`);
        return;
      }

      processHtmlFile(htmlFilePath, outputDir);
    },
  };
}
