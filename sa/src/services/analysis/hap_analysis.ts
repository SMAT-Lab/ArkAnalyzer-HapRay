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

import fs from 'fs';
import path from 'path';
import type { HapStaticAnalysisResult, ResourceAnalysisResult, TechStackDetection } from '../../config/types';
import { fileExists, ensureDirectoryExists } from '../../utils/file_utils';
import type { EnhancedJSZipAdapter } from '../../utils/zip-adapter';
import { createEnhancedZipAdapter } from '../../utils/zip-adapter';
import { ErrorFactory } from '../../errors';
import Logger, { LOG_MODULE_TYPE } from 'arkanalyzer/lib/utils/logger';
import type { ZipInstance } from '../../types/zip-types';
import { DetectorEngine } from '../../core/techstack/detector/detector-engine';
import { HapFileScanner } from '../../core/techstack/adapter/hap-file-scanner';
import { ResultAdapter } from '../../core/techstack/adapter/result-adapter';

const logger = Logger.getLogger(LOG_MODULE_TYPE.TOOL);

// ===================== 内部类型定义 =====================
/**
 * HAP分析配置选项
 */
interface HapAnalysisOptions {
    verbose?: boolean;
    outputDir?: string;
    /** 是否美化 JS 文件（默认：false） */
    beautifyJs?: boolean;
}


export class HapAnalysisService {
    private verbose: boolean;
    private detectorEngine: DetectorEngine;
    private detectorInitialized = false;

    constructor(options: HapAnalysisOptions = {}) {
        this.verbose = options.verbose ?? false;
        this.detectorEngine = DetectorEngine.getInstance();
    }

    // ===================== 主要业务方法 =====================
    /**
     * 分析HAP/ZIP文件
     * @param hapFilePath 文件路径（.hap/.zip等）
     * @param outputDir 输出目录
     */
    public async analyzeHap(hapFilePath: string, outputDir?: string): Promise<HapStaticAnalysisResult> {
        const startTime = Date.now();
        
        if (!fileExists(hapFilePath)) {
            throw ErrorFactory.createHapFileError(`HAP file not found: ${hapFilePath}`, hapFilePath);
        }

        // 基础校验与提示
        this.validateHapFile(hapFilePath);

        // 读取文件并委托给统一的ZIP分析流程
        const fileData = await this.readHapFile(hapFilePath);
        const result = await this.analyzeZipData(hapFilePath, fileData, outputDir);
        
        const processingTime = Date.now() - startTime;
        if (this.verbose) {
            this.logAnalysisSummary(hapFilePath, processingTime, result);
        }
        
        return result;
    }

    /**
     * 使用ZIP二进制数据进行分析，兼容任意ZIP来源（.hap/.zip/目录打包）
     * @param sourceLabel 源路径或标识
     * @param zipData ZIP二进制数据
     * @param outputDir 输出目录
     */
    public async analyzeZipData(sourceLabel: string, zipData: Buffer, outputDir?: string): Promise<HapStaticAnalysisResult> {
        if (this.verbose) {
            logger.info(`开始分析：${sourceLabel}`);
        }

        let zipAdapter: EnhancedJSZipAdapter | null = null;
        try {
            zipAdapter = await this.createZipAdapter(zipData, sourceLabel);
            
            if (this.verbose) {
                this.logZipInfo(zipAdapter);
            }

            // 持久化基本工件到输出目录（如果提供）
            if (outputDir) {
                await this.persistZipArtifacts(zipAdapter, sourceLabel, outputDir);
            }

            // 执行分析
            const analysisResult = await this.performAnalysis(zipAdapter, sourceLabel);
            
            if (this.verbose) {
                this.logAnalysisResults(analysisResult);
            }
            
            return analysisResult;
        } finally {
            zipAdapter = null;
        }
    }

    // ===================== 数据加载函数 =====================
    /**
     * 读取HAP文件数据
     */
    private async readHapFile(hapFilePath: string): Promise<Buffer> {
        try {
            const start = Date.now();
            const fileData = fs.readFileSync(hapFilePath);
            if (this.verbose) {
                const readMs = Date.now() - start;
                logger.info(`Read file: ${this.formatBytes(fileData.length)} in ${readMs}ms`);
            }
            return fileData;
        } catch (error) {
            throw ErrorFactory.createHapFileError(
                `Failed to read file: ${hapFilePath}`,
                hapFilePath,
                error instanceof Error ? error : new Error(String(error))
            );
        }
    }

    /**
     * 创建ZIP适配器
     */
    private async createZipAdapter(zipData: Buffer, sourceLabel: string): Promise<EnhancedJSZipAdapter> {
        try {
            return await createEnhancedZipAdapter(zipData);
        } catch (error) {
            throw ErrorFactory.createZipParsingError(
                `Failed to parse as ZIP: ${sourceLabel}`,
                sourceLabel,
                error instanceof Error ? error : new Error(String(error))
            );
        }
    }

