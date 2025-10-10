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
import fs from 'fs';
import type { FrameworkTypeKey, SoAnalysisResult } from '../../../config/types';
import { getFrameworkPatterns, matchSoPattern, isSystemSo } from '../../../config/framework-patterns';
import type {
    ZipInstance,
    ZipEntry,
    FileSizeLimits
} from '../../../types/zip-types';
import {
    isValidZipEntry,
    getSafeFileSize,
    safeReadZipEntry,
    isFileSizeExceeded,
    ZipEntryFilters,
    MemoryMonitor,
    DEFAULT_FILE_SIZE_LIMITS
} from '../../../types/zip-types';
import {
    ErrorFactory,
    ErrorUtils
} from '../../../errors';
import { ElfAnalyzer } from '../../elf/elf_analyzer';
import { FlutterAnalyzer } from './flutter_analyzer';
import Logger, { LOG_MODULE_TYPE } from 'arkanalyzer/lib/utils/logger';

/**
 * SO文件分析器 - 支持类型安全的ZIP分析，包含内存管理和错误处理
 */
export class SoAnalyzer {
    private readonly fileSizeLimits: FileSizeLimits;
    private readonly memoryMonitor: MemoryMonitor;
    private readonly supportedArchitectures: Array<string>;
    private readonly logger = Logger.getLogger(LOG_MODULE_TYPE.TOOL);
    private readonly flutterAnalyzer: FlutterAnalyzer;

