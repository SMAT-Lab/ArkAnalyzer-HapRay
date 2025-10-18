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
import os from 'os';
import JSZip from 'jszip';
import { fileExists, ensureDirectoryExists, getAllFiles } from '../../utils/file_utils';
import { ErrorFactory } from '../../errors';
import Logger, { LOG_MODULE_TYPE } from 'arkanalyzer/lib/utils/logger';
import { DetectorEngine } from '../../core/techstack/detector/detector-engine';
import type { FormatOptions } from '../report';
import { FormatterFactory, OutputFormat } from '../report';
import { Hap, type TechStackDetection } from '../../core/hap/hap_parser';
import { ZipUtils } from '../../utils/zip_utils';
import type { FileDetectionResult } from '../../core/techstack/types';

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
     * 分析多个HAP/ZIP文件或目录
     * @param inputPath 输入路径（文件或目录）
     * @param outputDir 输出目录
     * @param format 输出格式
     * @param jobs 并发数量
     */
    public async analyzeMultipleHaps(
        inputPath: string, 
        outputDir: string, 
        format: string, 
        jobs?: string
    ): Promise<void> {
        if (!fs.existsSync(inputPath)) {
            throw ErrorFactory.createHapFileError(`Input not found: ${inputPath}`, inputPath);
        }

        const supportedFormats = [...FormatterFactory.getSupportedFormats(), 'all'];
        if (!supportedFormats.includes(format)) {
            throw new Error(`Unsupported output format: ${format}. Supported formats: ${supportedFormats.join(', ')}`);
        }

        ensureDirectoryExists(outputDir);

        logger.info(`分析目标：${inputPath}`);
        logger.info(`输出目录：${outputDir}`);
        logger.info(`输出格式：${format}`);

        const targets = await this.collectAnalysisTargets(inputPath);
        if (targets.length === 0) {
            logger.warn('未发现可分析的目标（.hap 文件或包含 .hap 的目录）。');
            return;
        }

        const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
        const maxJobs = jobs === 'auto' ? os.cpus().length : parseInt(String(jobs ?? '4'), 10);
        
        logger.info(`开始并行分析 ${targets.length} 个HAP包，并发数：${maxJobs}...`);
        
        const analysisResults = await this.runWithConcurrency(targets, maxJobs, async (t) => {
            const startTime = Date.now();
            try {
                const result = await this.analyzeHap(t.label, outputDir);
                const duration = Date.now() - startTime;

                const baseName = this.sanitizeBaseName(t.outputBase);
                const perTargetOutput = path.join(outputDir, baseName);
                ensureDirectoryExists(perTargetOutput);

                // 生成报告
                if (format === 'all') {
                    const formats: Array<OutputFormat> = [OutputFormat.JSON, OutputFormat.HTML, OutputFormat.EXCEL];
                    logger.info(`为 ${baseName} 生成所有输出格式...`);
                    for (const currentFormat of formats) {
                        await this.generateReport(result, currentFormat, baseName, timestamp, perTargetOutput);
                    }
                } else {
                    await this.generateReport(result, format as OutputFormat, baseName, timestamp, perTargetOutput);
                }

                return { success: true, target: t, result, duration };
            } catch (error) {
                const duration = Date.now() - startTime;
                logger.error(`分析失败：${t.relativePath} 用时 ${duration}ms`, error);
                return { success: false, target: t, error, duration };
            }
        });
        
        // 统计结果
        const successful = analysisResults.filter(r => r.success).length;
        const failed = analysisResults.filter(r => !r.success).length;
        const totalDuration = analysisResults.reduce((sum, r) => sum + r.duration, 0);
        
        logger.info('\n=== 分析完成统计 ===');
        logger.info(`总目标数：${targets.length}`);
        logger.info(`成功：${successful}`);
        logger.info(`失败：${failed}`);
        logger.info(`总耗时：${totalDuration}ms`);
        logger.info(`平均耗时：${Math.round(totalDuration / targets.length)}ms`);

        if (failed > 0) {
            logger.warn(`有 ${failed} 个HAP包分析失败，请检查日志`);
        }
    }

    /**
     * 分析HAP/ZIP文件
     * @param hapFilePath 文件路径（.hap/.zip等）
     * @param outputDir 输出目录
     */
    public async analyzeHap(hapFilePath: string, outputDir?: string): Promise<Hap> {
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
    public async analyzeZipData(sourceLabel: string, zipData: Buffer, _outputDir?: string): Promise<Hap> {
        if (this.verbose) {
            logger.info(`开始分析：${sourceLabel}`);
        }

        try {
            // 直接使用 JSZip 解析
            const zip = await JSZip.loadAsync(zipData);
            
            if (this.verbose) {
                this.logZipInfo(zip);
            }

            // 执行分析
            const analysisResult = await this.performAnalysis(zip, sourceLabel);
            
            if (this.verbose) {
                this.logAnalysisResults(analysisResult);
            }
            
            return analysisResult;
        } catch (error) {
            throw ErrorFactory.createZipParsingError(
                `Failed to parse as ZIP: ${sourceLabel}`,
                sourceLabel,
                error instanceof Error ? error : new Error(String(error))
            );
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


    // ---- 分析执行 ----
    /**
     * 执行核心分析逻辑（直接调用技术栈检测）
     */
    private async performAnalysis(
        zip: JSZip,
        sourceLabel: string
    ): Promise<Hap> {
        // 创建 Hap 实例
        const hap = await Hap.loadFromHap(sourceLabel);
        
        // 执行技术栈分析
        const techStackDetections = await this.runTechStackAnalysis(zip);
        
        // 将技术栈检测结果设置到 Hap 实例中
        hap.techStackDetections = techStackDetections;
        
        return hap;
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
    private async runTechStackAnalysis(zip: JSZip): Promise<
    Array<TechStackDetection>
    > {
        this.ensureDetectorInitialized();

        const startTime = Date.now();
        logger.info('🔍 Starting TechStack analysis...');

        try {
            // 1. 扫描 ZIP 文件，提取所有文件（包括嵌套压缩包）
            const fileInfos = await ZipUtils.scanZipWithNestedSupport(zip);

            logger.info(`📁 Scanned ${fileInfos.length} files from HAP (including nested archives)`);

            // 2. 并行检测所有文件
            const detectionResults = await this.detectorEngine.detectFiles(fileInfos);

            // 3. 直接转换为 TechStackDetection 格式
            const techStackDetections = this.convertToTechStackDetections(detectionResults);

            // 4. 提取所有检测到的技术栈
            const detectedTechStacks = this.extractAllTechStacks(detectionResults);

            // 5. 统计信息
            const stats = this.getDetectionStats(detectionResults);
            const duration = Date.now() - startTime;

            logger.info(`✅ TechStack analysis completed in ${duration}ms`);
            logger.info(`   - Total files: ${stats.totalFiles}`);
            logger.info(`   - Detected files: ${stats.detectedFiles}`);
            logger.info(`   - Total detections: ${stats.totalDetections}`);
            logger.info(`   - Detected tech stacks: ${detectedTechStacks.join(', ')}`);

            // 打印技术栈统计
            for (const [techStack, count] of stats.techStackCounts.entries()) {
                logger.info(`   - ${techStack}: ${count} files`);
            }

            return techStackDetections;
        
        } catch (error) {
            logger.error('❌ TechStack analysis failed:', error);
            throw error;
        }
    }

    /**
     * 记录ZIP信息
     */
    private logZipInfo(zip: JSZip): void {
        const fileCount = Object.keys(zip.files).length;
        logger.info(`ZIP已加载，发现 ${fileCount} 个条目`);
        
        logger.info('ZIP内文件列表：');
        Object.keys(zip.files).forEach((filePath) => {
            logger.info(`  - ${filePath}`);
        });
    }

    /**
     * 记录分析结果
     */
    private logAnalysisResults(result: Hap): void {
        logger.info('\n=== HAP 静态分析结果 ===');
        logger.info(`HAP文件：${result.hapPath}`);
        logger.info(`包名：${result.bundleName}`);
        logger.info(`应用名：${result.appName}`);
        logger.info(`版本：${result.versionName} (${result.versionCode})`);

        // 技术栈分析结果
        logger.info('\n--- 技术栈分析 ---');
        logger.info(`检测到的技术栈文件总数：${result.techStackDetections.length}`);
        
        if (result.techStackDetections.length > 0) {
            const techStacks = [...new Set(result.techStackDetections.map(d => d.techStack))];
            logger.info(`识别到的技术栈：${techStacks.join(', ') || '无'}`);
            
            logger.info('技术栈文件列表:');
            for (const detection of result.techStackDetections) {
                logger.info(`  - ${detection.file}（${detection.techStack}）`);
            }
        }

        logger.info('=====================================\n');
    }

    /**
     * 记录分析摘要
     */
    private logAnalysisSummary(hapFilePath: string, processingTime: number, result: Hap): void {
        logger.info('\n=== HAP 分析摘要 ===');
        logger.info(`文件：${hapFilePath}`);
        logger.info(`处理时间：${processingTime}ms`);
        logger.info(`包名：${result.bundleName}`);
        logger.info(`应用名：${result.appName}`);
        logger.info(`技术栈文件：${result.techStackDetections.length}`);
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

    /**
     * 生成报告
     */
    private async generateReport(
        result: Hap,
        format: OutputFormat,
        baseName: string,
        timestamp: string,
        output: string
    ): Promise<void> {
        const formatter = FormatterFactory.create({
            format: format,
            outputPath: '',
            includeDetails: true,
            pretty: true
        });

        const fileExtension = formatter.getFileExtension();
        const outputFile = path.join(output, `${timestamp}${fileExtension}`);

        const formatOptions: FormatOptions = {
            format: format,
            outputPath: outputFile,
            includeDetails: true,
            pretty: true
        };

        const finalFormatter = FormatterFactory.create(formatOptions);
        const formatResult = await finalFormatter.format(result);

        if (formatResult.success) {
            logger.info(`${format.toUpperCase()} 报告已生成：${formatResult.filePath}`);
            logger.info(`文件大小：${this.formatFileSize(formatResult.fileSize)}`);
            logger.info(`格式化耗时：${formatResult.duration}ms`);
        } else {
            logger.error(`生成 ${format.toUpperCase()} 报告失败：${formatResult.error}`);
            throw new Error(`生成 ${format.toUpperCase()} 报告失败`);
        }
    }

    /**
     * 格式化文件大小
     */
    private formatFileSize(bytes: number): string {
        if (bytes === 0) { return '0 B'; }
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    /**
     * 清理基础名称
     */
    private sanitizeBaseName(name: string): string {
        return name.replace(/[^a-zA-Z0-9_\-\.\/\\]+/g, '_');
    }

    /**
     * 收集分析目标
     */
    private async collectAnalysisTargets(inputPath: string): Promise<Array<{ label: string; data?: Buffer; outputBase: string; relativePath: string }>> {
        const targets: Array<{ label: string; data?: Buffer; outputBase: string; relativePath: string }> = [];
        const stat = fs.statSync(inputPath);
        if (stat.isDirectory()) {
            // 递归收集.hap文件
            const files = getAllFiles(inputPath, { exts: ['.hap'] });
            for (const f of files) {
                // 计算相对于输入目录的相对路径
                const relativePath = path.relative(inputPath, f);
                // 移除文件扩展名，保留目录结构
                const relativeDir = path.dirname(relativePath);
                const fileName = path.basename(f, path.extname(f));
                // 始终保留目录结构，即使目录是当前目录
                const outputBase = relativeDir === '.' ? fileName : path.join(relativeDir, fileName);
                
                targets.push({ 
                    label: f, 
                    outputBase: outputBase,
                    relativePath: relativePath
                });
            }
        } else if (stat.isFile()) {
            const ext = path.extname(inputPath).toLowerCase();
            if (ext === '.hap' || ext === '.zip') {
                const fileName = path.basename(inputPath, ext);
                targets.push({ 
                    label: inputPath, 
                    outputBase: fileName,
                    relativePath: path.basename(inputPath)
                });
            } else {
                logger.warn(`Unsupported file type: ${inputPath}. Only .hap or .zip are supported as files.`);
            }
        }
        return targets;
    }

    /**
     * 并发控制执行函数
     */
    private async runWithConcurrency<T, R>(
        items: Array<T>,
        concurrency: number,
        processor: (item: T) => Promise<R>
    ): Promise<Array<R>> {
        const results: Array<R> = [];
        
        for (let i = 0; i < items.length; i += concurrency) {
            const batch = items.slice(i, i + concurrency);
            const batchPromises = batch.map(processor);
            const batchResults = await Promise.all(batchPromises);
            results.push(...batchResults);
        }
        
        return results;
    }

    /**
     * 将文件检测结果转换为 TechStackDetection 格式
     */
    private convertToTechStackDetections(fileDetections: Array<FileDetectionResult>): Array<TechStackDetection> {
        const results: Array<TechStackDetection> = [];

        for (const fileDetection of fileDetections) {
            // 只处理检测到技术栈的文件
            if (fileDetection.detections.length === 0) {
                continue;
            }

            // 提取技术栈（取第一个检测到的技术栈）
            const firstDetection = fileDetection.detections[0];
            const techStack = firstDetection.techStack;
            const fileType = firstDetection.ruleName;
            const confidence = firstDetection.confidence;

            // 合并所有元数据
            const metadata = this.mergeMetadata(fileDetection.detections);

            results.push({
                folder: fileDetection.folder,
                file: fileDetection.file,
                size: fileDetection.size,
                techStack,
                fileType,
                confidence,
                metadata
            });
        }

        return results;
    }

    /**
     * 合并所有检测结果的元数据
     */
    private mergeMetadata(detections: Array<{ metadata: Record<string, unknown> }>): Record<string, unknown> {
        const merged: Record<string, unknown> = {};

        for (const detection of detections) {
            // 合并元数据
            Object.assign(merged, detection.metadata);
        }

        return merged;
    }

    /**
     * 提取所有检测到的技术栈（去重）
     */
    private extractAllTechStacks(fileDetections: Array<FileDetectionResult>): Array<string> {
        const techStacks = new Set<string>();

        for (const fileDetection of fileDetections) {
            for (const detection of fileDetection.detections) {
                techStacks.add(detection.techStack);
            }
        }

        return Array.from(techStacks);
    }

    /**
     * 统计检测结果
     */
    private getDetectionStats(fileDetections: Array<FileDetectionResult>): {
        totalFiles: number;
        detectedFiles: number;
        totalDetections: number;
        techStackCounts: Map<string, number>;
    } {
        const techStackCounts = new Map<string, number>();
        let detectedFiles = 0;
        let totalDetections = 0;

        for (const fileDetection of fileDetections) {
            if (fileDetection.detections.length > 0) {
                detectedFiles++;
                totalDetections += fileDetection.detections.length;

                for (const detection of fileDetection.detections) {
                    const count = techStackCounts.get(detection.techStack) ?? 0;
                    techStackCounts.set(detection.techStack, count + 1);
                }
            }
        }

        return {
            totalFiles: fileDetections.length,
            detectedFiles,
            totalDetections,
            techStackCounts
        };
    }
}