    // ===================== 工具函数区 =====================
    // ---- 文件操作 ----
    /**
     * 验证HAP文件
     */
    private validateHapFile(hapFilePath: string): void {
        const lower = hapFilePath.toLowerCase();
        const isZipLike = lower.endsWith('.hap') || lower.endsWith('.zip');
        if (!isZipLike && this.verbose) {
            logger.warn(`Input file does not have .hap/.zip extension: ${hapFilePath}. Will attempt ZIP parsing.`);
        }
    }

    /**
     * 持久化ZIP工件
     */
    private async persistZipArtifacts(
        zipAdapter: EnhancedJSZipAdapter, 
        sourceLabel: string, 
        outputDir: string
    ): Promise<void> {
        try {
            ensureDirectoryExists(outputDir);
            const fileList = Object.entries(zipAdapter.files)
                .map(([p, e]) => `${p}\t${(e as unknown as { compressedSize: number }).compressedSize}`)
                .join('\n');
            fs.writeFileSync(path.join(outputDir, '文件列表.txt'), fileList);
            
            const overview = {
                来源: sourceLabel,
                条目总数: Object.keys(zipAdapter.files).length,
                压缩后大小: zipAdapter.getTotalCompressedSize(),
                未压缩大小: zipAdapter.getTotalUncompressedSize(),
                压缩比: zipAdapter.getOverallCompressionRatio()
            } as Record<string, unknown>;
            fs.writeFileSync(path.join(outputDir, 'zip概览.json'), JSON.stringify(overview, null, 2));
        } catch (error) {
            logger.warn(`Failed to persist ZIP artifacts: ${error}`);
        }
    }

    // ---- 分析执行 ----
    /**
     * 执行核心分析逻辑（直接调用技术栈检测）
     */
    private async performAnalysis(
        zipAdapter: EnhancedJSZipAdapter,
        sourceLabel: string
    ): Promise<HapStaticAnalysisResult> {
        // 直接执行技术栈分析
        const soAnalysis = await this.runTechStackAnalysis(zipAdapter.getJSZip() as unknown as ZipInstance);

        const resourceAnalysis: ResourceAnalysisResult = {
            totalFiles: 0,
            filesByType: new Map(),
            archiveFiles: [],
            jsFiles: [],
            hermesFiles: [],
            totalSize: 0,
            maxExtractionDepth: 0,
            extractedArchiveCount: 0
        };

        return {
            hapPath: sourceLabel,
            soAnalysis,
            resourceAnalysis,
            timestamp: new Date()
        };
    }

    /**
     * 确保检测引擎已初始化
     */
    private ensureDetectorInitialized(): void {
        if (!this.detectorInitialized) {
            try {
                this.detectorEngine.initialize();
                this.detectorInitialized = true;
                logger.info('✅ DetectorEngine initialized');
            } catch (error) {
                logger.error('❌ Failed to initialize DetectorEngine:', error);
                throw error;
            }
        }
    }

    /**
     * 运行技术栈分析
     */
    private async runTechStackAnalysis(zip: ZipInstance): Promise<{
        detectedFrameworks: Array<string>;
        techStackDetections: Array<TechStackDetection>;
        totalSoFiles: number;
    }> {
        this.ensureDetectorInitialized();

        const startTime = Date.now();
        logger.info('🔍 Starting TechStack analysis...');

        try {
            // 1. 扫描 ZIP 文件，提取所有文件
            // 扫描所有文件，由配置文件中的规则决定哪些文件需要检测
            const fileInfos = await HapFileScanner.scanZip(zip);

            logger.info(`📁 Scanned ${fileInfos.length} files from HAP`);

            // 2. 并行检测所有文件
            const detectionResults = await this.detectorEngine.detectFiles(fileInfos);

            // 3. 转换为现有格式
            const techStackDetections = ResultAdapter.toSoAnalysisResults(detectionResults, '');

            // 4. 提取所有检测到的框架
            const detectedFrameworks = ResultAdapter.extractAllFrameworks(detectionResults);

            // 5. 统计信息
            const stats = ResultAdapter.getDetectionStats(detectionResults);
            const duration = Date.now() - startTime;

            logger.info(`✅ TechStack analysis completed in ${duration}ms`);
            logger.info(`   - Total files: ${stats.totalFiles}`);
            logger.info(`   - Detected files: ${stats.detectedFiles}`);
            logger.info(`   - Total detections: ${stats.totalDetections}`);
            logger.info(`   - Detected frameworks: ${detectedFrameworks.join(', ')}`);

            // 打印框架统计
            for (const [framework, count] of stats.frameworkCounts.entries()) {
                logger.info(`   - ${framework}: ${count} files`);
            }

            return {
                detectedFrameworks,
                techStackDetections: techStackDetections,
                totalSoFiles: techStackDetections.length
            };
        } catch (error) {
            logger.error('❌ TechStack analysis failed:', error);
            throw error;
        }
    }

