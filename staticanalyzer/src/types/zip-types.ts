/*
 * Copyright (c) 2025 Huawei Device Co., Ltd.
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

/**
 * ZIP条目接口定义
 */
export interface ZipEntry {
    /** 文件名 */
    name: string;
    /** 是否为目录 */
    dir: boolean;
    /** 未压缩大小 */
    uncompressedSize?: number;
    /** 压缩大小 */
    compressedSize: number;
    /** 最后修改时间 */
    date?: Date;
    /** 异步读取文件内容 */
    async(type: 'nodebuffer'): Promise<Buffer>;
    async(type: 'string'): Promise<string>;
    async(type: 'uint8array'): Promise<Uint8Array>;
}

/**
 * ZIP文件集合接口
 */
export interface ZipFiles {
    [path: string]: ZipEntry;
}

/**
 * ZIP实例接口
 */
export interface ZipInstance {
    /** 文件集合 */
    files: ZipFiles;
    /** 加载ZIP数据 */
    loadAsync(data: Buffer): Promise<ZipInstance>;
}

/**
 * 文件大小限制配置
 */
export interface FileSizeLimits {
    /** 单个文件最大大小（字节） */
    maxFileSize: number;
    /** 总内存使用限制（字节） */
    maxMemoryUsage: number;
    /** 大文件阈值（字节） */
    largeFileThreshold: number;
}

/**
 * 默认文件大小限制
 */
export const DEFAULT_FILE_SIZE_LIMITS: FileSizeLimits = {
    maxFileSize: 100 * 1024 * 1024,      // 100MB
    maxMemoryUsage: 500 * 1024 * 1024,   // 500MB
    largeFileThreshold: 10 * 1024 * 1024  // 10MB
};

/**
 * ZIP条目类型守卫
 */
export function isValidZipEntry(entry: unknown): entry is ZipEntry {
    return (
        entry !== null &&
        typeof entry === 'object' &&
        'name' in entry &&
        'dir' in entry &&
        'compressedSize' in entry &&
        'async' in entry &&
        typeof (entry as Record<string, unknown>).name === 'string' &&
        typeof (entry as Record<string, unknown>).dir === 'boolean' &&
        typeof (entry as Record<string, unknown>).compressedSize === 'number' &&
        typeof (entry as Record<string, unknown>).async === 'function'
    );
}

/**
 * 检查是否为目录条目
 */
export function isDirectoryEntry(entry: ZipEntry): boolean {
    return entry.dir === true;
}

/**
 * 检查是否为文件条目
 */
export function isFileEntry(entry: ZipEntry): boolean {
    return entry.dir === false;
}

/**
 * 获取文件扩展名
 */
export function getFileExtension(fileName: string): string {
    const lastDotIndex = fileName.lastIndexOf('.');
    return lastDotIndex > 0 ? fileName.substring(lastDotIndex + 1).toLowerCase() : '';
}

/**
 * 检查文件是否在指定目录下
 */
export function isFileInDirectory(filePath: string, directory: string): boolean {
    return filePath.startsWith(directory);
}

/**
 * 检查文件是否为SO文件
 */
export function isSoFile(fileName: string): boolean {
    return fileName.endsWith('.so');
}

/**
 * 检查文件是否在libs目录下
 */
export function isInLibsDirectory(filePath: string): boolean {
    return filePath.startsWith('libs/');
}

/**
 * 获取安全的文件大小
 */
export function getSafeFileSize(entry: ZipEntry): number {
    // 优先使用未压缩大小
    if (typeof entry.uncompressedSize === 'number' && entry.uncompressedSize >= 0) {
        return entry.uncompressedSize;
    }
    
    // 回退到压缩大小
    if (typeof entry.compressedSize === 'number' && entry.compressedSize >= 0) {
        return entry.compressedSize;
    }
    
    // 默认返回0
    return 0;
}

/**
 * 检查文件大小是否超过限制
 */
export function isFileSizeExceeded(fileSize: number, limits: FileSizeLimits): boolean {
    return fileSize > limits.maxFileSize;
}

