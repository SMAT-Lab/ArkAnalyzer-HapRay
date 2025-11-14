/**
 * Main application entry point
 * 
 * This file initializes the Vue application and sets up:
 * - Application plugins (Pinia, Router, Element Plus, i18n)
 * - Database initialization from embedded data
 * - JSON data loading from embedded data
 * - Worker code and WASM data extraction
 */

import './assets/main.css';

import { createApp } from 'vue';
import { createPinia } from 'pinia';

import App from './App.vue';
import router from './router';
import ElementPlus from 'element-plus';
import 'element-plus/dist/index.css';
import i18n from './i18n/index';
import { vscode } from './utils/vscode';
import { useJsonDataStore } from './stores/jsonDataStore.ts';
import { changeBase64Str2Json } from './utils/jsonUtil.ts';
import { initDb } from './utils/dbApi.ts';

/**
 * Script tag IDs for embedded data
 */
const SCRIPT_TAG_IDS = {
    DB_WORKER_CODE: 'dbWorkerCode',
    SQL_WASM_BASE64: 'sqlWasmBase64',
    DB_DATA: 'dbData',
} as const;

/**
 * Global window interface extensions
 */
declare global {
    interface Window {
        initialPage: string;
        jsonData: string;
        frameJsonData: string;
        emptyFrameJson: string;
        compareJsonData: string;
        dbData: string; // gzip+base64 encoded SQLite database file
        baseMark: string;
        compareMark: string;
        dataType: string;
        __dbWorkerCode: string;
        __sqlWasmBase64: string;
    }
}

/**
 * Decodes a base64 encoded string to UTF-8 string
 * @param base64String - Base64 encoded string to decode
 * @returns Decoded UTF-8 string, or empty string if decoding fails
 */
function decodeBase64(base64String: string): string {
    if (!base64String) {
        return '';
    }

    try {
        // atob() decodes base64 to binary string, which is UTF-8 for JavaScript code
        return atob(base64String);
    } catch (error) {
        console.error('[Main] Failed to decode base64 string:', error);
        return '';
    }
}

/**
 * Retrieves text content from a script tag with the specified ID
 * @param scriptId - The ID of the script tag to read from
 * @returns The text content of the script tag, or empty string if not found
 */
function getDataFromScriptTag(scriptId: string): string {
    const scriptElement = document.getElementById(scriptId);
    
    if (!scriptElement) {
        console.warn(`[Main] Script tag with id '${scriptId}' not found`);
        return '';
    }

    const content = scriptElement.textContent;
    if (content === null) {
        console.warn(`[Main] Script tag '${scriptId}' has no text content`);
        return '';
    }

    return content;
}

/**
 * Loads and decodes worker code from embedded script tag
 * Sets window.__dbWorkerCode with the decoded worker code
 */
function loadWorkerCode(): void {
    const base64Code = getDataFromScriptTag(SCRIPT_TAG_IDS.DB_WORKER_CODE);
    
    if (!base64Code) {
        console.warn('[Main] Worker code not found in script tag');
        window.__dbWorkerCode = '';
        return;
    }

    const decodedCode = decodeBase64(base64Code);
    window.__dbWorkerCode = decodedCode;
    
    if (decodedCode) {
        console.log(`[Main] Worker code loaded and decoded (length: ${decodedCode.length})`);
    } else {
        console.warn('[Main] Worker code decoding failed or resulted in empty string');
    }
}

/**
 * Loads WASM base64 data from embedded script tag
 * Sets window.__sqlWasmBase64 with the WASM base64 data
 */
function loadWasmBase64(): void {
    const wasmBase64 = getDataFromScriptTag(SCRIPT_TAG_IDS.SQL_WASM_BASE64);
    window.__sqlWasmBase64 = wasmBase64;
    
    if (wasmBase64) {
        console.log(`[Main] WASM base64 data loaded (length: ${wasmBase64.length})`);
    } else {
        console.warn('[Main] WASM base64 data not found');
    }
}

