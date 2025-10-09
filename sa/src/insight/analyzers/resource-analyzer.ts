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

import path from 'path';
import type { ResourceFileInfo, ResourceAnalysisResult, ArchiveFileInfo, JsFileInfo, HermesFileInfo } from '../types';
import { FileType } from '../types';
import { detectFileTypeByExtension, detectFileTypeByMagic, getMimeType } from '../../config/magic-numbers';
import { createZipAdapter } from '../../utils/zip-adapter';
import type {
    ZipInstance,
    ZipEntry,
    FileSizeLimits
} from '../../types/zip-types';
import {
    isValidZipEntry,
    isFileEntry,
    getSafeFileSize,
    safeReadZipEntry,
    isFileSizeExceeded,
    MemoryMonitor,
    DEFAULT_FILE_SIZE_LIMITS
} from '../../types/zip-types';
import {
    ErrorFactory,
    ErrorUtils
} from '../errors';

/**
 * 分析上下文接口
 */
interface AnalysisContext {
    filesByType: Map<FileType, Array<ResourceFileInfo>>;
    archiveFiles: Array<ArchiveFileInfo>;
    jsFiles: Array<JsFileInfo>;
    hermesFiles: Array<HermesFileInfo>;
    totalSize: number;
    totalFiles: number;
    maxExtractionDepth: number;
    extractedArchiveCount: number;
    errors: Array<Error>;
}

/**
 * 资源文件分析器 - 支持递归压缩包解析，包含内存管理和错误处理
 */
export class ResourceAnalyzer {
    private readonly fileSizeLimits: FileSizeLimits;
    private readonly memoryMonitor: MemoryMonitor;
    private readonly maxRecursionDepth: number;

    constructor(fileSizeLimits: FileSizeLimits = DEFAULT_FILE_SIZE_LIMITS, maxRecursionDepth = 5) {
        this.fileSizeLimits = fileSizeLimits;
        this.memoryMonitor = new MemoryMonitor(fileSizeLimits.maxMemoryUsage);
        this.maxRecursionDepth = maxRecursionDepth;
    }

    /**
     * 直接从ZIP包中分析资源文件（支持递归解析）
     * @param zip JSZip实例
     * @returns 资源文件分析结果
     */
    public async analyzeResourcesFromZip(zip: ZipInstance): Promise<ResourceAnalysisResult> {
        if (!zip?.files) {
            throw ErrorFactory.createResourceAnalysisError('Invalid ZIP instance provided');
        }

        // 重置内存监控器
        this.memoryMonitor.reset();

        const analysisContext: AnalysisContext = {
            filesByType: new Map<FileType, Array<ResourceFileInfo>>(),
            archiveFiles: [],
            jsFiles: [],
            hermesFiles: [],
            totalSize: 0,
            totalFiles: 0,
            maxExtractionDepth: 0,
            extractedArchiveCount: 0,
            errors: []
        };

        try {
            await this.analyzeZipRecursively(zip, '', 0, analysisContext);

            const result: ResourceAnalysisResult = {
                totalFiles: analysisContext.totalFiles,
                filesByType: analysisContext.filesByType,
                archiveFiles: analysisContext.archiveFiles,
                jsFiles: analysisContext.jsFiles,
                hermesFiles: analysisContext.hermesFiles,
                totalSize: analysisContext.totalSize,
                maxExtractionDepth: analysisContext.maxExtractionDepth,
                extractedArchiveCount: analysisContext.extractedArchiveCount
            };

            // 如果有非致命错误，记录但不抛出
            if (analysisContext.errors.length > 0) {
                console.warn(`Resource analysis completed with ${analysisContext.errors.length} non-fatal errors`);
                analysisContext.errors.forEach(error => console.warn(error.message));
            }

            return result;

        } catch (error) {
            throw ErrorFactory.createResourceAnalysisError(
                'Failed to analyze resources from ZIP',
                undefined,
                error instanceof Error ? error : new Error(String(error))
            );
        } finally {
            // 清理内存监控器
            this.memoryMonitor.reset();
        }
    }