/**
 * 检查是否为大文件
 */
export function isLargeFile(fileSize: number, limits: FileSizeLimits): boolean {
    return fileSize > limits.largeFileThreshold;
}

/**
 * 安全地读取ZIP条目内容
 */
export async function safeReadZipEntry(
    entry: ZipEntry, 
    limits: FileSizeLimits = DEFAULT_FILE_SIZE_LIMITS
): Promise<Buffer> {
    const fileSize = getSafeFileSize(entry);
    
    // 检查文件大小限制
    if (isFileSizeExceeded(fileSize, limits)) {
        throw new Error(`File size ${fileSize} exceeds limit ${limits.maxFileSize}`);
    }
    
    try {
        return await entry.async('nodebuffer');
    } catch (error) {
        throw new Error(`Failed to read ZIP entry: ${error}`);
    }
}

/**
 * 批量处理ZIP条目的选项
 */
export interface BatchProcessOptions {
    /** 并发限制 */
    concurrency?: number;
    /** 文件大小限制 */
    fileSizeLimits?: FileSizeLimits;
    /** 跳过大文件 */
    skipLargeFiles?: boolean;
    /** 进度回调 */
    onProgress?: (processed: number, total: number) => void;
}

/**
 * 默认批量处理选项
 */
export const DEFAULT_BATCH_OPTIONS: Required<BatchProcessOptions> = {
    concurrency: 5,
    fileSizeLimits: DEFAULT_FILE_SIZE_LIMITS,
    skipLargeFiles: false,
    onProgress: () => {}
};

/**
 * ZIP条目过滤器类型
 */
export type ZipEntryFilter = (entry: ZipEntry, path: string) => boolean;

/**
 * 常用的ZIP条目过滤器
 */
export const ZipEntryFilters = {
    /** 只处理文件（跳过目录） */
    filesOnly: (entry: ZipEntry): boolean => isFileEntry(entry),
    
    /** 只处理SO文件 */
    soFilesOnly: (entry: ZipEntry): boolean => 
        isFileEntry(entry) && isSoFile(entry.name),
    
    /** 只处理libs目录下的SO文件 */
    libsSoFilesOnly: (entry: ZipEntry, path: string): boolean =>
        isFileEntry(entry) && isSoFile(entry.name) && isInLibsDirectory(path),
    
    /** 跳过libs目录下的SO文件 */
    skipLibsSoFiles: (entry: ZipEntry, path: string): boolean =>
        !(isSoFile(entry.name) && isInLibsDirectory(path)),
    
    /** 只处理小文件 */
    smallFilesOnly: (entry: ZipEntry): boolean => {
        const fileSize = getSafeFileSize(entry);
        return !isLargeFile(fileSize, DEFAULT_FILE_SIZE_LIMITS);
    }
};

/**
 * 内存使用监控器
 */
export class MemoryMonitor {
    private currentUsage = 0;
    private readonly maxUsage: number;

    constructor(maxUsage: number = DEFAULT_FILE_SIZE_LIMITS.maxMemoryUsage) {
        this.maxUsage = maxUsage;
    }

    /**
     * 分配内存
     */
    allocate(size: number): void {
        if (this.currentUsage + size > this.maxUsage) {
            throw new Error(`Memory allocation would exceed limit: ${this.currentUsage + size} > ${this.maxUsage}`);
        }
        this.currentUsage += size;
    }

    /**
     * 释放内存
     */
    deallocate(size: number): void {
        this.currentUsage = Math.max(0, this.currentUsage - size);
    }

    /**
     * 获取当前内存使用量
     */
    getCurrentUsage(): number {
        return this.currentUsage;
    }

    /**
     * 获取剩余可用内存
     */
    getAvailableMemory(): number {
        return Math.max(0, this.maxUsage - this.currentUsage);
    }

    /**
     * 检查是否可以分配指定大小的内存
     */
    canAllocate(size: number): boolean {
        return this.currentUsage + size <= this.maxUsage;
    }

    /**
     * 重置内存使用计数
     */
    reset(): void {
        this.currentUsage = 0;
    }
}
