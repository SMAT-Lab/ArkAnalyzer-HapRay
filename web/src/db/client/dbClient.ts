/**
 * Database Client - Main Thread Communication Layer
 * Handles message communication with Worker and provides database operation interfaces
 *
 * Responsibilities: Encapsulates Worker communication, provides basic methods like exec, query
 */

import type { WorkerRequest, WorkerResponse, WorkerMessageType } from '../serviceWorker/dbServiceWorker';

/**
 * SQL query parameter type
 */
export type SqlParam = string | number | null;

/**
 * SQL query result row type
 */
export type SqlRow = Record<string, unknown>;

/**
 * Request timeout in milliseconds
 */
const REQUEST_TIMEOUT_MS = 30000;

/**
 * ES module indicators
 */
const ES_MODULE_INDICATORS = ['import ', 'export ', 'import{', 'export{'] as const;

/**
 * Database client class
 * Responsible for message communication with dbServiceWorker
 */
export class DbClient {
  private worker: Worker | null = null;
  private pendingRequests: Map<string, { resolve: (value: unknown) => void; reject: (reason: unknown) => void }> = new Map();
  private requestIdCounter = 0;

  /**
   * Initialize Worker
   * @param dbDataBase64 - Base64 encoded gzip compressed database file (optional, reads from window.dbData)
   * @param wasmBase64 - Base64 encoded WASM file (optional, reads from window.__sqlWasmBase64)
   */
  async init(dbDataBase64?: string, wasmBase64?: string): Promise<void> {
    await this.createWorker();
    this.setupMessageHandlers();
    
    const finalDbData = this.getDbDataFromWindow(dbDataBase64);
    const finalWasmBase64 = this.getWasmBase64FromWindow(wasmBase64);
    
    console.log('[DbClient] Initializing database Worker...');
    await this.sendRequest('init', { dbData: finalDbData, wasmBase64: finalWasmBase64 });
    console.log('[DbClient] Database Worker initialized successfully');
  }

  /**
   * Execute SQL statement (no return value)
   * @param sql - SQL statement
   * @param params - Parameter array (optional)
   */
  async exec(sql: string, params?: SqlParam[]): Promise<void> {
    await this.sendRequest('exec', { sql, params });
  }

  /**
   * Query SQL statement (returns results)
   * @param sql - SQL query statement
   * @param params - Parameter array (optional)
   * @returns Query result array
   */
  async query(sql: string, params?: SqlParam[]): Promise<SqlRow[]> {
    const response = (await this.sendRequest('query', { sql, params })) as { result?: SqlRow[] };
    return response?.result || [];
  }

  /**
   * Close database and Worker
   */
  async close(): Promise<void> {
    if (this.worker) {
      await this.sendRequest('close');
      this.worker.terminate();
      this.worker = null;
    }
  }

  /**
   * Send custom type request (for business API calls)
   * @param type - Message type
   * @param payload - Request payload
   * @returns Response data
   */
  async request<T = unknown>(type: WorkerMessageType, payload?: unknown): Promise<T> {
    const response = await this.sendRequest(type, payload);
    if (response && typeof response === 'object' && 'result' in response) {
      return (response as { result: T }).result;
    }
    return response as T;
  }

  /**
   * Create Worker instance
   */
  private async createWorker(): Promise<void> {
    const workerCode = this.getWorkerCodeFromWindow();
    if (workerCode) {
      await this.createWorkerFromInlineCode(workerCode);
    } else {
      await this.createWorkerFromExternalFile();
    }
  }

  /**
   * Create Worker from inline code
   */
  private async createWorkerFromInlineCode(workerCode: string): Promise<void> {
    try {
      const isESModule = this.isESModule(workerCode);
      const blob = new Blob([workerCode], { type: 'application/javascript' });
      const workerUrl = URL.createObjectURL(blob);

      this.worker = isESModule
        ? new Worker(workerUrl, { type: 'module' })
        : new Worker(workerUrl);
      
      console.log('[DbClient] Worker created successfully');
    } catch (error) {
      console.error('[DbClient] Failed to create Worker:', error);
      throw error;
    }
  }

  /**
   * Get worker code from window object
   */
  private getWorkerCodeFromWindow(): string | undefined {
    if (typeof window === 'undefined') {
      return undefined;
    }
    return (window as { __dbWorkerCode?: string }).__dbWorkerCode;
  }

  /**
   * Create Worker from external file (development mode)
   */
  private async createWorkerFromExternalFile(): Promise<void> {
    try {
      this.worker = new Worker(new URL('../serviceWorker/dbServiceWorker.ts', import.meta.url), { type: 'module' });
      console.log('[DbClient] Worker created successfully (external file)');
    } catch (error) {
      console.error('[DbClient] Failed to create Worker (external file):', error);
      throw error;
    }
  }

