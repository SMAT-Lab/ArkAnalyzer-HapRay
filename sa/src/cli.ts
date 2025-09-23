#!/usr/bin/env node
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
import { HapStaticAnalyzer } from './hap-static-analyzer';
import { Logger } from './utils/logger';
import { FormatterFactory, OutputFormat, FormatOptions } from './formatters';

interface AnalyzeOptions {
    input: string;
    output: string;
    format: string;
}

const logger = Logger.getInstance();
const VERSION = '1.0.0';

// CLI命令定义
const program = new Command()
    .name('hapray-static')
    .version(VERSION)
    .description('HAP Static Analyzer - Analyze HAP packages for frameworks and resources')
    .requiredOption('-i, --input <path>', 'HAP file path to analyze')
    .option('-o, --output <path>', 'Output directory', './output')
    .option('-f, --format <format>', 'Output format: json, html, excel, all', 'all')
    .action(async (options: AnalyzeOptions) => {
        await analyzeHap(options);
    });

async function analyzeHap(options: AnalyzeOptions): Promise<void> {
    const { input, output, format } = options;

    // 默认配置
    const verbose = true; // 默认启用详细日志
    const details = true; // 默认包含详细信息

    // 验证输入文件
    if (!fs.existsSync(input)) {
        logger.error(`HAP file not found: ${input}`);
        process.exit(1);
    }

    // 验证输出格式
    const supportedFormats = [...FormatterFactory.getSupportedFormats(), 'all'];
    if (!supportedFormats.includes(format)) {
        logger.error(`Unsupported output format: ${format}`);
        logger.error(`Supported formats: ${supportedFormats.join(', ')}`);
        process.exit(1);
    }

    // 创建输出目录
    if (!fs.existsSync(output)) {
        fs.mkdirSync(output, { recursive: true });
    }

    logger.info(`Analyzing HAP package: ${input}`);
    logger.info(`Output directory: ${output}`);
    logger.info(`Output format: ${format}`);

    try {
        const analyzer = new HapStaticAnalyzer(verbose);

        // 执行分析
        const startTime = Date.now();
        const result = await analyzer.analyzeHap(input);
        const duration = Date.now() - startTime;

        logger.info(`Analysis completed in ${duration}ms`);

        // 显示分析结果摘要
        logger.info('Analysis Summary:');
        logger.info(`  Detected frameworks: ${result.soAnalysis.detectedFrameworks.join(', ') || 'None'}`);
        logger.info(`  SO files: ${result.soAnalysis.totalSoFiles}`);
        logger.info(`  Resource files: ${result.resourceAnalysis.totalFiles}`);
        logger.info(`  JS files: ${result.resourceAnalysis.jsFiles.length}`);
        logger.info(`  Hermes files: ${result.resourceAnalysis.hermesFiles.length}`);
        logger.info(`  Archive files: ${result.resourceAnalysis.archiveFiles.length}`);

        // 生成输出文件
        const baseName = path.basename(input, path.extname(input));
        const timestamp = new Date().toISOString().replace(/[:.]/g, '-');

        if (format === 'all') {
            // 生成所有格式
            const formats: OutputFormat[] = [OutputFormat.JSON, OutputFormat.HTML, OutputFormat.EXCEL];
            logger.info('Generating all output formats...');

            for (const currentFormat of formats) {
                await generateReport(result, currentFormat, baseName, timestamp, output, details);
            }
        } else {
            // 生成单一格式
            await generateReport(result, format as OutputFormat, baseName, timestamp, output, details);
        }

    } catch (error) {
        logger.error('Analysis failed:', error);
        process.exit(1);
    }
}

/**
 * 生成指定格式的报告
 */
async function generateReport(
    result: import('./types').HapStaticAnalysisResult,
    format: OutputFormat,
    baseName: string,
    timestamp: string,
    output: string,
    details: boolean
): Promise<void> {
    const logger = Logger.getInstance();

    // 根据格式确定文件扩展名
    const formatter = FormatterFactory.create({
        format: format,
        outputPath: '', // 临时值，稍后设置
        includeDetails: details,
        pretty: true
    });

    const fileExtension = formatter.getFileExtension();
    const outputFile = path.join(output, `${baseName}_${timestamp}${fileExtension}`);

    // 更新格式化器的输出路径
    const formatOptions: FormatOptions = {
        format: format,
        outputPath: outputFile,
        includeDetails: details,
        pretty: true
    };

    const finalFormatter = FormatterFactory.create(formatOptions);

    // 格式化并保存结果
    const formatResult = await finalFormatter.format(result);

    if (formatResult.success) {
        logger.info(`${format.toUpperCase()} report generated: ${formatResult.filePath}`);
        logger.info(`File size: ${formatFileSize(formatResult.fileSize)}`);
        logger.info(`Format duration: ${formatResult.duration}ms`);
    } else {
        logger.error(`Failed to generate ${format.toUpperCase()} report: ${formatResult.error}`);
        throw new Error(`Failed to generate ${format.toUpperCase()} report`);
    }
}

/**
 * 格式化文件大小
 */
function formatFileSize(bytes: number): string {
    if (bytes === 0) return '0 B';

    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));

    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

// 启动CLI
try {
    program.parse();
} catch (error) {
    logger.error('CLI Error:', error);
    process.exit(1);
}
