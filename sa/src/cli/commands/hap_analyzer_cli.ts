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
import { Command } from 'commander';
import { HapAnalysisService } from '../../services/analysis/hap_analysis';
import type { FormatOptions } from '../../formatters';
import { FormatterFactory, OutputFormat } from '../../formatters';
import { LOG_MODULE_TYPE, Logger } from 'arkanalyzer';
import { ensureDirectoryExists, getAllFiles } from '../../utils/file_utils';

const logger = Logger.getLogger(LOG_MODULE_TYPE.TOOL);

interface AnalyzeOptions {
    input: string;
    output: string;
    format: string;
}

const VERSION = '1.0.0';

export const HapAnalyzerCli = new Command('analyzer')
    .version(VERSION)
    .description('HAP 静态分析器 - 分析 HAP/ZIP 文件或目录中的框架与资源')
    .requiredOption('-i, --input <path>', '分析输入路径（HAP/ZIP 文件或目录）')
    .option('-o, --output <path>', '输出目录', './output')
    .option('-f, --format <format>', '输出格式：json, html, excel, all', 'all')
    .action(async (options: AnalyzeOptions) => {
        await analyzeHap(options);
    });

async function analyzeHap(options: AnalyzeOptions): Promise<void> {
    const { input, output, format } = options;

    const verbose = true;
    const details = true;

    if (!fs.existsSync(input)) {
        logger.error(`Input not found: ${input}`);
        process.exit(1);
    }

    const supportedFormats = [...FormatterFactory.getSupportedFormats(), 'all'];
    if (!supportedFormats.includes(format)) {
        logger.error(`Unsupported output format: ${format}`);
        logger.error(`Supported formats: ${supportedFormats.join(', ')}`);
        process.exit(1);
    }

    ensureDirectoryExists(output);

    logger.info(`分析目标：${input}`);
    logger.info(`输出目录：${output}`);
    logger.info(`输出格式：${format}`);

    try {
        const analyzer = new HapAnalysisService({ verbose });
        const targets = await collectAnalysisTargets(input);
        if (targets.length === 0) {
            logger.warn('未发现可分析的目标（.hap 文件或包含 .hap 的目录）。');
            return;
        }

        const timestamp = new Date().toISOString().replace(/[:.]/g, '-');

        for (const t of targets) {
            const startTime = Date.now();
            const result = await analyzer.analyzeHap(t.label);
            const duration = Date.now() - startTime;

            logger.info(`分析完成：${t.label} 用时 ${duration}ms`);
            logger.info('分析概要:');
            logger.info(`  框架类型：${result.soAnalysis.detectedFrameworks.join(', ') || '无'}`);
            logger.info(`  SO 文件：${result.soAnalysis.totalSoFiles}`);
            logger.info(`  资源文件：${result.resourceAnalysis.totalFiles}`);
            logger.info(`  JS 文件：${result.resourceAnalysis.jsFiles.length}`);
            logger.info(`  Hermes 文件：${result.resourceAnalysis.hermesFiles.length}`);
            logger.info(`  压缩文件：${result.resourceAnalysis.archiveFiles.length}`);

            const baseName = sanitizeBaseName(path.basename(t.outputBase, path.extname(t.outputBase)));
            const perTargetOutput = path.join(output, baseName);
            ensureDirectoryExists(perTargetOutput);

            if (format === 'all') {
                const formats: Array<OutputFormat> = [OutputFormat.JSON, OutputFormat.HTML, OutputFormat.EXCEL];
                logger.info(`为 ${baseName} 生成所有输出格式...`);
                for (const currentFormat of formats) {
                    await generateReport(result, currentFormat, baseName, timestamp, perTargetOutput, details);
                }
            } else {
                await generateReport(result, format as OutputFormat, baseName, timestamp, perTargetOutput, details);
            }
        }

    } catch (error) {
        logger.error('分析失败：', error);
        process.exit(1);
    }
}

async function generateReport(
    result: import('../../config/types').HapStaticAnalysisResult,
    format: OutputFormat,
    baseName: string,
    timestamp: string,
    output: string,
    details: boolean
): Promise<void> {
    const formatter = FormatterFactory.create({
        format: format,
        outputPath: '',
        includeDetails: details,
        pretty: true
    });

    const fileExtension = formatter.getFileExtension();
    const outputFile = path.join(output, `${baseName}_${timestamp}${fileExtension}`);

    const formatOptions: FormatOptions = {
        format: format,
        outputPath: outputFile,
        includeDetails: details,
        pretty: true
    };

    const finalFormatter = FormatterFactory.create(formatOptions);
    const formatResult = await finalFormatter.format(result);

    if (formatResult.success) {
        logger.info(`${format.toUpperCase()} 报告已生成：${formatResult.filePath}`);
        logger.info(`文件大小：${formatFileSize(formatResult.fileSize)}`);
        logger.info(`格式化耗时：${formatResult.duration}ms`);
    } else {
        logger.error(`生成 ${format.toUpperCase()} 报告失败：${formatResult.error}`);
        throw new Error(`生成 ${format.toUpperCase()} 报告失败`);
    }
}

function formatFileSize(bytes: number): string {
    if (bytes === 0) {return '0 B';}
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

function sanitizeBaseName(name: string): string {
    return name.replace(/[^a-zA-Z0-9_\-\.]+/g, '_');
}

async function collectAnalysisTargets(inputPath: string): Promise<Array<{ label: string; data?: Buffer; outputBase: string }>> {
    const targets: Array<{ label: string; data?: Buffer; outputBase: string }> = [];
    const stat = fs.statSync(inputPath);
    if (stat.isDirectory()) {
        // 递归收集.hap文件
        const files = getAllFiles(inputPath, { exts: ['.hap'] });
        for (const f of files) {
            targets.push({ label: f, outputBase: f });
        }
    } else if (stat.isFile()) {
        const ext = path.extname(inputPath).toLowerCase();
        if (ext === '.hap' || ext === '.zip') {
            targets.push({ label: inputPath, outputBase: inputPath });
        } else {
            logger.warn(`Unsupported file type: ${inputPath}. Only .hap or .zip are supported as files.`);
        }
    }
    return targets;
}
