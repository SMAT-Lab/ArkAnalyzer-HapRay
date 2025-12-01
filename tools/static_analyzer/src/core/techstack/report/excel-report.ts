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
import writeXlsxFile from 'write-excel-file/node';
import type { SheetData } from 'write-excel-file';
import type { FormatResult } from './index';
import { BaseFormatter } from './index';
import type { Hap } from '../../hap/hap_parser';

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

            // 构建所有工作表数据
            const sheets = this.buildAllSheets(result);

            // 写入Excel文件
            await writeXlsxFile(sheets.data, {
                sheets: sheets.names,
                filePath: this.options.outputPath
            });

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
     * 构建所有工作表
     */
    private buildAllSheets(result: Hap): { data: Array<SheetData>; names: Array<string> } {
        const summaryData = this.buildSummarySheetData(result);
        const techStackData = this.buildTechnologyStackInfoSheetData(result);
        const distributionData = this.buildTechStackDistributionSheetData(result);
        const insightsData = this.buildAnalysisInsightsSheetData(result);
        const dartPackagesData = this.buildDartPackagesSheetData(result);

        // 如果有Dart包数据，则添加Dart开源库sheet
        const hasDartPackages = dartPackagesData.length > 1; // 大于1表示有数据行（第一行是标题）

        if (hasDartPackages) {
            return {
                data: [summaryData, techStackData, distributionData, insightsData, dartPackagesData],
                names: ['分析摘要', '技术栈信息', '技术栈分布', '分析洞察', 'Dart开源库']
            };
        } else {
            return {
                data: [summaryData, techStackData, distributionData, insightsData],
                names: ['分析摘要', '技术栈信息', '技术栈分布', '分析洞察']
            };
        }
    }

    /**
     * 构建分析摘要工作表数据
     */
    private buildSummarySheetData(result: Hap): SheetData {
        // 过滤掉 Unknown 技术栈
        const filteredDetections = result.techStackDetections.filter(d => d.techStack !== 'Unknown');
        const detectedTechStacks = [...new Set(filteredDetections.map(d => d.techStack))];
        const totalFileSize = filteredDetections.reduce((sum, item) => sum + item.size, 0);

        const sheetData: SheetData = [];

        // 添加标题行
        sheetData.push([
            { value: '项目', fontWeight: 'bold' as const },
            { value: '值', fontWeight: 'bold' as const },
            { value: '说明', fontWeight: 'bold' as const }
        ]);

        // 添加数据行
        const summaryRows = [
            ['HAP文件路径', result.hapPath, '被分析的HAP文件完整路径'],
            ['包名', result.bundleName, 'HAP包的bundle名称'],
            ['应用名', result.appName, '应用显示名称'],
            ['版本名称', result.versionName, '应用版本名称'],
            ['版本代码', result.versionCode.toString(), '应用版本代码'],
            ['分析时间', this.formatDateTime(new Date()), '静态分析执行的时间'],
            ['分析器版本', '2.0.0', 'HAP静态分析器版本号'],
            ['', '', ''],
            ['技术栈文件总数', filteredDetections.length.toString(), '检测到的技术栈文件数量（不含Unknown）'],
            ['检测到的技术栈', detectedTechStacks.join(', ') || '无', '通过文件识别的技术栈'],
            ['总文件大小', this.formatFileSize(totalFileSize), '所有技术栈文件的总大小']
        ];

        summaryRows.forEach(row => {
            sheetData.push([
                { value: row[0], type: String },
                { value: row[1], type: String },
                { value: row[2], type: String }
            ]);
        });

        return sheetData;
    }

    /**
     * 构建技术栈信息工作表数据
     */
    private buildTechnologyStackInfoSheetData(result: Hap): SheetData {
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

        const sheetData: SheetData = [];

        // 添加标题行
        const headerRow = [
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
            { value: '来源版本名称', fontWeight: 'bold' as const },
            ...sortedMetadataColumns.map(column => ({
                value: column,
                fontWeight: 'bold' as const
            }))
        ];
        sheetData.push(headerRow);

        // 添加数据行
        filteredDetections.forEach(detection => {
            // 置信度格式化
            const confidenceStr = detection.confidence !== undefined
                ? `${(detection.confidence * 100).toFixed(0)}%`
                : '-';

            // 二进制/文本标识
            const binaryTypeStr = detection.isBinary === true ? 'Binary' :
                detection.isBinary === false ? 'Text' : '-';

            const row = [
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
            for (const column of sortedMetadataColumns) {
                const value = detection.metadata[column];
                let cellValue = '';
                if (value !== undefined && value !== null) {
                    if (Array.isArray(value)) {
                        // soExports 和 soImports 使用换行符分隔，其他数组使用逗号分隔
                        if (column === 'soExports' || column === 'soImports') {
                            cellValue = value.join(os.EOL);
                        } else {
                            cellValue = value.join(', ');
                        }
                    } else {
                        cellValue = String(value);
                    }
                }
                row.push({ value: cellValue, type: String });
            }

            sheetData.push(row);
        });

        return sheetData;
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
     * 构建技术栈分布工作表数据
     */
    private buildTechStackDistributionSheetData(result: Hap): SheetData {
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

        const sheetData: SheetData = [];

        // 添加标题行
        sheetData.push([
            { value: '技术栈名称', fontWeight: 'bold' as const },
            { value: '文件数量', fontWeight: 'bold' as const },
            { value: '占比(%)', fontWeight: 'bold' as const },
            { value: '总大小', fontWeight: 'bold' as const },
            { value: '平均大小', fontWeight: 'bold' as const }
        ]);

        // 添加数据行
        distributionData.forEach(item => {
            sheetData.push([
                { value: item.techStack, type: String },
                { value: item.count, type: Number },
                { value: item.percentage, type: Number },
                { value: item.totalSize, type: String },
                { value: item.avgSize, type: String }
            ]);
        });

        return sheetData;
    }

    /**
     * 构建分析洞察工作表数据
     */
    private buildAnalysisInsightsSheetData(result: Hap): SheetData {
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

        const sheetData: SheetData = [];

        // 添加标题行
        sheetData.push([
            { value: '洞察项目', fontWeight: 'bold' as const },
            { value: '值', fontWeight: 'bold' as const },
            { value: '说明', fontWeight: 'bold' as const }
        ]);

        // 添加数据行
        const insightsRows = [
            ['主要技术栈', primaryTechStack, '文件数量最多的技术栈'],
            ['技术栈多样性', techStackDiversity.toFixed(2), '技术栈分布的熵值，越高表示技术栈越多样化'],
            ['技术栈文件总数', filteredDetections.length.toString(), '检测到的技术栈文件数量（不含Unknown）'],
            ['总文件大小', this.formatFileSize(totalSize), '所有技术栈文件的总大小'],
            ['平均文件大小', avgFileSize, '技术栈文件的平均大小'],
            ['', '', ''],
            ['高置信度文件', highConfidence.toString(), '置信度 > 0.8 的文件数量'],
            ['中等置信度文件', mediumConfidence.toString(), '置信度 0.5-0.8 的文件数量'],
            ['低置信度文件', lowConfidence.toString(), '置信度 < 0.5 的文件数量'],
            ['', '', ''],
            ['小文件(<1MB)', fileSizeDistribution.small.toString(), '小于1MB的文件数量'],
            ['中等文件(1-10MB)', fileSizeDistribution.medium.toString(), '1-10MB的文件数量'],
            ['大文件(>10MB)', fileSizeDistribution.large.toString(), '大于10MB的文件数量']
        ];

        insightsRows.forEach(row => {
            sheetData.push([
                { value: row[0], type: String },
                { value: row[1], type: String },
                { value: row[2], type: String }
            ]);
        });

        return sheetData;
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

    /**
     * 构建Dart开源库汇总工作表数据
     */
    private buildDartPackagesSheetData(result: Hap): SheetData {
        const sheetData: SheetData = [];

        // 收集所有Flutter技术栈的文件，提取openSourcePackages元数据
        const dartPackagesMap = new Map<string, { version: string; filePaths: Array<string> }>();

        for (const detection of result.techStackDetections) {
            // 只处理Flutter技术栈
            if (detection.techStack !== 'Flutter') {
                continue;
            }

            // 检查是否有openSourcePackages元数据
            const openSourcePackages = detection.metadata.openSourcePackages;
            if (!openSourcePackages || !Array.isArray(openSourcePackages)) {
                continue;
            }

            // 构建完整文件路径
            const fullPath = detection.folder ? `${detection.folder}/${detection.file}` : detection.file;

            // 解析每个包（格式：packageName 或 packageName@version）
            for (const pkg of openSourcePackages) {
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
                        filePaths: [fullPath]
                    });
                } else {
                    const existing = dartPackagesMap.get(packageName)!;
                    // 如果当前版本更具体（不是'-'），则更新版本
                    if (version !== '-' && existing.version === '-') {
                        existing.version = version;
                    }
                    // 添加文件路径到列表（去重）
                    if (!existing.filePaths.includes(fullPath)) {
                        existing.filePaths.push(fullPath);
                    }
                }
            }
        }

        // 如果没有Dart包，返回空sheet（只有标题）
        if (dartPackagesMap.size === 0) {
            sheetData.push([
                { value: '包名', fontWeight: 'bold' as const },
                { value: '版本', fontWeight: 'bold' as const },
                { value: '来源文件路径', fontWeight: 'bold' as const },
                { value: '文件数量', fontWeight: 'bold' as const }
            ]);
            return sheetData;
        }

        // 添加标题行
        sheetData.push([
            { value: '包名', fontWeight: 'bold' as const },
            { value: '版本', fontWeight: 'bold' as const },
            { value: '来源文件路径', fontWeight: 'bold' as const },
            { value: '文件数量', fontWeight: 'bold' as const }
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
                { value: info.filePaths.length, type: Number }
            ]);
        }

        return sheetData;
    }
}
