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
import writeXlsxFile from 'write-excel-file/node';
import type { SheetData } from 'write-excel-file';
import { fileExists, ensureDirectoryExists, getAllFiles } from '../../utils/file_utils';
import { ErrorFactory } from '../../errors';
import Logger, { LOG_MODULE_TYPE } from 'arkanalyzer/lib/utils/logger';
import { DetectorEngine } from '../../core/techstack/detector/detector-engine';
import type { FormatOptions } from '../../core/techstack/report';
import { FormatterFactory, OutputFormat } from '../../core/techstack/report';
import { Hap, type TechStackDetection } from '../../core/hap/hap_parser';
import { ZipUtils } from '../../utils/zip_utils';
import { isBinaryFile } from '../../utils/file_utils';
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
     * @param jobs 并发数量
     */
    public async analyzeMultipleHaps(
        inputPath: string,
        outputDir: string,
        jobs?: string
    ): Promise<void> {
        if (!fs.existsSync(inputPath)) {
            throw ErrorFactory.createHapFileError(`Input not found: ${inputPath}`, inputPath);
        }

        ensureDirectoryExists(outputDir);

        logger.info(`分析目标：${inputPath}`);
        logger.info(`输出目录：${outputDir}`);

        const stat = fs.statSync(inputPath);

        // 如果是单个文件，直接分析
        if (stat.isFile()) {
            await this.analyzeSingleFile(inputPath, outputDir);
            return;
        }

        // 如果是目录，检查是否是应用包目录格式
        const dirName = path.basename(inputPath);
        if (this.isAppPackageDirectory(dirName)) {
            // 单个应用包目录：收集所有.hap/.hsp文件，生成一个报告
            await this.analyzeSingleAppDirectory(inputPath, outputDir);
        } else {
            // 多应用目录：搜索所有符合格式的子目录
            await this.analyzeMultipleAppDirectories(inputPath, outputDir, jobs);
        }
    }

    /**
     * 分析单个文件
     */
    private async analyzeSingleFile(filePath: string, outputDir: string): Promise<void> {
        const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
        const ext = path.extname(filePath).toLowerCase();

        if (ext !== '.hap' && ext !== '.hsp' && ext !== '.zip') {
            logger.warn(`Unsupported file type: ${filePath}. Only .hap, .hsp or .zip are supported.`);
            return;
        }

        logger.info(`分析单个文件：${filePath}`);
        const result = await this.analyzeHap(filePath, outputDir);

        const fileName = path.basename(filePath, ext);
        const perTargetOutput = path.join(outputDir, fileName);
        ensureDirectoryExists(perTargetOutput);

        // 生成报告
        const formats: Array<OutputFormat> = [OutputFormat.JSON, OutputFormat.HTML, OutputFormat.EXCEL];
        for (const currentFormat of formats) {
            await this.generateReport(result, currentFormat, fileName, timestamp, perTargetOutput);
        }

        logger.info(`✅ 文件分析完成：${filePath}`);
    }

    /**
     * 分析单个应用包目录（xxxxx@xxxx格式）
     */
    private async analyzeSingleAppDirectory(appDir: string, outputDir: string): Promise<void> {
        const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
        const dirName = path.basename(appDir);
        const appInfo = this.parseAppPackageDirectory(dirName);

        if (!appInfo) {
            logger.error(`无法解析应用包目录名：${dirName}`);
            return;
        }

        logger.info(`分析应用包目录：${dirName}`);
        logger.info(`  包名：${appInfo.packageName}`);
        logger.info(`  版本：${appInfo.version}`);

        // 收集目录下所有.hap/.hsp文件
        const files = getAllFiles(appDir, { exts: ['.hap', '.hsp'] });
        if (files.length === 0) {
            logger.warn(`目录 ${appDir} 中未发现.hap/.hsp文件`);
            return;
        }

        logger.info(`发现 ${files.length} 个HAP/HSP文件`);

        // 先找到entry类型的主包，获取正确的版本信息
        const entryHap = await this.findEntryHap(files);

        // 分析所有文件并合并结果
        const allDetections: Array<TechStackDetection> = [];
        const allResults: Array<Hap> = [];
        let combinedResult: Hap | null = null;

        for (const file of files) {
            logger.info(`  分析文件：${path.basename(file)}`);
            const result = await this.analyzeHap(file, outputDir);

            // 优先使用entry HAP的结果作为基础
            if (entryHap && result.hapPath === entryHap.hapPath) {
                combinedResult = result;
                logger.info(`  使用entry HAP的版本信息：${result.versionName} (${result.versionCode})`);
            } else {
                combinedResult ??= result;
            }
            allResults.push(result);

            // 合并技术栈检测结果
            allDetections.push(...result.techStackDetections);
        }

        if (combinedResult) {
            // 更新合并后的结果
            combinedResult.techStackDetections = allDetections;
            combinedResult.hapPath = appDir; // 使用目录路径

            // 如果找到了entry HAP，使用它的版本信息（已经在上面设置了）
            // 如果没有找到entry HAP，使用目录名作为后备
            if (entryHap) {
                combinedResult.bundleName = entryHap.bundleName;
                combinedResult.versionName = entryHap.versionName;
                combinedResult.versionCode = entryHap.versionCode;
                combinedResult.appName = entryHap.appName;
                logger.info(`  使用entry HAP的版本信息：${entryHap.versionName} (${entryHap.versionCode})`);
            } else {
                // 没有找到entry HAP，使用目录名作为后备
                logger.warn('  未找到entry类型的主应用包，使用目录名的版本信息');
                combinedResult.bundleName = appInfo.packageName;
                combinedResult.versionName = appInfo.version;
                // versionCode 从版本名称推导
                const versionParts = appInfo.version.split('.');
                if (versionParts.length >= 3) {
                    const major = parseInt(versionParts[0]) || 0;
                    const minor = parseInt(versionParts[1]) || 0;
                    const patch = parseInt(versionParts[2]) || 0;
                    combinedResult.versionCode = major * 1000000 + minor * 1000 + patch;
                }
            }

            // 生成报告到应用包目录名的子目录
            const perTargetOutput = path.join(outputDir, dirName);
            ensureDirectoryExists(perTargetOutput);

            const formats: Array<OutputFormat> = [OutputFormat.JSON, OutputFormat.HTML, OutputFormat.EXCEL];
            for (const currentFormat of formats) {
                await this.generateReport(combinedResult, currentFormat, dirName, timestamp, perTargetOutput);
            }

            logger.info(`✅ 应用包目录分析完成：${dirName}`);
        }
    }

    /**
     * 分析多个应用包目录
     */
    private async analyzeMultipleAppDirectories(rootDir: string, outputDir: string, jobs?: string): Promise<void> {
        logger.info('搜索应用包目录（格式：xxxxx@xxxx）...');

        // 搜索所有符合格式的子目录
        const appDirs: Array<string> = [];
        const entries = fs.readdirSync(rootDir, { withFileTypes: true });

        for (const entry of entries) {
            if (entry.isDirectory() && this.isAppPackageDirectory(entry.name)) {
                const fullPath = path.join(rootDir, entry.name);
                appDirs.push(fullPath);
            }
        }

        if (appDirs.length === 0) {
            logger.warn('未发现符合格式的应用包目录');
            // 回退到原有逻辑：收集所有.hap/.hsp文件
            const targets = await this.collectAnalysisTargets(rootDir);
            if (targets.length === 0) {
                logger.warn('未发现可分析的目标（.hap/.hsp 文件）。');
                return;
            }
            await this.analyzeTargetsWithConcurrency(targets, outputDir, jobs);
            return;
        }

        logger.info(`发现 ${appDirs.length} 个应用包目录`);

        // 分析每个应用包目录
        const allResults: Array<{ appDir: string; result: Hap }> = [];

        for (const appDir of appDirs) {
            const dirName = path.basename(appDir);
            logger.info(`\n处理应用包目录：${dirName}`);

            try {
                const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
                const appInfo = this.parseAppPackageDirectory(dirName);

                if (!appInfo) {
                    logger.error(`无法解析应用包目录名：${dirName}`);
                    continue;
                }

                // 收集目录下所有.hap/.hsp文件
                const files = getAllFiles(appDir, { exts: ['.hap', '.hsp'] });
                if (files.length === 0) {
                    logger.warn(`目录 ${dirName} 中未发现.hap/.hsp文件`);
                    continue;
                }

                logger.info(`  发现 ${files.length} 个HAP/HSP文件`);

                // 先找到entry类型的主包，获取正确的版本信息
                const entryHap = await this.findEntryHap(files);

                // 分析所有文件并合并结果
                const allDetections: Array<TechStackDetection> = [];
                let combinedResult: Hap | null = null;

                for (const file of files) {
                    logger.info(`    分析文件：${path.basename(file)}`);
                    const result = await this.analyzeHap(file, outputDir);

                    // 优先使用entry HAP的结果作为基础
                    if (entryHap && result.hapPath === entryHap.hapPath) {
                        combinedResult = result;
                        logger.info(`    使用entry HAP的版本信息：${result.versionName} (${result.versionCode})`);
                    } else {
                        combinedResult ??= result;
                    }

                    // 合并技术栈检测结果
                    allDetections.push(...result.techStackDetections);
                }

                if (combinedResult) {
                    // 更新合并后的结果
                    combinedResult.techStackDetections = allDetections;
                    combinedResult.hapPath = appDir;

                    // 如果找到了entry HAP，使用它的版本信息
                    // 如果没有找到entry HAP，使用目录名作为后备
                    if (entryHap) {
                        combinedResult.bundleName = entryHap.bundleName;
                        combinedResult.versionName = entryHap.versionName;
                        combinedResult.versionCode = entryHap.versionCode;
                        combinedResult.appName = entryHap.appName;
                        logger.info(`    使用entry HAP的版本信息：${entryHap.versionName} (${entryHap.versionCode})`);
                    } else {
                        // 没有找到entry HAP，使用目录名作为后备
                        logger.warn('    未找到entry类型的主应用包，使用目录名的版本信息');
                        combinedResult.bundleName = appInfo.packageName;
                        combinedResult.versionName = appInfo.version;
                        // versionCode 从版本名称推导
                        const versionParts = appInfo.version.split('.');
                        if (versionParts.length >= 3) {
                            const major = parseInt(versionParts[0]) || 0;
                            const minor = parseInt(versionParts[1]) || 0;
                            const patch = parseInt(versionParts[2]) || 0;
                            combinedResult.versionCode = major * 1000000 + minor * 1000 + patch;
                        }
                    }

                    // 生成报告到应用包目录名的子目录
                    const perTargetOutput = path.join(outputDir, dirName);
                    ensureDirectoryExists(perTargetOutput);

                    const formats: Array<OutputFormat> = [OutputFormat.JSON, OutputFormat.HTML, OutputFormat.EXCEL];
                    for (const currentFormat of formats) {
                        await this.generateReport(combinedResult, currentFormat, dirName, timestamp, perTargetOutput);
                    }

                    allResults.push({ appDir: dirName, result: combinedResult });
                    logger.info(`  ✅ 完成：${dirName}`);
                }
            } catch (error) {
                logger.error(`  ❌ 分析失败：${dirName}`, error);
            }
        }

        // 生成汇总Excel
        if (allResults.length > 0) {
            await this.generateSummaryExcel(allResults, outputDir);
        }

        logger.info('\n=== 多应用分析完成 ===');
        logger.info(`总应用数：${appDirs.length}`);
        logger.info(`成功：${allResults.length}`);
        logger.info(`失败：${appDirs.length - allResults.length}`);
    }

    /**
     * 使用并发分析目标（回退逻辑）
     */
    private async analyzeTargetsWithConcurrency(
        targets: Array<{ label: string; data?: Buffer; outputBase: string; relativePath: string }>,
        outputDir: string,
        jobs?: string
    ): Promise<void> {
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
                const formats: Array<OutputFormat> = [OutputFormat.JSON, OutputFormat.HTML, OutputFormat.EXCEL];
                logger.info(`为 ${baseName} 生成所有输出格式...`);
                for (const currentFormat of formats) {
                    await this.generateReport(result, currentFormat, baseName, timestamp, perTargetOutput);
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
        const isZipLike = lower.endsWith('.hap') || lower.endsWith('.hsp') || lower.endsWith('.zip');
        if (!isZipLike && this.verbose) {
            logger.warn(`Input file does not have .hap/.hsp/.zip extension: ${hapFilePath}. Will attempt ZIP parsing.`);
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

        // 为每个检测结果添加来源信息
        techStackDetections.forEach(detection => {
            detection.sourceHapPath = sourceLabel;
            detection.sourceBundleName = hap.bundleName;
            detection.sourceVersionCode = hap.versionCode;
            detection.sourceVersionName = hap.versionName;
        });

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
     * 生成汇总Excel文件
     */
    private async generateSummaryExcel(
        allResults: Array<{ appDir: string; result: Hap }>,
        outputDir: string
    ): Promise<void> {
        logger.info('\n生成汇总Excel...');

        const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
        const summaryPath = path.join(outputDir, `summary_${timestamp}.xlsx`);

        // 收集所有可能的 metadata 字段
        const metadataColumns = new Set<string>();
        for (const { result } of allResults) {
            const filteredDetections = result.techStackDetections.filter(d => d.techStack !== 'Unknown');
            for (const detection of filteredDetections) {
                Object.keys(detection.metadata).forEach(key => {
                    metadataColumns.add(key);
                });
            }
        }
        const sortedMetadataColumns = Array.from(metadataColumns).sort();

        // 1. 创建应用汇总工作表
        const summarySheetData = this.createSummarySheetData(allResults);

        // 2. 创建技术栈详情工作表
        const detailSheetData = this.createDetailSheetData(allResults, sortedMetadataColumns);

        // 3. 创建技术栈分析汇总工作表
        const analysisSheetData = this.createTechStackAnalysisSheetData(allResults);

        // 4. 创建Dart开源库汇总工作表
        const dartPackagesSheetData = this.createDartPackagesSheetData(allResults);

        // 写入Excel文件
        const sheets = [summarySheetData, detailSheetData, analysisSheetData];
        const sheetNames = ['应用汇总', '技术栈详情', '技术栈分析'];

        // 如果有Dart包数据，添加Dart开源库sheet
        if (dartPackagesSheetData.length > 1) { // 大于1表示有数据行（第一行是标题）
            sheets.push(dartPackagesSheetData);
            sheetNames.push('Dart开源库');
        }

        await writeXlsxFile(sheets, {
            sheets: sheetNames,
            filePath: summaryPath
        });

        logger.info(`✅ 汇总Excel已生成：${summaryPath}`);
    }

    /**
     * 创建应用汇总工作表数据
     */
    private createSummarySheetData(
        allResults: Array<{ appDir: string; result: Hap }>
    ): SheetData {
        const sheetData: SheetData = [];

        // 表头
        sheetData.push([
            { value: '应用目录', fontWeight: 'bold' as const },
            { value: '包名', fontWeight: 'bold' as const },
            { value: '应用名', fontWeight: 'bold' as const },
            { value: '版本名称', fontWeight: 'bold' as const },
            { value: '版本代码', fontWeight: 'bold' as const },
            { value: '技术栈文件总数', fontWeight: 'bold' as const },
            { value: '检测到的技术栈', fontWeight: 'bold' as const },
            { value: '总文件大小', fontWeight: 'bold' as const }
        ]);

        // 填充数据
        for (const { appDir, result } of allResults) {
            const filteredDetections = result.techStackDetections.filter(d => d.techStack !== 'Unknown');
            const detectedTechStacks = [...new Set(filteredDetections.map(d => d.techStack))];
            const totalFileSize = filteredDetections.reduce((sum, item) => sum + item.size, 0);

            sheetData.push([
                { value: appDir, type: String },
                { value: result.bundleName, type: String },
                { value: result.appName, type: String },
                { value: result.versionName, type: String },
                { value: result.versionCode, type: Number },
                { value: filteredDetections.length, type: Number },
                { value: detectedTechStacks.join(', ') || '无', type: String },
                { value: this.formatFileSize(totalFileSize), type: String }
            ]);
        }

        return sheetData;
    }

    /**
     * 创建技术栈详情工作表数据
     */
    private createDetailSheetData(
        allResults: Array<{ appDir: string; result: Hap }>,
        metadataColumns: Array<string>
    ): SheetData {
        const sheetData: SheetData = [];

        // 表头
        const headerRow = [
            { value: '应用目录', fontWeight: 'bold' as const },
            { value: '包名', fontWeight: 'bold' as const },
            { value: '文件夹', fontWeight: 'bold' as const },
            { value: '文件名', fontWeight: 'bold' as const },
            { value: '技术栈', fontWeight: 'bold' as const },
            { value: '文件类型', fontWeight: 'bold' as const },
            { value: '二进制/文本', fontWeight: 'bold' as const },
            { value: '文件大小', fontWeight: 'bold' as const },
            { value: '置信度', fontWeight: 'bold' as const },
            { value: '来源HAP包', fontWeight: 'bold' as const },
            { value: '来源包名', fontWeight: 'bold' as const },
            { value: '来源版本号', fontWeight: 'bold' as const },
            { value: '来源版本名称', fontWeight: 'bold' as const }
        ];

        // 添加 metadata 列到表头
        for (const column of metadataColumns) {
            headerRow.push({ value: column, fontWeight: 'bold' as const });
        }
        sheetData.push(headerRow);

        // 填充数据
        for (const { appDir, result } of allResults) {
            const filteredDetections = result.techStackDetections.filter(d => d.techStack !== 'Unknown');

            for (const detection of filteredDetections) {
                const confidenceStr = detection.confidence !== undefined
                    ? `${(detection.confidence * 100).toFixed(0)}%`
                    : '-';

                // 二进制/文本标识
                const binaryTypeStr = detection.isBinary === true ? 'Binary' :
                    detection.isBinary === false ? 'Text' : '-';

                const row = [
                    { value: appDir, type: String },
                    { value: result.bundleName, type: String },
                    { value: detection.folder, type: String },
                    { value: detection.file, type: String },
                    { value: detection.techStack, type: String },
                    { value: detection.fileType ?? '-', type: String },
                    { value: binaryTypeStr, type: String },
                    { value: this.formatFileSize(detection.size), type: String },
                    { value: confidenceStr, type: String },
                    { value: detection.sourceHapPath ?? '-', type: String },
                    { value: detection.sourceBundleName ?? '-', type: String },
                    { value: detection.sourceVersionCode?.toString() ?? '-', type: String },
                    { value: detection.sourceVersionName ?? '-', type: String }
                ];

                // 添加 metadata 字段
                for (const column of metadataColumns) {
                    const value = detection.metadata[column];
                    let cellValue = '';
                    if (value !== undefined && value !== null) {
                        if (Array.isArray(value)) {
                            cellValue = value.join(os.EOL);
                        } else {
                            cellValue = String(value);
                        }
                    }
                    row.push({ value: cellValue, type: String });
                }

                sheetData.push(row);
            }
        }

        return sheetData;
    }

    /**
     * 创建技术栈分析汇总工作表数据
     */
    private createTechStackAnalysisSheetData(
        allResults: Array<{ appDir: string; result: Hap }>
    ): SheetData {
        const sheetData: SheetData = [];

        // 统计数据
        const techStackStats = new Map<string, {
            appCount: number;
            fileCount: number;
            totalSize: number;
            apps: Set<string>;
        }>();

        const appTechStackStats = new Map<string, Map<string, number>>();

        // 收集统计数据
        for (const { appDir, result } of allResults) {
            const filteredDetections = result.techStackDetections.filter(d => d.techStack !== 'Unknown');
            const appTechStacks = new Map<string, number>();

            for (const detection of filteredDetections) {
                const techStack = detection.techStack;

                // 技术栈总体统计
                if (!techStackStats.has(techStack)) {
                    techStackStats.set(techStack, {
                        appCount: 0,
                        fileCount: 0,
                        totalSize: 0,
                        apps: new Set()
                    });
                }

                const stats = techStackStats.get(techStack)!;
                stats.apps.add(appDir);
                stats.fileCount++;
                stats.totalSize += detection.size;

                // 应用级技术栈统计
                appTechStacks.set(techStack, (appTechStacks.get(techStack) ?? 0) + 1);
            }

            appTechStackStats.set(appDir, appTechStacks);
        }

        // 更新应用数量
        for (const [, stats] of techStackStats) {
            stats.appCount = stats.apps.size;
        }

        // 1. 技术栈总体统计表
        sheetData.push([
            { value: '技术栈总体统计', fontWeight: 'bold' as const, fontSize: 14 }
        ]);
        sheetData.push([{ value: '' }]); // 空行

        // 表头
        sheetData.push([
            { value: '技术栈', fontWeight: 'bold' as const },
            { value: '应用数量', fontWeight: 'bold' as const },
            { value: '文件数量', fontWeight: 'bold' as const },
            { value: '总文件大小', fontWeight: 'bold' as const },
            { value: '平均文件大小', fontWeight: 'bold' as const },
            { value: '占比', fontWeight: 'bold' as const }
        ]);

        // 按文件数量排序
        const sortedStats = Array.from(techStackStats.entries())
            .sort((a, b) => b[1].fileCount - a[1].fileCount);

        const totalFiles = Array.from(techStackStats.values())
            .reduce((sum, stats) => sum + stats.fileCount, 0);

        for (const [techStack, stats] of sortedStats) {
            const percentage = ((stats.fileCount / totalFiles) * 100).toFixed(1);
            sheetData.push([
                { value: techStack, type: String },
                { value: stats.appCount, type: Number },
                { value: stats.fileCount, type: Number },
                { value: this.formatFileSize(stats.totalSize), type: String },
                { value: this.formatFileSize(stats.totalSize / stats.fileCount), type: String },
                { value: `${percentage}%`, type: String }
            ]);
        }

        // 2. 应用技术栈分布表
        sheetData.push([{ value: '' }]); // 空行
        sheetData.push([{ value: '' }]); // 空行
        sheetData.push([
            { value: '应用技术栈分布', fontWeight: 'bold' as const, fontSize: 14 }
        ]);
        sheetData.push([{ value: '' }]); // 空行

        // 构建应用技术栈分布表头
        const techStacks = Array.from(techStackStats.keys()).sort();
        const appDistHeaderRow = [
            { value: '应用名称', fontWeight: 'bold' as const },
            { value: '包名', fontWeight: 'bold' as const }
        ];
        for (const techStack of techStacks) {
            appDistHeaderRow.push({ value: techStack, fontWeight: 'bold' as const });
        }
        appDistHeaderRow.push({ value: '技术栈总数', fontWeight: 'bold' as const });
        sheetData.push(appDistHeaderRow);

        // 填充应用技术栈分布数据
        for (const { appDir, result } of allResults) {
            const appTechStacks: Map<string, number> = appTechStackStats.get(appDir) ?? new Map<string, number>();
            const row: Array<{ value: string | number; type?: typeof String | typeof Number }> = [
                { value: result.appName, type: String },
                { value: result.bundleName, type: String }
            ];

            for (const techStack of techStacks) {
                const count: number = appTechStacks.get(techStack) ?? 0;
                row.push({ value: count, type: Number });
            }

            row.push({ value: appTechStacks.size, type: Number });
            sheetData.push(row);
        }

        // 3. 技术栈排名
        sheetData.push([{ value: '' }]); // 空行
        sheetData.push([{ value: '' }]); // 空行
        sheetData.push([
            { value: '技术栈使用排名（Top 10）', fontWeight: 'bold' as const, fontSize: 14 }
        ]);
        sheetData.push([{ value: '' }]); // 空行

        sheetData.push([
            { value: '排名', fontWeight: 'bold' as const },
            { value: '技术栈', fontWeight: 'bold' as const },
            { value: '文件数量', fontWeight: 'bold' as const },
            { value: '应用数量', fontWeight: 'bold' as const },
            { value: '占比', fontWeight: 'bold' as const }
        ]);

        const top10 = sortedStats.slice(0, 10);
        for (let i = 0; i < top10.length; i++) {
            const [techStack, stats] = top10[i];
            const percentage = ((stats.fileCount / totalFiles) * 100).toFixed(1);
            sheetData.push([
                { value: i + 1, type: Number },
                { value: techStack, type: String },
                { value: stats.fileCount, type: Number },
                { value: stats.appCount, type: Number },
                { value: `${percentage}%`, type: String }
            ]);
        }

        return sheetData;
    }

    /**
     * 创建Dart开源库汇总工作表数据
     */
    private createDartPackagesSheetData(
        allResults: Array<{ appDir: string; result: Hap }>
    ): SheetData {
        const sheetData: SheetData = [];

        // 收集所有Flutter技术栈的文件，提取openSourcePackages元数据
        const dartPackagesMap = new Map<string, {
            version: string;
            filePaths: Array<string>;
            apps: Set<string>;
        }>();

        logger.info(`开始收集Dart开源包，共${allResults.length}个应用`);

        for (const { appDir, result } of allResults) {
            logger.info(`  处理应用: ${appDir}, 技术栈检测数: ${result.techStackDetections.length}`);

            let flutterFileCount = 0;
            let dartPackageCount = 0;
            let hasStackTrace = false;

            for (const detection of result.techStackDetections) {
                // 只处理Flutter技术栈
                if (detection.techStack !== 'Flutter') {
                    continue;
                }

                flutterFileCount++;

                // 检查是否有openSourcePackages元数据
                const openSourcePackages = detection.metadata.openSourcePackages;
                if (!openSourcePackages) {
                    logger.warn(`    ⚠️ Flutter文件 ${detection.file} 没有openSourcePackages元数据`);
                    continue;
                }

                // 支持字符串和数组两种格式
                // 当只有1个包时，metadata extractor会返回字符串而不是数组
                const packagesArray = Array.isArray(openSourcePackages)
                    ? openSourcePackages
                    : [openSourcePackages];

                dartPackageCount += packagesArray.length;
                logger.info(`    Flutter文件 ${detection.file} 包含 ${packagesArray.length} 个Dart包`);

                // 检查是否包含stack_trace包
                const hasStackTraceInFile = packagesArray.some((pkg: unknown) => {
                    const pkgStr = String(pkg);
                    return pkgStr.startsWith('stack_trace');
                });
                if (hasStackTraceInFile) {
                    hasStackTrace = true;
                    logger.info(`    ✅ 发现stack_trace包在 ${detection.file}`);
                }


                // 构建完整文件路径
                const fullPath = detection.folder
                    ? `${appDir}/${detection.folder}/${detection.file}`
                    : `${appDir}/${detection.file}`;

                // 解析每个包（格式：packageName 或 packageName@version）
                for (const pkg of packagesArray) {
                    const pkgStr = String(pkg);
                    const atIndex = pkgStr.indexOf('@');

                    let packageName: string;
                    let version: string;

                    if (atIndex > 0) {
                        packageName = pkgStr.substring(0, atIndex);
                        version = pkgStr.substring(atIndex + 1);
                    } else {
                        packageName = pkgStr;
                        version = '-';
                    }

                    // 记录包信息
                    if (!dartPackagesMap.has(packageName)) {
                        dartPackagesMap.set(packageName, {
                            version: version,
                            filePaths: [fullPath],
                            apps: new Set([appDir])
                        });
                        if (packageName === 'stack_trace') {
                            logger.info(`    📦 新包: ${packageName}@${version} 来自 ${appDir}, 路径: ${fullPath}`);
                        } else {
                            logger.debug(`    新包: ${packageName}@${version} 来自 ${appDir}`);
                        }
                    } else {
                        const existing = dartPackagesMap.get(packageName)!;
                        const beforeApps = existing.apps.size;
                        const beforePaths = existing.filePaths.length;

                        // 如果当前版本更具体（不是'-'），则更新版本
                        if (version !== '-' && existing.version === '-') {
                            existing.version = version;
                        }
                        // 添加文件路径到列表（去重）
                        if (!existing.filePaths.includes(fullPath)) {
                            existing.filePaths.push(fullPath);
                        }
                        // 添加应用
                        existing.apps.add(appDir);

                        if (packageName === 'stack_trace') {
                            logger.info(`    📦 已存在包: ${packageName}@${version} 来自 ${appDir}, 应用数: ${beforeApps} -> ${existing.apps.size}, 路径数: ${beforePaths} -> ${existing.filePaths.length}, 路径: ${fullPath}`);
                        } else {
                            logger.debug(`    已存在包: ${packageName}@${version} 来自 ${appDir}, 应用数: ${beforeApps} -> ${existing.apps.size}, 路径数: ${beforePaths} -> ${existing.filePaths.length}`);
                        }
                    }
                }
            }

            if (flutterFileCount > 0) {
                logger.info(`  应用 ${appDir}: 发现${flutterFileCount}个Flutter文件，包含${dartPackageCount}个Dart包引用${hasStackTrace ? ' (包含stack_trace)' : ''}`);
            } else {
                logger.info(`  应用 ${appDir}: 没有发现Flutter文件`);
            }
        }

        logger.info(`Dart包汇总完成，共收集到${dartPackagesMap.size}个不同的包`);

        // 输出详细的汇总信息
        if (dartPackagesMap.size > 0) {
            logger.info('Dart包汇总详情:');
            for (const [packageName, info] of dartPackagesMap.entries()) {
                logger.info(`  - ${packageName}@${info.version}: ${info.apps.size}个应用, ${info.filePaths.length}个文件`);
                logger.debug(`    应用列表: ${Array.from(info.apps).join(', ')}`);
                logger.debug(`    文件列表: ${info.filePaths.join(', ')}`);
            }
        }

        // 如果没有Dart包，返回空sheet（只有标题）
        if (dartPackagesMap.size === 0) {
            sheetData.push([
                { value: '包名', fontWeight: 'bold' as const },
                { value: '版本', fontWeight: 'bold' as const },
                { value: '来源文件路径', fontWeight: 'bold' as const },
                { value: '文件数量', fontWeight: 'bold' as const },
                { value: '应用数量', fontWeight: 'bold' as const }
            ]);
            return sheetData;
        }

        // 添加标题行
        sheetData.push([
            { value: '包名', fontWeight: 'bold' as const },
            { value: '版本', fontWeight: 'bold' as const },
            { value: '来源文件路径', fontWeight: 'bold' as const },
            { value: '文件数量', fontWeight: 'bold' as const },
            { value: '应用数量', fontWeight: 'bold' as const }
        ]);

        // 按包名排序
        const sortedPackages = Array.from(dartPackagesMap.entries()).sort((a, b) =>
            a[0].localeCompare(b[0])
        );

        // 添加数据行
        for (const [packageName, info] of sortedPackages) {
            sheetData.push([
                { value: packageName, type: String },
                { value: info.version, type: String },
                { value: info.filePaths.join(os.EOL), type: String },
                { value: info.filePaths.length, type: Number },
                { value: info.apps.size, type: Number }
            ]);
        }

        return sheetData;
    }

    /**
     * 检查目录名是否符合应用包格式 (xxxxx@xxxx)
     */
    private isAppPackageDirectory(dirName: string): boolean {
        // 匹配格式: xxxxx@xxxx，例如 com.ctrip.harmonynext@8.85.4
        const pattern = /^.+@.+$/;
        return pattern.test(dirName);
    }

    /**
     * 解析应用包目录名，提取包名和版本号
     */
    private parseAppPackageDirectory(dirName: string): { packageName: string; version: string } | null {
        const atIndex = dirName.lastIndexOf('@');
        if (atIndex === -1) {
            return null;
        }
        return {
            packageName: dirName.substring(0, atIndex),
            version: dirName.substring(atIndex + 1)
        };
    }

    /**
     * 从HAP文件列表中找到entry类型的主应用包
     * 优先选择文件名为 entry.hap 的包，排除系统组件包（如ArkWebCore.hap），
     * 如果没有则选择第一个非系统组件的entry类型包
     */
    private async findEntryHap(hapFiles: Array<string>): Promise<Hap | null> {
        // 系统组件HAP包列表（这些不应该被当作主应用包）
        const systemHapNames = ['arkwebcore.hap'];

        // 第一步：优先查找文件名为 entry.hap 的包
        const entryHapFile = hapFiles.find(file => path.basename(file).toLowerCase() === 'entry.hap');
        if (entryHapFile) {
            try {
                const zip = await JSZip.loadAsync(fs.readFileSync(entryHapFile));
                const moduleJsonFile = zip.file('module.json');

                if (moduleJsonFile) {
                    const moduleJsonContent = await moduleJsonFile.async('string');
                    const moduleJson = JSON.parse(moduleJsonContent) as {
                        module?: { type?: string };
                        app?: { bundleName: string; versionCode: number; versionName: string; label: string };
                    };

                    // 验证是否是entry类型
                    if (moduleJson.module?.type === 'entry') {
                        const hap = await Hap.loadFromHap(entryHapFile);
                        logger.info('  优先使用 entry.hap 作为主应用包');
                        return hap;
                    }
                }
            } catch (error) {
                logger.warn(`解析 entry.hap 失败：${entryHapFile}`, error);
            }
        }

        // 第二步：如果没有 entry.hap，查找第一个非系统组件的entry类型HAP包
        for (const hapFile of hapFiles) {
            const fileName = path.basename(hapFile).toLowerCase();

            // 跳过系统组件HAP包
            if (systemHapNames.includes(fileName)) {
                logger.debug(`  跳过系统组件包：${path.basename(hapFile)}`);
                continue;
            }

            try {
                const zip = await JSZip.loadAsync(fs.readFileSync(hapFile));
                const moduleJsonFile = zip.file('module.json');

                if (moduleJsonFile) {
                    const moduleJsonContent = await moduleJsonFile.async('string');
                    const moduleJson = JSON.parse(moduleJsonContent) as {
                        module?: { type?: string };
                        app?: { bundleName: string; versionCode: number; versionName: string; label: string };
                    };

                    // 检查是否是entry类型的模块
                    if (moduleJson.module?.type === 'entry') {
                        // 找到entry类型，解析完整的Hap对象
                        const hap = await Hap.loadFromHap(hapFile);
                        logger.info(`  使用 ${path.basename(hapFile)} 作为主应用包`);
                        return hap;
                    }
                }
            } catch (error) {
                logger.warn(`解析HAP文件失败：${hapFile}`, error);
            }
        }

        return null;
    }

    /**
     * 收集分析目标
     */
    private async collectAnalysisTargets(inputPath: string): Promise<Array<{ label: string; data?: Buffer; outputBase: string; relativePath: string }>> {
        const targets: Array<{ label: string; data?: Buffer; outputBase: string; relativePath: string }> = [];
        const stat = fs.statSync(inputPath);
        if (stat.isDirectory()) {
            // 递归收集.hap和.hsp文件
            const files = getAllFiles(inputPath, { exts: ['.hap', '.hsp'] });
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
            if (ext === '.hap' || ext === '.hsp' || ext === '.zip') {
                const fileName = path.basename(inputPath, ext);
                targets.push({
                    label: inputPath,
                    outputBase: fileName,
                    relativePath: path.basename(inputPath)
                });
            } else {
                logger.warn(`Unsupported file type: ${inputPath}. Only .hap, .hsp or .zip are supported as files.`);
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

            // 判断文件是否为二进制文件
            const isBinary = isBinaryFile(fileDetection.file);

            results.push({
                folder: fileDetection.folder,
                file: fileDetection.file,
                size: fileDetection.size,
                techStack,
                fileType,
                confidence,
                isBinary,
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
