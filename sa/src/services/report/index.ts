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

import type { HapStaticAnalysisResult } from '../../config/types';

/**
 * 支持的输出格式
 */
export enum OutputFormat {
    JSON = 'json',
    HTML = 'html',
    EXCEL = 'excel'
}

/**
 * 格式化选项
 */
export interface FormatOptions {
    /** 输出格式 */
    format: OutputFormat;
    /** 输出文件路径 */
    outputPath: string;
    /** 是否美化输出 */
    pretty?: boolean;
    /** 是否包含详细信息 */
    includeDetails?: boolean;
    /** 自定义模板路径（仅HTML格式） */
    templatePath?: string;
}

/**
 * 格式化结果
 */
export interface FormatResult {
    /** 输出文件路径 */
    filePath: string;
    /** 文件大小（字节） */
    fileSize: number;
    /** 格式化耗时（毫秒） */
    duration: number;
    /** 是否成功 */
    success: boolean;
    /** 错误信息（如果失败） */
    error?: string;
}

/**
 * 抽象格式化器基类
 */
export abstract class BaseFormatter {
    protected options: FormatOptions;

    constructor(options: FormatOptions) {
        this.options = options;
    }

    /**
     * 格式化分析结果
     * @param result 分析结果
     * @returns 格式化结果
     */
    abstract format(result: HapStaticAnalysisResult): Promise<FormatResult>;

    /**
     * 获取输出文件扩展名
     */
    abstract getFileExtension(): string;

    /**
     * 验证格式化选项
     */
    protected validateOptions(): void {
        if (!this.options.outputPath) {
            throw new Error('Output path is required');
        }
    }

    /**
     * 格式化文件大小
     */
    protected formatFileSize(bytes: number): string {
        if (bytes === 0) {return '0 B';}
        
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    /**
     * 格式化日期时间
     */
    protected formatDateTime(date: Date): string {
        return date.toLocaleString('zh-CN', {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
        });
    }

    /**
     * 计算百分比
     */
    protected calculatePercentage(value: number, total: number): string {
        if (total === 0) {return '0%';}
        return ((value / total) * 100).toFixed(1) + '%';
    }

    /**
     * 获取文件类型统计
     */
    protected getFileTypeStats(result: HapStaticAnalysisResult): Array<{type: string, count: number, percentage: string, barWidth: number}> {
        const stats: Array<{type: string, count: number, percentage: string, barWidth: number}> = [];
        const total = result.resourceAnalysis.totalFiles;

        for (const [fileType, files] of result.resourceAnalysis.filesByType) {
            stats.push({
                type: fileType,
                count: files.length,
                percentage: this.calculatePercentage(files.length, total),
                barWidth: 0 // 临时值，稍后计算
            });
        }

        // 按数量排序
        const sortedStats = stats.sort((a, b) => b.count - a.count);

        // 计算条状图宽度（基于最大值的相对百分比）
        if (sortedStats.length > 0) {
            const maxCount = sortedStats[0].count;
            sortedStats.forEach(stat => {
                stat.barWidth = maxCount > 0 ? Math.max(10, (stat.count / maxCount) * 100) : 10;
            });
        }

        return sortedStats;
    }

    /**
     * 获取框架统计
     */
    protected getFrameworkStats(result: HapStaticAnalysisResult): Array<{framework: string, count: number, percentage: string}> {
        const frameworkCount = new Map<string, number>();
        
        result.soAnalysis.soFiles.forEach(soFile => {
            soFile.frameworks.forEach(framework => {
                frameworkCount.set(framework, (frameworkCount.get(framework) ?? 0) + 1);
            });
        });

        const stats: Array<{framework: string, count: number, percentage: string}> = [];
        const total = result.soAnalysis.totalSoFiles;

        for (const [framework, count] of frameworkCount) {
            stats.push({
                framework,
                count,
                percentage: this.calculatePercentage(count, total)
            });
        }

        return stats.sort((a, b) => b.count - a.count);
    }
}

/**
 * 格式化器工厂
 */
export class FormatterFactory {
    /**
     * 创建格式化器
     * @param options 格式化选项
     * @returns 格式化器实例
     */
    static create(options: FormatOptions): BaseFormatter {
        switch (options.format) {
            case OutputFormat.JSON:
                return new JsonFormatter(options);
            case OutputFormat.HTML:
                return new HtmlFormatter(options);
            case OutputFormat.EXCEL:
                return new ExcelFormatter(options);
            default:
                throw new Error(`Unsupported output format: ${options.format}`);
        }
    }

    /**
     * 获取支持的格式列表
     */
    static getSupportedFormats(): Array<OutputFormat> {
        return Object.values(OutputFormat);
    }

    /**
     * 验证格式是否支持
     */
    static isFormatSupported(format: string): boolean {
        return Object.values(OutputFormat).includes(format as OutputFormat);
    }
}

// 导入具体的格式化器实现
import { JsonFormatter } from './json-report';
import { HtmlFormatter } from './html-report';
import { ExcelFormatter } from './excel-report';

export { JsonFormatter, HtmlFormatter, ExcelFormatter };
