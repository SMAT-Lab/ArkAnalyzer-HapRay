/**
 * Vite Plugin: Inject JSON and DB data into HTML at final build stage
 * Replaces JSON_DATA_PLACEHOLDER and DB_DATA_PLACEHOLDER in HTML
 * 
 * This plugin only runs in development mode to inject test data
 */

import { Plugin } from 'vite';
import fs from 'fs';
import path from 'path';
import { gzipSync } from 'zlib';

/**
 * Plugin configuration constants
 */
const PLUGIN_NAME = 'inject-data';
const PLUGIN_ENFORCE = 'post' as const;

/**
 * File paths and placeholders
 */
const DIST_DIR_NAME = 'dist';
const HTML_FILE_NAME = 'index.html';
const JSON_FILE_NAME = 'test_perf.json';
const DB_FILE_NAME = 'hapray_report.db';
const PLACEHOLDER_JSON = 'JSON_DATA_PLACEHOLDER';
const PLACEHOLDER_DB = 'DB_DATA_PLACEHOLDER';

/**
 * Compression settings
 */
const GZIP_LEVEL = 9;
const DEFAULT_JSON_CONTENT = '{}';

/**
 * Vite plugin to inject JSON and database data into HTML
 * @returns Vite plugin configuration
 */
export default function injectDataPlugin(): Plugin {
  // Only execute in development mode
  if (process.env.NODE_ENV !== 'development') {
    return {
      name: PLUGIN_NAME,
    };
  }

  const projectRoot = path.resolve(__dirname);
  let hasInjected = false;

  /**
   * Get output HTML file path
   */
  function getHtmlFilePath(): string {
    const outputDir = path.resolve(projectRoot, DIST_DIR_NAME);
    return path.resolve(outputDir, HTML_FILE_NAME);
  }

  /**
   * Read HTML file content
   * @param htmlFilePath - Path to HTML file
   * @returns HTML content or null if file doesn't exist
   */
  function readHtmlFile(htmlFilePath: string): string | null {
    if (!fs.existsSync(htmlFilePath)) {
      console.warn(`[${PLUGIN_NAME}] HTML file does not exist:`, htmlFilePath);
      return null;
    }

    try {
      return fs.readFileSync(htmlFilePath, 'utf-8');
    } catch (error) {
      console.error(`[${PLUGIN_NAME}] Failed to read HTML file:`, error);
      return null;
    }
  }

  /**
   * Write HTML file content
   * @param htmlFilePath - Path to HTML file
   * @param content - HTML content to write
   */
  function writeHtmlFile(htmlFilePath: string, content: string): void {
    try {
      fs.writeFileSync(htmlFilePath, content, 'utf-8');
    } catch (error) {
      console.error(`[${PLUGIN_NAME}] Failed to write HTML file:`, error);
      throw error;
    }
  }

  /**
   * Compress and encode JSON content
   * @param jsonContent - JSON content as string
   * @returns Base64 encoded compressed JSON
   */
  function compressAndEncodeJson(jsonContent: string): string {
    try {
      const jsonBuffer = Buffer.from(jsonContent, 'utf-8');
      const compressedJson = gzipSync(jsonBuffer, { level: GZIP_LEVEL });
      return compressedJson.toString('base64');
    } catch (error) {
      console.error(`[${PLUGIN_NAME}] Failed to compress JSON:`, error);
      return Buffer.from(DEFAULT_JSON_CONTENT, 'utf-8').toString('base64');
    }
  }

  /**
   * Read and process JSON file
   * @returns Base64 encoded compressed JSON, or default empty object if file doesn't exist
   */
  function processJsonFile(): string {
    const jsonFilePath = path.resolve(projectRoot, JSON_FILE_NAME);

    if (!fs.existsSync(jsonFilePath)) {
      console.warn(`[${PLUGIN_NAME}] JSON file not found: ${jsonFilePath}, using default empty object`);
      return Buffer.from(DEFAULT_JSON_CONTENT, 'utf-8').toString('base64');
    }

    try {
      const jsonContent = fs.readFileSync(jsonFilePath, 'utf-8');
      return compressAndEncodeJson(jsonContent);
    } catch (error) {
      console.error(`[${PLUGIN_NAME}] Failed to read JSON file:`, error);
      return Buffer.from(DEFAULT_JSON_CONTENT, 'utf-8').toString('base64');
    }
  }

  /**
   * Escape single quotes for HTML attribute usage
   * @param str - String to escape
   * @returns Escaped string
   */
  function escapeSingleQuotes(str: string): string {
    return str.replace(/'/g, "\\'");
  }

  /**
   * Replace JSON placeholder in HTML
   * @param html - HTML content
   * @returns Modified HTML and whether changes were made
   */
  function replaceJsonPlaceholder(html: string): { html: string; hasChanges: boolean } {
    if (!html.includes(PLACEHOLDER_JSON)) {
      return { html, hasChanges: false };
    }

    const jsonDataStr = processJsonFile();
    const escapedJsonData = escapeSingleQuotes(jsonDataStr);
    const modifiedHtml = html.replace(new RegExp(PLACEHOLDER_JSON, 'g'), escapedJsonData);

    return { html: modifiedHtml, hasChanges: true };
  }

  /**
   * Compress and encode database file
   * @param dbData - Database file buffer
   * @returns Base64 encoded compressed database
   */
  function compressAndEncodeDb(dbData: Buffer): string {
    try {
      const compressedData = gzipSync(dbData, { level: GZIP_LEVEL });
      return compressedData.toString('base64');
    } catch (error) {
      console.error(`[${PLUGIN_NAME}] Failed to compress database:`, error);
      return '';
    }
  }

  /**
   * Read and process database file
   * @returns Base64 encoded compressed database, or empty string if file doesn't exist
   */
  function processDbFile(): string {
    const dbFilePath = path.resolve(projectRoot, DB_FILE_NAME);

    if (!fs.existsSync(dbFilePath)) {
      console.warn(`[${PLUGIN_NAME}] Database file not found: ${dbFilePath}`);
      return '';
    }

    try {
      const dbData = fs.readFileSync(dbFilePath);
      return compressAndEncodeDb(dbData);
    } catch (error) {
      console.error(`[${PLUGIN_NAME}] Failed to read database file:`, error);
      return '';
    }
  }

  /**
   * Replace database placeholder in HTML
   * @param html - HTML content
   * @returns Modified HTML and whether changes were made
   */
  function replaceDbPlaceholder(html: string): { html: string; hasChanges: boolean } {
    if (!html.includes(PLACEHOLDER_DB)) {
      return { html, hasChanges: false };
    }

    const base64Data = processDbFile();
    const modifiedHtml = html.replace(new RegExp(PLACEHOLDER_DB, 'g'), base64Data);

    return { html: modifiedHtml, hasChanges: true };
  }

  /**
   * Inject data into HTML file
   * Replaces placeholders with actual data from files
   */
  function injectData(): void {
    if (hasInjected) {
      return;
    }

    const htmlFilePath = getHtmlFilePath();
    const html = readHtmlFile(htmlFilePath);

    if (!html) {
      return;
    }

    let modifiedHtml = html;
    let hasChanges = false;

    // Process JSON placeholder
    const jsonResult = replaceJsonPlaceholder(modifiedHtml);
    modifiedHtml = jsonResult.html;
    hasChanges = hasChanges || jsonResult.hasChanges;

    // Process database placeholder
    const dbResult = replaceDbPlaceholder(modifiedHtml);
    modifiedHtml = dbResult.html;
    hasChanges = hasChanges || dbResult.hasChanges;

    // Save modified HTML if there are changes
    if (hasChanges) {
      writeHtmlFile(htmlFilePath, modifiedHtml);
      hasInjected = true;
      console.log(`[${PLUGIN_NAME}] Successfully injected data into HTML`);
    }
  }

  return {
    name: PLUGIN_NAME,
    enforce: PLUGIN_ENFORCE,
    closeBundle() {
      injectData();
    },
  };
}
