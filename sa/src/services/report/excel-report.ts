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
import Excel from 'exceljs';
import type { FormatResult } from './index';
import { BaseFormatter } from './index';
import type { Hap } from '../../core/hap/hap_parser';

/**
 * Excel格式化器
 */
export class ExcelFormatter extends BaseFormatter {
    /**
     * 格式化分析结果为Excel
     */
    async format(result: Hap): Promise<FormatResult> {
        const startTime = Date.now();

        try {
            this.validateOptions();

            // 确保输出目录存在
            const outputDir = path.dirname(this.options.outputPath);
            if (!fs.existsSync(outputDir)) {
                fs.mkdirSync(outputDir, { recursive: true });
            }

            // 创建工作簿和工作表
            const workbook = new Excel.Workbook();
            await this.buildExcelWorkbook(workbook, result);

            // 写入Excel文件
            await workbook.xlsx.writeFile(this.options.outputPath);

            const fileSize = fs.statSync(this.options.outputPath).size;
            const duration = Date.now() - startTime;

            return {
                filePath: this.options.outputPath,
                fileSize,
                duration,
                success: true
            };

        } catch (error) {
            return {
                filePath: this.options.outputPath,
                fileSize: 0,
                duration: Date.now() - startTime,
                success: false,
                error: error instanceof Error ? error.message : String(error)
            };
        }
    }

    /**
     * 获取文件扩展名
     */
    getFileExtension(): string {
        return '.xlsx';
    }

    /**
     * 构建Excel工作簿
     */
    private async buildExcelWorkbook(workbook: Excel.Workbook, result: Hap): Promise<void> {
        // 创建分析摘要工作表
        const summarySheet = workbook.addWorksheet('分析摘要');
        this.buildSummarySheet(summarySheet, result);

        // 技术栈信息
        const techStackSheet = workbook.addWorksheet('技术栈信息');
        this.buildTechnologyStackInfoSheet(techStackSheet, result);

        // 技术栈分布分析
        const techStackDistributionSheet = workbook.addWorksheet('技术栈分布');
        this.buildTechStackDistributionSheet(techStackDistributionSheet, result);

        // 分析洞察
        const insightsSheet = workbook.addWorksheet('分析洞察');
        this.buildAnalysisInsightsSheet(insightsSheet, result);
    }

    /**
     * 构建分析摘要工作表
     */
    private buildSummarySheet(worksheet: Excel.Worksheet, result: Hap): void {
        // 设置列
        worksheet.columns = [
            { header: '项目', key: 'item', width: 25 },
            { header: '值', key: 'value', width: 35 },
            { header: '说明', key: 'description', width: 50 }
        ];

        // 过滤掉 Unknown 技术栈
        const filteredDetections = result.techStackDetections.filter(d => d.techStack !== 'Unknown');
        const detectedTechStacks = [...new Set(filteredDetections.map(d => d.techStack))];
        const totalFileSize = filteredDetections.reduce((sum, item) => sum + item.size, 0);

        // 添加数据
        const summaryData = [
            { item: 'HAP文件路径', value: result.hapPath, description: '被分析的HAP文件完整路径' },
            { item: '包名', value: result.bundleName, description: 'HAP包的bundle名称' },
            { item: '应用名', value: result.appName, description: '应用显示名称' },
            { item: '版本名称', value: result.versionName, description: '应用版本名称' },
            { item: '版本代码', value: result.versionCode.toString(), description: '应用版本代码' },
            { item: '分析时间', value: this.formatDateTime(new Date()), description: '静态分析执行的时间' },
            { item: '分析器版本', value: '2.0.0', description: 'HAP静态分析器版本号' },
            { item: '', value: '', description: '' },
            { item: '技术栈文件总数', value: filteredDetections.length.toString(), description: '检测到的技术栈文件数量（不含Unknown）' },
            { item: '检测到的技术栈', value: detectedTechStacks.join(', ') || '无', description: '通过文件识别的技术栈' },
            { item: '总文件大小', value: this.formatFileSize(totalFileSize), description: '所有技术栈文件的总大小' }
        ];

        summaryData.forEach(row => {
            worksheet.addRow(row);
        });

        // 设置标题行样式
        worksheet.getRow(1).font = { bold: true, size: 12 };
        worksheet.getRow(1).fill = {
            type: 'pattern',
            pattern: 'solid',
            fgColor: { argb: 'FFE6F3FF' }
        };
    }

