/**
 * 临时文件管理器 - 统一管理临时文件的创建和清理
 * 
 * 职责：
 * 1. 创建临时目录
 * 2. 写入临时文件
 * 3. 自动清理资源
 * 4. 提供安全的文件操作
 */

import fs from 'fs';
import path from 'path';
import os from 'os';

/**
 * 临时文件信息
 */
export interface TempFileInfo {
    /** 临时文件路径 */
    path: string;
    /** 文件名 */
    fileName: string;
}

/**
 * 临时目录管理器
 */
export class TempDirectoryManager {
    private readonly tempDir: string;
    private readonly createdFiles: Set<string> = new Set();
    private isCleanedUp = false;
    
    /**
     * 创建临时目录管理器
     * @param prefix 临时目录前缀
     */
    constructor(prefix = 'hapray-') {
        this.tempDir = fs.mkdtempSync(path.join(os.tmpdir(), prefix));
    }
    
    /**
     * 获取临时目录路径
     */
    public getPath(): string {
        return this.tempDir;
    }
    
    /**
     * 写入临时文件
     * @param fileName 文件名
     * @param data 文件数据
     * @returns 临时文件信息
     */
    public writeFile(fileName: string, data: Buffer | Uint8Array): TempFileInfo {
        if (this.isCleanedUp) {
            throw new Error('TempDirectoryManager has been cleaned up');
        }
        
        const filePath = path.join(this.tempDir, fileName);
        fs.writeFileSync(filePath, data);
        this.createdFiles.add(filePath);
        
        return {
            path: filePath,
            fileName
        };
    }
    
    /**
     * 写入多个临时文件
     * @param files 文件列表 {fileName: data}
     * @returns 临时文件信息列表
     */
    public writeFiles(files: Record<string, Buffer | Uint8Array>): Array<TempFileInfo> {
        const results: Array<TempFileInfo> = [];
        
        for (const [fileName, data] of Object.entries(files)) {
            results.push(this.writeFile(fileName, data));
        }
        
        return results;
    }
    
    /**
     * 检查文件是否存在
     * @param fileName 文件名
     */
    public fileExists(fileName: string): boolean {
        const filePath = path.join(this.tempDir, fileName);
        return fs.existsSync(filePath);
    }
    
    /**
     * 获取文件路径
     * @param fileName 文件名
     */
    public getFilePath(fileName: string): string {
        return path.join(this.tempDir, fileName);
    }
    
    /**
     * 清理所有临时文件
     */
    public cleanup(): void {
        if (this.isCleanedUp) {
            return;
        }
        
        try {
            if (fs.existsSync(this.tempDir)) {
                fs.rmSync(this.tempDir, { recursive: true, force: true });
            }
            this.isCleanedUp = true;
            this.createdFiles.clear();
        } catch (error) {
            console.warn(`Failed to cleanup temp directory ${this.tempDir}:`, error);
        }
    }
    
    /**
     * 获取已创建的文件数量
     */
    public getFileCount(): number {
        return this.createdFiles.size;
    }
}

/**
 * 使用临时目录执行操作（自动清理）
 * 
 * @param prefix 临时目录前缀
 * @param operation 要执行的操作
 * @returns 操作结果
 * 
 * @example
 * ```typescript
 * const result = await withTempDirectory('flutter-analysis-', async (tempDir) => {
 *   const file1 = tempDir.writeFile('libapp.so', buffer1);
 *   const file2 = tempDir.writeFile('libflutter.so', buffer2);
 *   return await analyzeFlutter(file1.path, file2.path);
 * });
 * ```
 */
export async function withTempDirectory<T>(
    prefix: string,
    operation: (tempDir: TempDirectoryManager) => Promise<T>
): Promise<T> {
    const tempDir = new TempDirectoryManager(prefix);
    
    try {
        return await operation(tempDir);
    } finally {
        tempDir.cleanup();
    }
}

/**
 * 同步版本：使用临时目录执行操作（自动清理）
 */
export function withTempDirectorySync<T>(
    prefix: string,
    operation: (tempDir: TempDirectoryManager) => T
): T {
    const tempDir = new TempDirectoryManager(prefix);
    
    try {
        return operation(tempDir);
    } finally {
        tempDir.cleanup();
    }
}

