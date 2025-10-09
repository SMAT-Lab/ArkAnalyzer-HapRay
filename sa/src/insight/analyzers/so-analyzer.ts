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
import type { FrameworkTypeKey, SoAnalysisResult } from '../types';
import { getFrameworkPatterns, matchSoPattern, isSystemSo } from '../config/framework-patterns';
import type {
    ZipInstance,
    ZipEntry,
    FileSizeLimits
} from '../types/zip-types';
import {
    isValidZipEntry,
    getSafeFileSize,
    safeReadZipEntry,
    isFileSizeExceeded,
    ZipEntryFilters,
    MemoryMonitor,
    DEFAULT_FILE_SIZE_LIMITS
} from '../types/zip-types';
import {
    ErrorFactory,
    ErrorUtils
} from '../errors';

/**
 * SO文件分析器 - 支持类型安全的ZIP分析，包含内存管理和错误处理
 */
export class SoAnalyzer {
    private readonly fileSizeLimits: FileSizeLimits;
    private readonly memoryMonitor: MemoryMonitor;
    private readonly supportedArchitectures: Array<string>;

    constructor(fileSizeLimits: FileSizeLimits = DEFAULT_FILE_SIZE_LIMITS) {
        this.fileSizeLimits = fileSizeLimits;
        this.memoryMonitor = new MemoryMonitor(fileSizeLimits.maxMemoryUsage);
        // this.supportedArchitectures = [
        //     'libs/arm64-v8a/',
        //     'libs/arm64/',
        //     'libs/armeabi-v7a/',
        //     'libs/x86/',
        //     'libs/x86_64/'
        // ];
        this.supportedArchitectures = [
            'libs/arm64-v8a/',
            'libs/arm64/'
        ];
    }

    /**
     * 直接从ZIP包中分析SO文件
     * @param zip JSZip实例
     * @returns SO文件分析结果
     */
    public async analyzeSoFilesFromZip(zip: ZipInstance): Promise<{
        detectedFrameworks: Array<FrameworkTypeKey>;
        soFiles: Array<SoAnalysisResult>;
        totalSoFiles: number;
    }> {
        if (!zip?.files) {
            throw ErrorFactory.createSoAnalysisError('Invalid ZIP instance provided');
        }

        // 重置内存监控器
        this.memoryMonitor.reset();

        const soFiles: Array<SoAnalysisResult> = [];
        const detectedFrameworks = new Set<FrameworkTypeKey>();
        const errors: Array<Error> = [];

        try {
            const entries = Object.entries(zip.files);

            for (const [filePath, zipEntry] of entries) {
                try {
                    // 验证ZIP条目
                    if (!isValidZipEntry(zipEntry)) {
                        errors.push(new Error(`Invalid ZIP entry: ${filePath}`));
                        continue;
                    }

                    // 只处理libs目录下的SO文件
                    if (!ZipEntryFilters.libsSoFilesOnly(zipEntry, filePath)) {
                        continue;
                    }

                    const soResult = await this.processSoFile(filePath, zipEntry);
                    if (soResult) {
                        soFiles.push(soResult);

                        // 收集检测到的框架
                        soResult.frameworks.forEach(framework => {
                            if (framework !== 'Unknown') {
                                detectedFrameworks.add(framework);
                            }
                        });
                    }

                } catch (error) {
                    const analysisError = ErrorFactory.createSoAnalysisError(
                        `Failed to process SO file: ${filePath}`,
                        filePath,
                        error instanceof Error ? error : new Error(String(error))
                    );
                    errors.push(analysisError);

                    // 对于非关键错误，继续处理其他文件
                    if (!ErrorUtils.isMemoryError(error)) {
                        continue;
                    }

                    // 内存错误需要立即停止处理
                    throw analysisError;
                }
            }

            const result = {
                detectedFrameworks: Array.from(detectedFrameworks),
                soFiles,
                totalSoFiles: soFiles.length
            };

            // 如果有非致命错误，记录但不抛出
            if (errors.length > 0) {
                console.warn(`SO analysis completed with ${errors.length} non-fatal errors`);
                errors.forEach(error => console.warn(error.message));
            }

            return result;

        } catch (error) {
            throw ErrorFactory.createSoAnalysisError(
                'Failed to analyze SO files from ZIP',
                undefined,
                error instanceof Error ? error : new Error(String(error))
            );
        } finally {
            // 清理内存监控器
            this.memoryMonitor.reset();
        }
    }

    /**
     * 处理单个SO文件
     */
    private async processSoFile(filePath: string, zipEntry: ZipEntry): Promise<SoAnalysisResult | null> {
        try {
            // 检查是否在支持的架构目录下
            const isInSupportedArch = this.supportedArchitectures.some(arch =>
                filePath.startsWith(arch)
            );

            if (!isInSupportedArch) {
                return null;
            }

            const fileName = path.basename(filePath);
            const fileSize = await this.getFileSizeWithMemoryCheck(zipEntry, filePath);

            if (fileSize === 0) {
                return null;
            }

            // 检测框架
            const frameworks = this.identifyFrameworks(fileName);
            const isSystemLib = isSystemSo(fileName);

            return {
                filePath,
                fileName,
                frameworks,
                fileSize,
                isSystemLib
            };
        } catch (error) {
            throw ErrorFactory.createSoAnalysisError(
                `Failed to process SO file: ${filePath}`,
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
                `SO file size ${fileSize} exceeds limit ${this.fileSizeLimits.maxFileSize}`,
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
                        `Cannot allocate memory for SO file: ${filePath}`,
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
     * 根据SO文件名识别框架类型
     * @param fileName SO文件名
     * @returns 识别到的框架类型数组
     */
    private identifyFrameworks(fileName: string): Array<FrameworkTypeKey> {
        try {
            // 首先检查是否是系统库
            if (isSystemSo(fileName)) {
                return ['System'];
            }

            const frameworkPatterns = getFrameworkPatterns();
            const detectedFrameworks: Array<FrameworkTypeKey> = [];

            // 遍历所有框架模式进行匹配
            for (const [frameworkType, patterns] of Object.entries(frameworkPatterns)) {
                for (const pattern of patterns) {
                    if (matchSoPattern(fileName, pattern)) {
                        const framework = frameworkType;
                        if (!detectedFrameworks.includes(framework)) {
                            detectedFrameworks.push(framework);
                        }
                        break; // 找到匹配就跳出内层循环
                    }
                }
            }

            return detectedFrameworks.length > 0 ? detectedFrameworks : ['Unknown'];
        } catch (error) {
            console.warn(`Failed to identify frameworks for ${fileName}:`, error);
            return ['Unknown'];
        }
    }
}
