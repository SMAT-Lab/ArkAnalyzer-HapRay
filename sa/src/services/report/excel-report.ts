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
import type { HapStaticAnalysisResult, ResourceFileInfo } from '../../config/types';

/**
 * Excel格式化器
 */
export class ExcelFormatter extends BaseFormatter {
    /**
     * 格式化分析结果为Excel
     */
    async format(result: HapStaticAnalysisResult): Promise<FormatResult> {
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
    private async buildExcelWorkbook(workbook: Excel.Workbook, result: HapStaticAnalysisResult): Promise<void> {
        // 创建分析摘要工作表
        const summarySheet = workbook.addWorksheet('分析摘要');
        this.buildSummarySheet(summarySheet, result);

        // 第一部分：文件类型信息
        const fileTypeSheet = workbook.addWorksheet('文件类型信息');
        this.buildFileTypeInfoSheet(fileTypeSheet, result);

        // 第二部分：技术栈信息
        const techStackSheet = workbook.addWorksheet('技术栈信息');
        this.buildTechnologyStackInfoSheet(techStackSheet, result);

        // 创建文件类型统计工作表
        const statsSheet = workbook.addWorksheet('文件类型统计');
        this.buildStatsSheet(statsSheet, result);

        // 如果有压缩包，创建压缩包工作表
        if (result.resourceAnalysis.archiveFiles.length > 0) {
            const archiveSheet = workbook.addWorksheet('压缩包分析');
            this.buildArchiveSheet(archiveSheet, result);
        }
    }

    /**
     * 构建分析摘要工作表
     */
    private buildSummarySheet(worksheet: Excel.Worksheet, result: HapStaticAnalysisResult): void {
        // 设置列
        worksheet.columns = [
            { header: '项目', key: 'item', width: 25 },
            { header: '值', key: 'value', width: 35 },
            { header: '说明', key: 'description', width: 50 }
        ];

        // 添加数据
        const summaryData = [
            { item: 'HAP文件路径', value: result.hapPath, description: '被分析的HAP文件完整路径' },
            { item: '分析时间', value: this.formatDateTime(result.timestamp), description: '静态分析执行的时间' },
            { item: '分析器版本', value: '1.1.0', description: 'HAP静态分析器版本号' },
            { item: '', value: '', description: '' },
            { item: 'SO文件总数', value: result.soAnalysis.totalSoFiles.toString(), description: '检测到的共享库文件数量' },
            { item: '资源文件总数', value: result.resourceAnalysis.totalFiles.toString(), description: '包含嵌套文件的总文件数量' },
            { item: 'JavaScript文件数', value: result.resourceAnalysis.jsFiles.length.toString(), description: 'JS源码文件数量' },
            { item: 'Hermes文件数', value: result.resourceAnalysis.hermesFiles.length.toString(), description: 'Hermes字节码文件数量' },
            { item: '压缩文件数', value: result.resourceAnalysis.archiveFiles.length.toString(), description: '压缩包文件数量' },
            { item: '总文件大小', value: this.formatFileSize(result.resourceAnalysis.totalSize), description: '所有文件的总大小' },
            { item: '检测到的框架', value: result.soAnalysis.detectedFrameworks.join(', ') || '无', description: '通过SO文件识别的技术框架' },
            { item: '解压的压缩包数', value: result.resourceAnalysis.extractedArchiveCount.toString() || '0', description: '成功解压分析的压缩包数量' },
            { item: '最大解压深度', value: result.resourceAnalysis.maxExtractionDepth.toString() || '0', description: '嵌套压缩包的最大层级深度' }
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
     * 构建文件类型信息工作表
     */
    private buildFileTypeInfoSheet(worksheet: Excel.Worksheet, result: HapStaticAnalysisResult): void {
        // 设置列
        worksheet.columns = [
            { header: '文件名', key: 'fileName', width: 30 },
            { header: '路径', key: 'filePath', width: 60 },
            { header: '分类（后缀名）', key: 'fileType', width: 20 },
            { header: '文件大小', key: 'fileSize', width: 15 }
        ];

        // 添加数据
        for (const [fileType, files] of result.resourceAnalysis.filesByType) {
            for (const file of files) {
                worksheet.addRow({
                    fileName: file.fileName,
                    filePath: file.filePath,
                    fileType: fileType,
                    fileSize: this.formatFileSize(file.fileSize)
                });
            }
        }

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
    private buildTechnologyStackInfoSheet(worksheet: Excel.Worksheet, result: HapStaticAnalysisResult): void {
        // 设置列
        worksheet.columns = [
            { header: '文件名', key: 'fileName', width: 30 },
            { header: '路径', key: 'filePath', width: 60 },
            { header: '技术栈', key: 'technologyStack', width: 25 },
            { header: '文件大小', key: 'fileSize', width: 15 },
            { header: '40位版本', key: 'hex40', width: 45 },
            { header: 'Dart版本', key: 'dartVersion', width: 15 },
            { header: '最后修改时间', key: 'lastModified', width: 20 },
            { header: 'Dart包', key: 'dartPackages', width: 50 },
            { header: 'KMP特征', key: 'kmpSignatures', width: 40 },
            { header: '其他元数据', key: 'metadata', width: 40 }
        ];

        // 添加数据
        result.soAnalysis.soFiles.forEach(soFile => {
            // 过滤掉 Unknown 框架
            if (soFile.techStack === 'Unknown') {
                return; // 跳过没有识别框架的文件
            }

            // 从 metadata 中提取信息
            const hex40 = soFile.metadata.flutterHex40 || '';
            const dartVersion = soFile.metadata.dartVersion || '';

            // 最后修改时间
            let lastModified = '';
            const lastModifiedStr = soFile.metadata.lastModified;
            if (lastModifiedStr) {
                const date = new Date(lastModifiedStr);
                if (!isNaN(date.getTime())) {
                    lastModified = `${date.toLocaleDateString('zh-CN')} ${date.toLocaleTimeString('zh-CN')}`;
                }
            }

            // Dart 包
            let dartPackages = '';
            if (soFile.metadata.dartPackages && Array.isArray(soFile.metadata.dartPackages)) {
                const packageNames = soFile.metadata.dartPackages
                    .slice(0, 10) // Excel 中可以显示更多
                    .join(', ');
                const more = soFile.metadata.dartPackages.length > 10
                    ? ` 等${soFile.metadata.dartPackages.length}个`
                    : '';
                dartPackages = `${packageNames}${more}`;
            }

            // KMP 相关信息
            let kmpSignatures = '';
            if (soFile.metadata.kotlinSignatures && Array.isArray(soFile.metadata.kotlinSignatures)) {
                kmpSignatures = soFile.metadata.kotlinSignatures.join(', ');
            }

            // 其他元数据
            let metadataStr = '';
            if (soFile.metadata && Object.keys(soFile.metadata).length > 0) {
                const excludeKeys = ['flutterHex40', 'dartVersion', 'lastModified', 'dartPackages', 'kotlinSignatures'];
                const metadataEntries = Object.entries(soFile.metadata)
                    .filter(([key]) => !excludeKeys.includes(key))
                    .map(([key, value]) => `${key}: ${value}`)
                    .join('; ');
                metadataStr = metadataEntries;
            }

            worksheet.addRow({
                fileName: soFile.file,
                filePath: `${soFile.folder}/${soFile.file}`,
                technologyStack: soFile.techStack,
                fileSize: this.formatFileSize(soFile.size),
                hex40: hex40,
                dartVersion: dartVersion,
                lastModified: lastModified,
                dartPackages: dartPackages,
                kmpSignatures: kmpSignatures,
                metadata: metadataStr
            });
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
            to: 'J1'
        };
    }

    /**
     * 构建文件类型统计工作表
     */
    private buildStatsSheet(worksheet: Excel.Worksheet, result: HapStaticAnalysisResult): void {
        // 设置列
        worksheet.columns = [
            { header: '文件类型', key: 'fileType', width: 20 },
            { header: '文件数量', key: 'count', width: 15 },
            { header: '总大小', key: 'totalSize', width: 20 },
            { header: '平均大小', key: 'avgSize', width: 20 },
            { header: '占比', key: 'percentage', width: 15 }
        ];

        // 添加数据
        const totalFiles = result.resourceAnalysis.totalFiles;
        for (const [fileType, files] of result.resourceAnalysis.filesByType) {
            const count = files.length;
            const totalSize = files.reduce((sum: number, file: ResourceFileInfo) => sum + file.fileSize, 0);
            const avgSize = count > 0 ? totalSize / count : 0;
            const percentage = totalFiles > 0 ? ((count / totalFiles) * 100).toFixed(1) + '%' : '0%';

            worksheet.addRow({
                fileType: fileType,
                count: count,
                totalSize: this.formatFileSize(totalSize),
                avgSize: this.formatFileSize(avgSize),
                percentage: percentage
            });
        }

        // 设置标题行样式
        worksheet.getRow(1).font = { bold: true, size: 12 };
        worksheet.getRow(1).fill = {
            type: 'pattern',
            pattern: 'solid',
            fgColor: { argb: 'FFE6F3FF' }
        };
    }



    /**
     * 构建压缩包工作表
     */
    private buildArchiveSheet(worksheet: Excel.Worksheet, result: HapStaticAnalysisResult): void {
        // 设置列
        worksheet.columns = [
            { header: '压缩包名', key: 'fileName', width: 30 },
            { header: '路径', key: 'filePath', width: 60 },
            { header: '大小', key: 'fileSize', width: 15 },
            { header: '解压状态', key: 'extracted', width: 15 },
            { header: '包含文件数', key: 'entryCount', width: 15 },
            { header: '嵌套深度', key: 'depth', width: 15 }
        ];

        // 添加数据
        result.resourceAnalysis.archiveFiles.forEach(archiveFile => {
            worksheet.addRow({
                fileName: archiveFile.fileName,
                filePath: archiveFile.filePath,
                fileSize: this.formatFileSize(archiveFile.fileSize),
                extracted: archiveFile.extracted ? '✅ 已解压' : '❌ 未解压',
                entryCount: archiveFile.entryCount || 0,
                depth: archiveFile.extractionDepth || 0
            });

            // 处理嵌套的压缩包
            if (archiveFile.nestedArchives) {
                archiveFile.nestedArchives.forEach(nestedArchive => {
                    worksheet.addRow({
                        fileName: '  └─ ' + nestedArchive.fileName,
                        filePath: nestedArchive.filePath,
                        fileSize: this.formatFileSize(nestedArchive.fileSize),
                        extracted: nestedArchive.extracted ? '✅ 已解压' : '❌ 未解压',
                        entryCount: nestedArchive.entryCount || 0,
                        depth: nestedArchive.extractionDepth || 0
                    });
                });
            }
        });

        // 设置标题行样式
        worksheet.getRow(1).font = { bold: true, size: 12 };
        worksheet.getRow(1).fill = {
            type: 'pattern',
            pattern: 'solid',
            fgColor: { argb: 'FFE6F3FF' }
        };
    }
}
