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
import type { FlutterAnalysisResult, FrameworkTypeKey, SoAnalysisResult } from '../../../config/types';
import { getFrameworkPatterns, matchSoPattern } from '../../../config/framework-patterns';
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
import { tmpdir } from 'os';

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

            // 对unknown框架的SO文件进行额外检测
            await this.analyzeUnknownSoFiles(soFiles, zip);

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
                isSystemLib: false,
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
            const tempDir = tmpdir();
            const tempFilePath = path.join(tempDir, `temp_${Date.now()}_${Math.random().toString(36).substr(2, 9)}.so`);
            
            try {
                // 写入临时文件
                fs.writeFileSync(tempFilePath, soBuffer);
                
                // 方法1: 使用ElfAnalyzer获取符号
                const elfAnalyzer = ElfAnalyzer.getInstance();
                const symbols = await elfAnalyzer.getSymbols(tempFilePath);
                
                // 检查符号表中是否包含Kotlin相关字符串
                const allSymbols = [...symbols.exports, ...symbols.imports];
                const kotlinSymbols = allSymbols.filter(symbol => 
                    symbol.includes('Kotlin') || 
                    symbol.includes('KOTLIN_NATIVE_AVAILABLE_PROCESSORS') ||
                    symbol.includes('kfun') ||
                    symbol.includes('kotlinNativeReference')
                );
                
                this.logger.debug(`KMP verification (symbols): found ${kotlinSymbols.length} Kotlin-related symbols out of ${allSymbols.length} total symbols`);
                
                // 如果符号表中找到Kotlin相关符号，直接返回true
                if (kotlinSymbols.length > 0) {
                    this.logger.debug(`KMP verification passed via symbol analysis: ${kotlinSymbols.length} Kotlin symbols found`);
                    return true;
                }
                
                // 方法2: 扫描二进制内容查找Kotlin特征
                const binaryContent = soBuffer.toString('binary');
                const kotlinPatterns = [
                    'Kotlin',
                    'KOTLIN_NATIVE_AVAILABLE_PROCESSORS',
                    'kotlin'
                ];
                
                let foundPatterns = 0;
                const foundPatternDetails: Array<{pattern: string, count: number}> = [];
                
                for (const pattern of kotlinPatterns) {
                    const regex = new RegExp(pattern, 'gi');
                    const matches = binaryContent.match(regex);
                    if (matches) {
                        foundPatterns += matches.length;
                        foundPatternDetails.push({pattern, count: matches.length});
                        this.logger.debug(`KMP binary scan: found "${pattern}" ${matches.length} times`);
                    }
                }
                
                this.logger.debug(`KMP verification (binary): found ${foundPatterns} total Kotlin-related patterns`);
                
                // 如果找到足够的Kotlin特征，确认为KMP框架
                const isKmpFramework = foundPatterns >= 1; // 至少需要1个特征匹配
                
                if (isKmpFramework) {
                    this.logger.debug(`KMP verification passed via binary analysis: ${foundPatterns} patterns found`, foundPatternDetails);
                } else {
                    this.logger.debug(`KMP verification failed: only ${foundPatterns} patterns found (threshold: 3)`);
                }
                
                return isKmpFramework;
                
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
    private async performFlutterAnalysis(fileName: string, zip: ZipInstance): Promise<FlutterAnalysisResult | null> {
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
    private async performFlutterFullAnalysis(fileName: string, zip: ZipInstance): Promise<FlutterAnalysisResult | null> {
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
            const tempDir = fs.mkdtempSync(path.join(tmpdir(), 'flutter-analysis-'));
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

    /**
     * 对unknown框架的SO文件进行额外检测，识别Flutter和KMP框架
     * @param soFiles SO文件分析结果数组
     * @param zip ZIP实例
     */
    private async analyzeUnknownSoFiles(soFiles: Array<SoAnalysisResult>, zip: ZipInstance): Promise<void> {
        try {
            // 筛选出unknown框架的SO文件
            const unknownSoFiles = soFiles.filter(so => 
                so.frameworks.includes('Unknown') && !so.frameworks.includes('System')
            );

            if (unknownSoFiles.length === 0) {
                this.logger.debug('No unknown SO files found for additional analysis');
                return;
            }

            this.logger.info(`Analyzing ${unknownSoFiles.length} unknown SO files for Flutter and KMP frameworks`);

            for (const soFile of unknownSoFiles) {
                try {
                    // 检测Flutter框架
                    const isFlutter = await this.detectFlutterFramework(soFile, zip);
                    if (isFlutter) {
                        soFile.frameworks = soFile.frameworks.filter(f => f !== 'Unknown');
                        soFile.frameworks.push('Flutter');
                        this.logger.info(`Detected Flutter framework in unknown SO: ${soFile.fileName}`);
                        
                        // 进行Flutter详细分析
                        try {
                            soFile.flutterAnalysis = await this.performFlutterAnalysis(soFile.fileName, zip);
                        } catch (error) {
                            this.logger.warn(`Failed to perform Flutter analysis for ${soFile.fileName}: ${(error as Error).message}`);
                        }
                        continue;
                    }

                    // 检测KMP框架
                    const isKmp = await this.detectKmpFramework(soFile, zip);
                    if (isKmp) {
                        soFile.frameworks = soFile.frameworks.filter(f => f !== 'Unknown');
                        soFile.frameworks.push('KMP');
                        this.logger.info(`Detected KMP framework in unknown SO: ${soFile.fileName}`);
                    }

                } catch (error) {
                    this.logger.warn(`Failed to analyze unknown SO file ${soFile.fileName}: ${(error as Error).message}`);
                }
            }

        } catch (error) {
            this.logger.error(`Failed to analyze unknown SO files: ${(error as Error).message}`);
        }
    }

    /**
     * 检测SO文件是否为Flutter框架
     * @param soFile SO文件分析结果
     * @param zip ZIP实例
     * @returns 是否为Flutter框架
     */
    private async detectFlutterFramework(soFile: SoAnalysisResult, zip: ZipInstance): Promise<boolean> {
        try {
            // 获取SO文件对应的ZIP条目
            const zipEntry = zip.files[soFile.filePath];

            // 读取SO文件内容
            const soBuffer = await safeReadZipEntry(zipEntry, this.fileSizeLimits);

            // 创建临时文件用于ELF分析
            const tempDir = tmpdir();
            const tempFilePath = path.join(tempDir, `temp_flutter_${Date.now()}_${Math.random().toString(36).substr(2, 9)}.so`);
            
            try {
                // 写入临时文件
                fs.writeFileSync(tempFilePath, soBuffer);
                
                // 使用FlutterAnalyzer进行检测
                const flutterResult = await this.flutterAnalyzer.analyzeFlutter(tempFilePath);
                
                // 如果检测到Flutter特征，则确认为Flutter框架
                return flutterResult.isFlutter || flutterResult.dartPackages.length > 0;
                
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
            this.logger.warn(`Flutter framework detection failed for ${soFile.fileName}:`, error);
            return false;
        }
    }

    /**
     * 检测SO文件是否为KMP框架
     * @param soFile SO文件分析结果
     * @param zip ZIP实例
     * @returns 是否为KMP框架
     */
    private async detectKmpFramework(soFile: SoAnalysisResult, zip: ZipInstance): Promise<boolean> {
        try {
            // 获取SO文件对应的ZIP条目
            const zipEntry = zip.files[soFile.filePath];

            // 使用现有的KMP验证方法
            return await this.verifyKmpFramework(zipEntry, zip);
        } catch (error) {
            this.logger.warn(`KMP framework detection failed for ${soFile.fileName}:`, error);
            return false;
        }
    }
}