    /**
     * 递归分析ZIP文件
     */
    private async analyzeZipRecursively(
        zip: ZipInstance,
        basePath: string,
        depth: number,
        context: AnalysisContext
    ): Promise<void> {
        if (depth > this.maxRecursionDepth) {
            console.warn(`Maximum recursion depth ${this.maxRecursionDepth} reached, skipping deeper analysis`);
            return;
        }

        context.maxExtractionDepth = Math.max(context.maxExtractionDepth, depth);
        const entries = Object.entries(zip.files);

        for (const [filePath, zipEntry] of entries) {
            try {
                // 验证ZIP条目
                if (!isValidZipEntry(zipEntry)) {
                    context.errors.push(new Error(`Invalid ZIP entry: ${filePath}`));
                    continue;
                }

                // 跳过目录
                if (!isFileEntry(zipEntry)) {
                    continue;
                }

                // 跳过libs目录下的SO文件（已在SO分析器中处理）
                if (filePath.startsWith('libs/') && filePath.endsWith('.so')) {
                    continue;
                }

                const fullPath = basePath ? `${basePath}/${filePath}` : filePath;
                const fileInfo = await this.processFileEntry(fullPath, zipEntry);
                if (!fileInfo) {
                    continue;
                }

                context.totalFiles++;
                context.totalSize += fileInfo.fileSize;

                // 按类型分组
                this.addFileToTypeMap(context.filesByType, fileInfo);

                // 处理特殊文件类型
                await this.processSpecialFileTypesRecursively(fileInfo, zipEntry, depth, context);

            } catch (error) {
                const analysisError = ErrorFactory.createResourceAnalysisError(
                    `Failed to process file: ${filePath}`,
                    filePath,
                    error instanceof Error ? error : new Error(String(error))
                );
                context.errors.push(analysisError);

                // 对于非关键错误，继续处理其他文件
                if (!ErrorUtils.isMemoryError(error)) {
                    continue;
                }

                // 内存错误需要立即停止处理
                throw analysisError;
            }
        }
    }

    /**
     * 处理单个文件条目
     */
    private async processFileEntry(filePath: string, zipEntry: ZipEntry): Promise<ResourceFileInfo | null> {
        try {
            const fileName = path.basename(filePath);
            const fileSize = await this.getFileSizeWithMemoryCheck(zipEntry, filePath);

            if (fileSize === 0) {
                return null;
            }

            const fileType = this.detectFileType(fileName);
            const mimeType = getMimeType(fileName);

            return {
                filePath,
                fileName,
                fileType,
                fileSize,
                mimeType,
                isTextFile: this.isLikelyTextFile(fileType)
            };
        } catch (error) {
            throw ErrorFactory.createResourceAnalysisError(
                `Failed to process file entry: ${filePath}`,
                filePath,
                error instanceof Error ? error : new Error(String(error))
            );
        }
    }

    /**
     * 获取文件大小并进行内存检查
     */
    private async getFileSizeWithMemoryCheck(zipEntry: ZipEntry, filePath: string): Promise<number> {
        const fileSize = getSafeFileSize(zipEntry);

        // 检查文件大小限制
        if (isFileSizeExceeded(fileSize, this.fileSizeLimits)) {
            throw ErrorFactory.createFileSizeLimitError(
                `File size ${fileSize} exceeds limit ${this.fileSizeLimits.maxFileSize}`,
                fileSize,
                this.fileSizeLimits.maxFileSize,
                filePath
            );
        }

        // 如果无法从元数据获取大小，需要读取内容
        if (fileSize === 0 && zipEntry.uncompressedSize === undefined) {
            try {
                // 检查内存是否足够
                if (!this.memoryMonitor.canAllocate(zipEntry.compressedSize)) {
                    throw ErrorFactory.createOutOfMemoryError(
                        `Cannot allocate memory for file: ${filePath}`,
                        zipEntry.compressedSize
                    );
                }

                this.memoryMonitor.allocate(zipEntry.compressedSize);

                try {
                    const content = await safeReadZipEntry(zipEntry, this.fileSizeLimits);
                    return content.length;
                } finally {
                    this.memoryMonitor.deallocate(zipEntry.compressedSize);
                }
            } catch (error) {
                if (ErrorUtils.isMemoryError(error)) {
                    throw error;
                }
                // 如果读取失败，返回压缩大小作为估算
                return zipEntry.compressedSize;
            }
        }

        return fileSize;
    }

    /**
     * 将文件添加到类型映射中
     */
    private addFileToTypeMap(filesByType: Map<FileType, Array<ResourceFileInfo>>, fileInfo: ResourceFileInfo): void {
        if (!filesByType.has(fileInfo.fileType)) {
            filesByType.set(fileInfo.fileType, []);
        }
        filesByType.get(fileInfo.fileType)!.push(fileInfo);
    }