/**
 * Loads database data from embedded script tag
 * Sets window.dbData with the database data
 */
function loadDatabaseData(): void {
    const dbData = getDataFromScriptTag(SCRIPT_TAG_IDS.DB_DATA);
    window.dbData = dbData;
    
    if (window.dbData) {
        console.log(`[Main] Database data loaded (length: ${window.dbData.length})`);
    } else {
        console.log('[Main] Database data not found');
    }
}

/**
 * Checks if the database data is a placeholder or empty
 * @param dbData - Database data string to check
 * @returns True if the data is a placeholder or empty, false otherwise
 */
function isDatabaseDataPlaceholder(dbData: string): boolean {
    return !dbData || dbData.trim().length < 100;
}

/**
 * Initializes the database from embedded data
 * Reads database data from window.dbData and initializes the database
 */
async function initializeDatabase(): Promise<void> {
    const dbData = window.dbData;

    if (isDatabaseDataPlaceholder(dbData)) {
        console.log('[Main] Database data is placeholder or empty, skipping initialization');
        return;
    }

    try {
        console.log('[Main] Initializing database from embedded data...');
        // initDb automatically reads from window.dbData and window.__sqlWasmBase64
        await initDb(dbData);
        console.log('[Main] Database initialized successfully');
    } catch (error) {
        console.error('[Main] Failed to initialize database:', error);
        throw error;
    }
}

/**
 * Loads and processes JSON data from window object
 * Decodes base64 encoded JSON data and stores it in the JSON data store
 */
function loadJsonData(): void {
    const jsonData = window.jsonData;
    
    if (!jsonData) {
        console.log('[Main] No JSON data found, skipping JSON data loading');
        return;
    }

    try {
        const jsonDataStore = useJsonDataStore();
        const decodedJsonData = changeBase64Str2Json(jsonData, window.dataType);
        const decodedCompareJsonData = changeBase64Str2Json(window.compareJsonData, window.dataType);
        
        jsonDataStore.setJsonData(decodedJsonData, decodedCompareJsonData);
        console.log('[Main] JSON data loaded and processed successfully');
    } catch (error) {
        console.error('[Main] Failed to load JSON data:', error);
    }
}

/**
 * Configures and initializes the Vue application
 * Sets up all required plugins and extensions
 * @returns The configured Vue application instance
 */
function createVueApp() {
    const app = createApp(App);
    
    // Configure global properties
    app.config.globalProperties.$vscode = vscode;
    
    // Register plugins
    app.use(i18n);
    app.use(createPinia());
    app.use(router);
    app.use(ElementPlus);
    
    return app;
}

/**
 * Initializes application data from embedded script tags
 * Loads worker code, WASM data, database data, and JSON data
 * Ensures database is initialized before loading JSON data that depends on it
 */
async function initializeApplicationData(): Promise<void> {
    // Load worker code and WASM data (required for database operations)
    loadWorkerCode();
    loadWasmBase64();
    
    // Load database data
    loadDatabaseData();
    
    // Initialize database first if data is available
    if (!isDatabaseDataPlaceholder(window.dbData)) {
        try {
            await initializeDatabase();
        } catch (error) {
            console.error('[Main] Database initialization error:', error);
        }
    } else {
        console.log('[Main] Database data is placeholder or empty, skipping database initialization');
    }
    
    // Load JSON data after database is initialized
    // This ensures loadNativeMemoryDataFromDb can access the database
    loadJsonData();
}

// Create and configure Vue application
const app = createVueApp();

// Initialize application data from embedded resources
// Wait for database initialization before loading JSON data
initializeApplicationData().catch((error) => {
    console.error('[Main] Failed to initialize application data:', error);
}).then(() => {
    console.log('[Main] Application data initialized successfully');
    // Mount the application
    app.mount('#app');
});