    constructor(fileSizeLimits: FileSizeLimits = DEFAULT_FILE_SIZE_LIMITS) {
        this.fileSizeLimits = fileSizeLimits;
        this.memoryMonitor = new MemoryMonitor(fileSizeLimits.maxMemoryUsage);
        this.flutterAnalyzer = FlutterAnalyzer.getInstance();
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
        // zip.files is always present on a valid adapter

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

                    const soResult = await this.processSoFile(filePath, zipEntry, zip);
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
    private async processSoFile(filePath: string, zipEntry: ZipEntry, zip: ZipInstance): Promise<SoAnalysisResult | null> {
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
            const frameworks = await this.identifyFrameworks(fileName, zipEntry, zip);
            const isSystemLib = isSystemSo(fileName);

            // 如果是Flutter相关的SO文件，进行详细分析
            let flutterAnalysisResult = null;
            if (frameworks.includes('Flutter')) {
                try {
                    flutterAnalysisResult = await this.performFlutterAnalysis(fileName, zip);
                } catch (error) {
                    this.logger.warn(`Failed to perform Flutter analysis for ${fileName}: ${(error as Error).message}`);
                }
            }

            return {
                filePath,
                fileName,
                frameworks,
                fileSize,
                isSystemLib,
                flutterAnalysis: flutterAnalysisResult
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
     * @param zipEntry SO文件的ZIP条目（用于KMP框架的细化检测）
     * @param zip ZIP实例（用于KMP框架的细化检测）
     * @returns 识别到的框架类型数组
     */
    private async identifyFrameworks(fileName: string, zipEntry?: ZipEntry, zip?: ZipInstance): Promise<Array<FrameworkTypeKey>> {
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
                        
                        // 对于KMP框架，需要进一步验证
                        if (framework === 'KMP' && zipEntry && zip) {
                            const isKmpConfirmed = await this.verifyKmpFramework(zipEntry, zip);
                            if (isKmpConfirmed) {
                                if (!detectedFrameworks.includes(framework)) {
                                    detectedFrameworks.push(framework);
                                }
                            } else {
                                this.logger.debug(`KMP framework verification failed for ${fileName}, treating as Unknown`);
                            }
                        } else {
                            if (!detectedFrameworks.includes(framework)) {
                                detectedFrameworks.push(framework);
                            }
                        }
                        break; // 找到匹配就跳出内层循环
                    }
                }
            }

            return detectedFrameworks.length > 0 ? detectedFrameworks : ['Unknown'];
        } catch (error) {
            this.logger.warn(`Failed to identify frameworks for ${fileName}:`, error);
            return ['Unknown'];
        }
    }

    /**
     * 验证KMP框架的细化检测
     * @param zipEntry SO文件的ZIP条目
     * @param zip ZIP实例
     * @returns 是否为真正的KMP框架
     */
    private async verifyKmpFramework(zipEntry: ZipEntry, _zip: ZipInstance): Promise<boolean> {
        try {
            // 读取SO文件内容
            const soBuffer = await safeReadZipEntry(zipEntry, this.fileSizeLimits);

            // 创建临时文件用于ELF分析
            const tempDir = (await import('os')).tmpdir();
            const tempFilePath = path.join(tempDir, `temp_${Date.now()}_${Math.random().toString(36).substr(2, 9)}.so`);
            
            try {
                // 写入临时文件
                fs.writeFileSync(tempFilePath, soBuffer);
                
                // 使用ElfAnalyzer获取符号
                const elfAnalyzer = ElfAnalyzer.getInstance();
                const symbols = await elfAnalyzer.getSymbols(tempFilePath);
                
                // 检查导出符号中是否包含Kotlin相关字符串
                const allSymbols = [...symbols.exports, ...symbols.imports];
                const kotlinSymbols = allSymbols.filter(symbol => 
                    symbol.includes('Kotlin') || 
                    symbol.includes('KOTLIN_NATIVE_AVAILABLE_PROCESSORS')
                );
                
                this.logger.debug(`KMP verification: found ${kotlinSymbols.length} Kotlin-related symbols out of ${allSymbols.length} total symbols`);
                
                // 如果找到Kotlin相关符号，则确认为KMP框架
                return kotlinSymbols.length > 0;
                
            } finally {
                // 清理临时文件
                try {
                    if (fs.existsSync(tempFilePath)) {
                        fs.unlinkSync(tempFilePath);
                    }
                } catch (cleanupError) {
                    this.logger.warn(`Failed to cleanup temp file ${tempFilePath}:`, cleanupError);
                }
            }
        } catch (error) {
            this.logger.warn('KMP framework verification failed:', error);
            return false;
        }
    }

    /**
     * 执行Flutter详细分析
     * @param fileName SO文件名
     * @param zip ZIP实例
     * @returns Flutter分析结果
     */
    private async performFlutterAnalysis(fileName: string, zip: ZipInstance): Promise<import('../../../config/types').FlutterAnalysisResult | null> {
        try {
            // 所有Flutter相关的SO文件都进行完整分析（包信息+版本信息）
            return await this.performFlutterFullAnalysis(fileName, zip);
        } catch (error) {
            this.logger.error(`Flutter analysis failed: ${(error as Error).message}`);
            return null;
        }
    }

    /**
     * 执行完整的Flutter分析（分析当前SO文件的包信息和版本信息）
     */
    private async performFlutterFullAnalysis(fileName: string, zip: ZipInstance): Promise<import('../../../config/types').FlutterAnalysisResult | null> {
        try {
            // 查找当前SO文件和libflutter.so
            let currentSoPath: string | null = null;
            let libflutterSoPath: string | null = null;

            for (const [filePath] of Object.entries(zip.files)) {
                const basename = path.basename(filePath);
                if (basename === fileName) {
                    currentSoPath = filePath;
                } else if (basename === 'libflutter.so') {
                    libflutterSoPath = filePath;
                }
            }

            if (!currentSoPath) {
                this.logger.warn(`${fileName} not found for Flutter analysis`);
                return null;
            }

            // 创建临时文件进行分析
            const tempDir = fs.mkdtempSync(path.join((await import('os')).tmpdir(), 'flutter-analysis-'));
            let currentSoTempPath: string | null = null;
            let libflutterTempPath: string | null = null;

            try {
                // 提取当前SO文件到临时文件
                const currentSoEntry = zip.files[currentSoPath];
                const currentSoData = await safeReadZipEntry(currentSoEntry, this.fileSizeLimits);
                currentSoTempPath = path.join(tempDir, fileName);
                fs.writeFileSync(currentSoTempPath, currentSoData);

                // 提取libflutter.so到临时文件（如果存在且不是当前文件）
                if (libflutterSoPath && fileName !== 'libflutter.so') {
                    const libflutterEntry = zip.files[libflutterSoPath];
                    const libflutterData = await safeReadZipEntry(libflutterEntry, this.fileSizeLimits);
                    libflutterTempPath = path.join(tempDir, 'libflutter.so');
                    fs.writeFileSync(libflutterTempPath, libflutterData);
                }

                // 执行Flutter分析
                if (!currentSoTempPath) {
                    this.logger.warn('Temp path for current SO not prepared');
                    return null;
                }
                const libflutterPath = (fileName === 'libflutter.so' ? currentSoTempPath : libflutterTempPath) ?? undefined;
                const analysisResult = await this.flutterAnalyzer.analyzeFlutter(currentSoTempPath, libflutterPath);

                this.logger.info(`Flutter analysis completed for ${fileName}: isFlutter=${analysisResult.isFlutter}, packages=${analysisResult.dartPackages.length}, version=${analysisResult.flutterVersion?.hex40 ?? 'unknown'}`);

                return analysisResult;

            } finally {
                // 清理临时文件
                try {
                    if (fs.existsSync(tempDir)) {
                        fs.rmSync(tempDir, { recursive: true, force: true });
                    }
                } catch (cleanupError) {
                    this.logger.warn(`Failed to cleanup temp directory ${tempDir}:`, cleanupError);
                }
            }

        } catch (error) {
            this.logger.error(`Flutter full analysis failed: ${(error as Error).message}`);
            return null;
        }
    }


}