    /**
     * 递归处理特殊文件类型
     */
    private async processSpecialFileTypesRecursively(
        fileInfo: ResourceFileInfo,
        zipEntry: ZipEntry,
        depth: number,
        context: AnalysisContext
    ): Promise<void> {
        switch (fileInfo.fileType) {
            case FileType.ZIP: {
                const archiveInfo: ArchiveFileInfo = {
                    ...fileInfo,
                    entryCount: 0,
                    extracted: false,
                    extractionDepth: depth,
                    nestedFiles: [],
                    nestedArchives: []
                };

                // 尝试解析嵌套的ZIP文件
                if (depth < this.maxRecursionDepth) {
                    try {
                        await this.extractAndAnalyzeNestedArchive(zipEntry, archiveInfo, depth, context);
                    } catch (error) {
                        console.warn(`Failed to extract nested archive ${fileInfo.filePath}:`, error);
                        archiveInfo.extracted = false;
                    }
                }

                context.archiveFiles.push(archiveInfo);
                break;
            }

            case FileType.JS: {
                const jsInfo: JsFileInfo = {
                    ...fileInfo,
                    isMinified: this.isMinifiedJs(fileInfo.fileName),
                    estimatedLines: this.estimateJsLines(fileInfo.fileSize)
                };
                context.jsFiles.push(jsInfo);
                break;
            }

            case FileType.HERMES_BYTECODE: {
                const hermesInfo: HermesFileInfo = {
                    ...fileInfo,
                    version: undefined,
                    isValidHermes: true // 基于文件类型检测假设有效
                };
                context.hermesFiles.push(hermesInfo);
                break;
            }
        }
    }



    /**
     * 检测文件类型
     */
    private detectFileType(fileName: string): FileType {
        // 优先使用扩展名检测
        const typeByExt = detectFileTypeByExtension(fileName);
        if (typeByExt !== FileType.Unknown) {
            return typeByExt;
        }

        return FileType.Unknown;
    }

    /**
     * 判断是否可能是文本文件
     */
    private isLikelyTextFile(fileType: FileType): boolean {
        const textTypes = [FileType.JS, FileType.JSON, FileType.XML, FileType.TEXT];
        return textTypes.includes(fileType);
    }

    /**
     * 判断JS文件是否被压缩
     */
    private isMinifiedJs(fileName: string): boolean {
        return fileName.includes('.min.') || fileName.includes('-min.');
    }

    /**
     * 估算JS文件行数
     */
    private estimateJsLines(fileSize: number): number {
        // 基于文件大小估算行数，平均每行约50字节
        return Math.max(1, Math.floor(fileSize / 50));
    }

    /**
     * 提取并分析嵌套的压缩文件
     */
    private async extractAndAnalyzeNestedArchive(
        zipEntry: ZipEntry,
        archiveInfo: ArchiveFileInfo,
        depth: number,
        context: AnalysisContext
    ): Promise<void> {
        try {
            // 读取压缩文件内容
            const archiveBuffer = await safeReadZipEntry(zipEntry, this.fileSizeLimits);

            // 检测文件类型
            const detectedType = detectFileTypeByMagic(archiveBuffer);
            if (detectedType !== FileType.ZIP) {
                // 不是ZIP文件，跳过
                return;
            }

            // 创建嵌套ZIP实例
            const nestedZip = await createZipAdapter(archiveBuffer);

            // 创建嵌套分析上下文
            const nestedContext: AnalysisContext = {
                filesByType: new Map<FileType, Array<ResourceFileInfo>>(),
                archiveFiles: [],
                jsFiles: [],
                hermesFiles: [],
                totalSize: 0,
                totalFiles: 0,
                maxExtractionDepth: 0,
                extractedArchiveCount: 0,
                errors: []
            };

            // 递归分析嵌套ZIP
            await this.analyzeZipRecursively(nestedZip, archiveInfo.filePath, depth + 1, nestedContext);

            // 更新archiveInfo
            archiveInfo.extracted = true;
            archiveInfo.entryCount = nestedContext.totalFiles;
            archiveInfo.nestedFiles = [];
            archiveInfo.nestedArchives = nestedContext.archiveFiles;

            // 收集嵌套文件到主上下文
            for (const [fileType, files] of nestedContext.filesByType) {
                if (!context.filesByType.has(fileType)) {
                    context.filesByType.set(fileType, []);
                }
                context.filesByType.get(fileType)!.push(...files);
                archiveInfo.nestedFiles.push(...files);
            }

            // 合并统计信息
            context.totalFiles += nestedContext.totalFiles;
            context.totalSize += nestedContext.totalSize;
            context.jsFiles.push(...nestedContext.jsFiles);
            context.hermesFiles.push(...nestedContext.hermesFiles);
            context.extractedArchiveCount++;
            context.maxExtractionDepth = Math.max(context.maxExtractionDepth, nestedContext.maxExtractionDepth);

        } catch (error) {
            console.warn('Failed to extract nested archive:', error);
            archiveInfo.extracted = false;
            throw error;
        }
    }
}