    /**
     * 构建技术栈信息工作表
     */
    private buildTechnologyStackInfoSheet(worksheet: Excel.Worksheet, result: Hap): void {
        // 过滤掉 Unknown 技术栈
        const filteredDetections = result.techStackDetections.filter(d => d.techStack !== 'Unknown');

        // 收集所有可能的 metadata 字段
        const metadataColumns = new Set<string>();
        for (const detection of filteredDetections) {
            Object.keys(detection.metadata).forEach(key => {
                metadataColumns.add(key);
            });
        }

        const sortedMetadataColumns = Array.from(metadataColumns).sort();

        // 设置列
        const columns = [
            { header: '文件夹', key: 'folder', width: 40 },
            { header: '文件名', key: 'fileName', width: 30 },
            { header: '技术栈', key: 'technologyStack', width: 20 },
            { header: '文件类型', key: 'fileType', width: 20 },
            { header: '文件大小', key: 'fileSize', width: 15 },
            { header: '置信度', key: 'confidence', width: 12 },
            ...sortedMetadataColumns.map(column => ({
                header: column,
                key: column,
                width: 20
            }))
        ];

        worksheet.columns = columns;

        // 添加数据
        filteredDetections.forEach(detection => {
            // 置信度格式化
            const confidenceStr = detection.confidence !== undefined
                ? `${(detection.confidence * 100).toFixed(0)}%`
                : '-';

            const rowData: Record<string, unknown> = {
                folder: detection.folder,
                fileName: detection.file,
                technologyStack: detection.techStack,
                fileType: detection.fileType ?? '-',
                fileSize: this.formatFileSize(detection.size),
                confidence: confidenceStr
            };

            // 添加 metadata 字段
            for (const column of sortedMetadataColumns) {
                const value = detection.metadata[column];
                if (value !== undefined && value !== null) {
                    if (Array.isArray(value)) {
                        rowData[column] = value.join(', ');
                    } else {
                        rowData[column] = String(value);
                    }
                } else {
                    rowData[column] = '';
                }
            }

            worksheet.addRow(rowData);
        });

        // 设置标题行样式
        worksheet.getRow(1).font = { bold: true, size: 12 };
        worksheet.getRow(1).fill = {
            type: 'pattern',
            pattern: 'solid',
            fgColor: { argb: 'FFE6F3FF' }
        };

        // 设置自动筛选
        worksheet.autoFilter = {
            from: 'A1',
            to: 'L1'
        };
    }