    // ---- 日志和格式化 ----
    /**
     * 记录ZIP信息
     */
    private logZipInfo(zipAdapter: EnhancedJSZipAdapter): void {
        const fileCount = Object.keys(zipAdapter.files).length;
        logger.info(`ZIP已加载，发现 ${fileCount} 个条目`);
        logger.info(`未压缩总大小：${this.formatBytes(zipAdapter.getTotalUncompressedSize())}`);
        logger.info(`压缩后总大小：${this.formatBytes(zipAdapter.getTotalCompressedSize())}`);
        logger.info(`总体压缩比：${(zipAdapter.getOverallCompressionRatio() * 100).toFixed(1)}%`);
        logger.info('ZIP内文件列表：');
        Object.keys(zipAdapter.files).forEach((filePath) => {
            logger.info(`  - ${filePath}`);
        });
    }

    /**
     * 记录分析结果
     */
    private logAnalysisResults(result: HapStaticAnalysisResult): void {
        logger.info('\n=== HAP 静态分析结果 ===');
        logger.info(`HAP文件：${result.hapPath}`);
        logger.info(`分析时间：${result.timestamp.toISOString()}`);

        // SO文件分析结果
        logger.info('\n--- SO 分析 ---');
        logger.info(`SO文件总数：${result.soAnalysis.totalSoFiles}`);
        logger.info(`识别到的框架：${result.soAnalysis.detectedFrameworks.join(', ') || '无'}`);

        if (result.soAnalysis.techStackDetections.length > 0) {
            logger.info('SO 文件列表:');
            for (const soFile of result.soAnalysis.techStackDetections) {
                logger.info(`  - ${soFile.file}（${soFile.techStack}）`);
            }
        }

        // 资源文件分析结果
        logger.info('\n--- 资源分析 ---');
        logger.info(`文件总数：${result.resourceAnalysis.totalFiles}（包含嵌套）`);
        logger.info(`总大小：${this.formatBytes(result.resourceAnalysis.totalSize)}`);
        logger.info(`压缩文件：${result.resourceAnalysis.archiveFiles.length}`);
        logger.info(`JS文件：${result.resourceAnalysis.jsFiles.length}`);
        logger.info(`Hermes字节码文件：${result.resourceAnalysis.hermesFiles.length}`);

        if (result.resourceAnalysis.extractedArchiveCount > 0) {
            logger.info(`已解压压缩包数量：${result.resourceAnalysis.extractedArchiveCount}`);
            logger.info(`最大解压深度：${result.resourceAnalysis.maxExtractionDepth}`);
        }

        if (result.resourceAnalysis.filesByType.size > 0) {
            logger.info('按类型统计:');
            for (const [fileType, files] of result.resourceAnalysis.filesByType) {
                const totalSize = files.reduce((sum, file) => sum + file.fileSize, 0);
                logger.info(`  - ${fileType}: ${files.length} 个文件（${this.formatBytes(totalSize)}）`);
            }
        }

        // 显示压缩文件详情
        if (result.resourceAnalysis.archiveFiles.length > 0) {
            logger.info('\n压缩文件详情:');
            for (const archive of result.resourceAnalysis.archiveFiles) {
                logger.info(`  - ${archive.fileName}（${this.formatBytes(archive.fileSize)}）`);
                if (archive.extracted) {
                    logger.info(`    ✓ 已解压：${archive.entryCount} 个文件，深度：${archive.extractionDepth}`);
                    if (archive.nestedFiles && archive.nestedFiles.length > 0) {
                        const nestedByType = new Map<string, number>();
                        for (const file of archive.nestedFiles) {
                            nestedByType.set(file.fileType, (nestedByType.get(file.fileType) ?? 0) + 1);
                        }
                        logger.info(
                            `    └─ 嵌套文件：${Array.from(nestedByType.entries())
                                .map(([type, count]) => `${type}(${count})`)
                                .join(', ')}`
                        );
                    }
                } else {
                    logger.info('    ✗ 未解压（深度限制或错误）');
                }
            }
        }
        logger.info('=====================================\n');
    }

    /**
     * 记录分析摘要
     */
    private logAnalysisSummary(hapFilePath: string, processingTime: number, result: HapStaticAnalysisResult): void {
        logger.info('\n=== HAP 分析摘要 ===');
        logger.info(`文件：${hapFilePath}`);
        logger.info(`处理时间：${processingTime}ms`);
        logger.info(`SO文件：${result.soAnalysis.totalSoFiles}`);
        logger.info(`资源文件：${result.resourceAnalysis.totalFiles}`);
        logger.info(`总大小：${this.formatBytes(result.resourceAnalysis.totalSize)}`);
        logger.info('==================\n');
    }

    /**
     * 格式化字节数
     */
    private formatBytes(bytes: number): string {
        if (bytes === 0) { return '0 B'; }

        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));

        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }
}
