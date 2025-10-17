/**
 * 文件大小获取和内存检查的公共工具函数
 * 消除重复代码，统一文件大小处理逻辑
 */

import type { ZipEntry } from '../types/zip-types';
import type { MemoryMonitor, FileSizeLimits } from '../types/zip-types';
import { getSafeFileSize, isFileSizeExceeded, safeReadZipEntry } from '../types/zip-types';
import { ErrorFactory } from '../errors';

/**
 * 获取文件大小配置
 */
export interface FileSizeOptions {
    zipEntry: ZipEntry;
    filePath: string;
    memoryMonitor: MemoryMonitor;
    limits: FileSizeLimits;
}

/**
 * 文件大小获取结果
 */
export interface FileSizeResult {
    /** 文件大小（字节） */
    size: number;
    /** 是否使用了压缩大小估算 */
    isEstimated: boolean;
}

/**
 * 智能获取文件大小（带内存检查和容错）
 * 
 * 策略：
 * 1. 如果元数据显示文件超过限制，直接使用压缩大小估算
 * 2. 否则尝试获取实际大小，失败时降级到压缩大小
 * 3. 对于未知大小的文件，进行内存检查后读取
 * 
 * @param options 文件大小获取选项
 * @returns 文件大小结果
 */
export async function getFileSizeWithFallback(options: FileSizeOptions): Promise<FileSizeResult> {
    const { zipEntry, filePath, memoryMonitor, limits } = options;
    
    // 策略1: 元数据检查 - 如果未压缩大小超过限制，使用压缩大小估算
    const metaUncompressed = zipEntry.uncompressedSize ?? getSafeFileSize(zipEntry);
    if (metaUncompressed > limits.maxFileSize) {
        return {
            size: zipEntry.compressedSize,
            isEstimated: true
        };
    }
    
    // 策略2: 尝试获取实际大小
    try {
        const actualSize = await getFileSizeWithMemoryCheck(zipEntry, filePath, memoryMonitor, limits);
        return {
            size: actualSize,
            isEstimated: false
        };
    } catch (error) {
        // 如果是文件大小限制错误，降级到压缩大小
        if ((error as Error & { code?: string }).code === 'FILE_SIZE_LIMIT_ERROR') {
            return {
                size: zipEntry.compressedSize,
                isEstimated: true
            };
        }
        // 其他错误继续抛出
        throw error;
    }
}

/**
 * 获取文件大小（带内存检查）
 * 
 * @param zipEntry ZIP条目
 * @param filePath 文件路径
 * @param memoryMonitor 内存监控器
 * @param limits 文件大小限制
 * @returns 文件大小（字节）
 * @throws 文件大小超限或内存不足时抛出错误
 */
async function getFileSizeWithMemoryCheck(
    zipEntry: ZipEntry,
    filePath: string,
    memoryMonitor: MemoryMonitor,
    limits: FileSizeLimits
): Promise<number> {
    const size = getSafeFileSize(zipEntry);
    
    // 检查文件大小是否超限
    if (isFileSizeExceeded(size, limits)) {
        throw ErrorFactory.createFileSizeLimitError(
            `文件大小 ${size} 超过限制 ${limits.maxFileSize}`,
            size,
            limits.maxFileSize,
            filePath
        );
    }
    
    // 如果大小已知，直接返回
    if (size > 0) {
        return size;
    }
    
    // 大小未知，需要读取文件来确定
    // 先检查内存是否足够
    if (!memoryMonitor.canAllocate(zipEntry.compressedSize)) {
        throw ErrorFactory.createOutOfMemoryError(
            `内存不足，无法处理文件：${filePath}`,
            zipEntry.compressedSize
        );
    }
    
    // 分配内存并读取
    memoryMonitor.allocate(zipEntry.compressedSize);
    try {
        const content = await safeReadZipEntry(zipEntry, limits);
        return content.length;
    } finally {
        memoryMonitor.deallocate(zipEntry.compressedSize);
    }
}

/**
 * 简化版：仅获取文件大小（不抛出异常）
 * 
 * 适用于只需要大小信息，不需要严格验证的场景
 * 
 * @param zipEntry ZIP条目
 * @param limits 文件大小限制
 * @returns 文件大小，超限时返回压缩大小
 */
export function getFileSizeSafe(zipEntry: ZipEntry, limits: FileSizeLimits): number {
    const metaUncompressed = zipEntry.uncompressedSize ?? getSafeFileSize(zipEntry);
    
    // 如果超过限制，返回压缩大小作为估算
    if (metaUncompressed > limits.maxFileSize) {
        return zipEntry.compressedSize;
    }
    
    // 返回实际大小
    return getSafeFileSize(zipEntry);
}