    /**
     * 格式化文件大小
     */
    protected formatFileSize(bytes: number): string {
        if (bytes === 0) { return '0 B'; }
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    /**
     * 构建技术栈分布工作表
     */
    private buildTechStackDistributionSheet(worksheet: Excel.Worksheet, result: Hap): void {
        // 设置列
        worksheet.columns = [
            { header: '技术栈名称', key: 'techStack', width: 20 },
            { header: '文件数量', key: 'count', width: 15 },
            { header: '占比(%)', key: 'percentage', width: 15 },
            { header: '总大小', key: 'totalSize', width: 20 },
            { header: '平均大小', key: 'avgSize', width: 20 }
        ];

        // 过滤掉 Unknown 技术栈
        const filteredDetections = result.techStackDetections.filter(d => d.techStack !== 'Unknown');

        // 统计技术栈分布
        const techStackStats: Record<string, { count: number; totalSize: number }> = {};
        for (const item of filteredDetections) {
            const techStack = item.techStack;
            if (!(techStack in techStackStats)) {
                techStackStats[techStack] = { count: 0, totalSize: 0 };
            }
            techStackStats[techStack].count++;
            techStackStats[techStack].totalSize += item.size;
        }

        const totalFiles = filteredDetections.length;
        const distributionData = Object.entries(techStackStats).map(([techStack, stats]) => ({
            techStack,
            count: stats.count,
            percentage: totalFiles > 0 ? Math.round((stats.count / totalFiles) * 100) : 0,
            totalSize: this.formatFileSize(stats.totalSize),
            avgSize: this.formatFileSize(stats.count > 0 ? stats.totalSize / stats.count : 0)
        }));

        // 按文件数量排序
        distributionData.sort((a, b) => b.count - a.count);

        // 添加数据
        worksheet.addRows(distributionData);

        // 设置样式
        worksheet.getRow(1).font = { bold: true };
        worksheet.getRow(1).fill = {
            type: 'pattern',
            pattern: 'solid',
            fgColor: { argb: 'FFE6E6FA' }
        };
    }

    /**
     * 构建分析洞察工作表
     */
    private buildAnalysisInsightsSheet(worksheet: Excel.Worksheet, result: Hap): void {
        // 设置列
        worksheet.columns = [
            { header: '洞察项目', key: 'insight', width: 25 },
            { header: '值', key: 'value', width: 35 },
            { header: '说明', key: 'description', width: 50 }
        ];

        // 过滤掉 Unknown 技术栈
        const filteredDetections = result.techStackDetections.filter(d => d.techStack !== 'Unknown');

        // 计算洞察数据
        const techStackCounts: Record<string, number> = {};
        let highConfidence = 0;
        let mediumConfidence = 0;
        let lowConfidence = 0;
        let totalSize = 0;

        for (const item of filteredDetections) {
            const techStack = item.techStack;
            techStackCounts[techStack] = (techStackCounts[techStack] || 0) + 1;
            totalSize += item.size;

            const confidence = item.confidence ?? 0;
            if (confidence > 0.8) {
                highConfidence++;
            } else if (confidence >= 0.5) {
                mediumConfidence++;
            } else {
                lowConfidence++;
            }
        }

        // 找到主要技术栈
        const primaryTechStack = Object.entries(techStackCounts)
            .sort(([, a], [, b]) => b - a)[0]?.[0] || 'Unknown';

        // 计算技术栈多样性（熵）
        const techStackDiversity = this.calculateDiversity(techStackCounts);

        // 文件大小分布
        const fileSizeDistribution = this.calculateFileSizeDistribution(filteredDetections);

        const avgFileSize = filteredDetections.length > 0
            ? this.formatFileSize(totalSize / filteredDetections.length)
            : '0 B';

        const insightsData = [
            { insight: '主要技术栈', value: primaryTechStack, description: '文件数量最多的技术栈' },
            { insight: '技术栈多样性', value: techStackDiversity.toFixed(2), description: '技术栈分布的熵值，越高表示技术栈越多样化' },
            { insight: '技术栈文件总数', value: filteredDetections.length.toString(), description: '检测到的技术栈文件数量（不含Unknown）' },
            { insight: '总文件大小', value: this.formatFileSize(totalSize), description: '所有技术栈文件的总大小' },
            { insight: '平均文件大小', value: avgFileSize, description: '技术栈文件的平均大小' },
            { insight: '', value: '', description: '' },
            { insight: '高置信度文件', value: highConfidence.toString(), description: '置信度 > 0.8 的文件数量' },
            { insight: '中等置信度文件', value: mediumConfidence.toString(), description: '置信度 0.5-0.8 的文件数量' },
            { insight: '低置信度文件', value: lowConfidence.toString(), description: '置信度 < 0.5 的文件数量' },
            { insight: '', value: '', description: '' },
            { insight: '小文件(<1MB)', value: fileSizeDistribution.small.toString(), description: '小于1MB的文件数量' },
            { insight: '中等文件(1-10MB)', value: fileSizeDistribution.medium.toString(), description: '1-10MB的文件数量' },
            { insight: '大文件(>10MB)', value: fileSizeDistribution.large.toString(), description: '大于10MB的文件数量' }
        ];

        // 添加数据
        worksheet.addRows(insightsData);

        // 设置样式
        worksheet.getRow(1).font = { bold: true };
        worksheet.getRow(1).fill = {
            type: 'pattern',
            pattern: 'solid',
            fgColor: { argb: 'FFE6E6FA' }
        };
    }

    /**
     * 计算技术栈多样性（熵）
     */
    private calculateDiversity(techStackCounts: Record<string, number>): number {
        const total = Object.values(techStackCounts).reduce((sum, count) => sum + count, 0);
        let entropy = 0;

        for (const count of Object.values(techStackCounts)) {
            const probability = count / total;
            if (probability > 0) {
                entropy -= probability * Math.log2(probability);
            }
        }

        return entropy;
    }

    /**
     * 计算文件大小分布
     */
    private calculateFileSizeDistribution(items: Array<{ size: number }>): { small: number; medium: number; large: number } {
        const distribution = { small: 0, medium: 0, large: 0 };
        const MB = 1024 * 1024;

        for (const item of items) {
            if (item.size < MB) {
                distribution.small++;
            } else if (item.size < 10 * MB) {
                distribution.medium++;
            } else {
                distribution.large++;
            }
        }

        return distribution;
    }
}