  /**
   * Check if code is ES module
   */
  private isESModule(code: string): boolean {
    return ES_MODULE_INDICATORS.some(indicator => code.includes(indicator));
  }

  /**
   * Setup message handlers for Worker
   */
  private setupMessageHandlers(): void {
    if (!this.worker) {
      return;
    }

    this.worker.onmessage = (e: MessageEvent<WorkerResponse>) => {
      this.handleWorkerMessage(e.data);
    };

    this.worker.onerror = (error) => {
      this.handleWorkerError(error);
    };

    this.worker.onmessageerror = (error) => {
      console.error('[DbClient] Worker message error:', error);
    };
  }

  /**
   * Handle Worker message
   */
  private handleWorkerMessage(data: WorkerResponse): void {
    const { id, type, payload, error } = data;
    const request = this.pendingRequests.get(id);

    if (!request) {
      console.warn('[DbClient] Received response for unknown request, id:', id);
      return;
    }

    this.pendingRequests.delete(id);

    if (type === 'success') {
      request.resolve(payload);
    } else {
      request.reject(new Error(error || 'Unknown error'));
    }
  }

  /**
   * Handle Worker error
   */
  private handleWorkerError(error: ErrorEvent): void {
    console.error('[DbClient] Worker error:', error);
    console.error('[DbClient] Worker error details:', {
      message: error.message,
      filename: error.filename,
      lineno: error.lineno,
      colno: error.colno,
      error: error.error,
    });

    // Clean up all pending requests
    for (const [id, request] of this.pendingRequests.entries()) {
      this.pendingRequests.delete(id);
      request.reject(error);
    }
  }

  /**
   * Get database data from window object
   */
  private getDbDataFromWindow(dbDataBase64?: string): string | undefined {
    if (dbDataBase64 || typeof window === 'undefined') {
      return dbDataBase64;
    }

    if (window.dbData) {
      return window.dbData;
    }

    return undefined;
  }

  /**
   * Get WASM base64 from window object
   */
  private getWasmBase64FromWindow(wasmBase64?: string): string | undefined {
    if (wasmBase64 || typeof window === 'undefined') {
      return wasmBase64;
    }

    if (window.__sqlWasmBase64) {
      return window.__sqlWasmBase64;
    }

    return undefined;
  }

  /**
   * Send request to Worker
   */
  private sendRequest(type: WorkerMessageType, payload?: unknown): Promise<unknown> {
    return new Promise((resolve, reject) => {
      if (!this.worker) {
        console.error('[DbClient] Worker not initialized, cannot send request');
        reject(new Error('Worker not initialized'));
        return;
      }

      const id = `req_${this.requestIdCounter++}`;
      const timeoutId = this.setupRequestTimeout(id, type, reject);
      const { wrappedResolve, wrappedReject } = this.createWrappedCallbacks(timeoutId, resolve, reject);

      this.pendingRequests.set(id, { resolve: wrappedResolve, reject: wrappedReject });

      const request: WorkerRequest = { id, type, payload };
      this.postMessageToWorker(request, id, timeoutId, wrappedReject);
    });
  }

  /**
   * Setup request timeout
   */
  private setupRequestTimeout(id: string, type: WorkerMessageType, reject: (reason: unknown) => void): NodeJS.Timeout {
    return setTimeout(() => {
      if (this.pendingRequests.has(id)) {
        console.error('[DbClient] Request timeout, id:', id, 'type:', type);
        this.pendingRequests.delete(id);
        reject(new Error('Request timeout'));
      }
    }, REQUEST_TIMEOUT_MS);
  }

  /**
   * Create wrapped callbacks with timeout cleanup
   */
  private createWrappedCallbacks(
    timeoutId: NodeJS.Timeout,
    resolve: (value: unknown) => void,
    reject: (reason: unknown) => void
  ): { wrappedResolve: (value: unknown) => void; wrappedReject: (reason: unknown) => void } {
    return {
      wrappedResolve: (value: unknown) => {
        clearTimeout(timeoutId);
        resolve(value);
      },
      wrappedReject: (reason: unknown) => {
        clearTimeout(timeoutId);
        reject(reason);
      },
    };
  }

  /**
   * Post message to Worker
   */
  private postMessageToWorker(
    request: WorkerRequest,
    id: string,
    timeoutId: NodeJS.Timeout,
    wrappedReject: (reason: unknown) => void
  ): void {
    try {
      this.worker!.postMessage(request);
      console.log('[DbClient] Request sent to Worker, id:', id);
    } catch (error) {
      console.error('[DbClient] Failed to send request:', error);
      clearTimeout(timeoutId);
      this.pendingRequests.delete(id);
      wrappedReject(error);
    }
  }
}
