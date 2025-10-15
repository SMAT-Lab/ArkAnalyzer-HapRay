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
import type { FormatResult } from './index';
import { BaseFormatter } from './index';
import type { HapStaticAnalysisResult, ResourceFileInfo, FileType } from '../../config/types';

/**
 * 文件类型信息项
 */
interface FileTypeInfoItem {
    fileName: string;
    filePath: string;
    fileType: string;
    fileSize: number;
    fileSizeFormatted: string;
}

/**
 * 技术栈信息项（直接使用 SoAnalysisResult 格式）
 */
interface TechnologyStackInfoItem {
    folder: string;
    file: string;
    size: number;
    techStack: string;
    metadata: {
        version?: string;
        lastModified?: string;
        dartVersion?: string;
        flutterHex40?: string;
        dartPackages?: Array<string>;
        kotlinSignatures?: Array<string>;
        [key: string]: unknown;
    };
}

/**
 * JSON报告结构
 */
interface JsonReport {
    metadata: {
        hapPath: string;
        timestamp: string;
        analysisDate: string;
        version: string;
        format: string;
    };
    summary: {
        totalFiles: number;
        totalSize: number;
        totalSizeFormatted: string;
        detectedFrameworks: Array<string>;
        fileTypeCount: number;
        technologyStackCount: number;
    };

    // 第一部分：文件类型信息
    fileTypeInfo: {
        totalCount: number;
        items: Array<FileTypeInfoItem>;
        statistics: Array<{
            type: string;
            count: number;
            totalSize: number;
            totalSizeFormatted: string;
            percentage: string;
        }>;
    };

    // 第二部分：技术栈信息
    technologyStackInfo: {
        totalCount: number;
        items: Array<TechnologyStackInfoItem>;
        statistics: Array<{
            framework: string;
            count: number;
            percentage: string;
        }>;
    };
}

/**
 * JSON格式化器
 */
export class JsonFormatter extends BaseFormatter {
    /**
     * 格式化分析结果为JSON
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

            // 构建JSON报告数据
            const jsonReport = this.buildJsonReport(result);
            
            // 写入文件
            const jsonContent = this.options.pretty 
                ? JSON.stringify(jsonReport, null, 2)
                : JSON.stringify(jsonReport);
                
            fs.writeFileSync(this.options.outputPath, jsonContent, 'utf8');
            
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
        return '.json';
    }

    /**
     * 构建JSON报告数据
     */
    private buildJsonReport(result: HapStaticAnalysisResult): JsonReport {
        // 构建文件类型信息
        const fileTypeInfo = this.buildFileTypeInfo(result);

        // 构建技术栈信息
        const technologyStackInfo = this.buildTechnologyStackInfo(result);

        const report: JsonReport = {
            metadata: {
                hapPath: result.hapPath,
                timestamp: result.timestamp.toISOString(),
                analysisDate: this.formatDateTime(result.timestamp),
                version: '2.0.0',
                format: 'json'
            },
            summary: {
                totalFiles: result.resourceAnalysis.totalFiles,
                totalSize: result.resourceAnalysis.totalSize,
                totalSizeFormatted: this.formatFileSize(result.resourceAnalysis.totalSize),
                detectedFrameworks: result.soAnalysis.detectedFrameworks,
                fileTypeCount: fileTypeInfo.totalCount,
                technologyStackCount: technologyStackInfo.totalCount
            },
            fileTypeInfo,
            technologyStackInfo
        };

        return report;
    }

    /**
     * 构建文件类型信息
     */
    private buildFileTypeInfo(result: HapStaticAnalysisResult): JsonReport['fileTypeInfo'] {
        const items: Array<FileTypeInfoItem> = [];

        // 收集所有文件的类型信息
        for (const [fileType, files] of result.resourceAnalysis.filesByType) {
            for (const file of files) {
                items.push({
                    fileName: file.fileName,
                    filePath: file.filePath,
                    fileType: String(fileType),
                    fileSize: file.fileSize,
                    fileSizeFormatted: this.formatFileSize(file.fileSize)
                });
            }
        }

        // 计算统计信息
        const statistics = this.getFileTypeStats(result).map(stat => {
            const files = result.resourceAnalysis.filesByType.get(stat.type as unknown as FileType) ?? [];
            const totalSize = files.reduce((sum: number, file: ResourceFileInfo) => sum + file.fileSize, 0);
            return {
                type: stat.type,
                count: stat.count,
                totalSize,
                totalSizeFormatted: this.formatFileSize(totalSize),
                percentage: stat.percentage
            };
        });

        return {
            totalCount: items.length,
            items: this.options.includeDetails !== false ? items : [],
            statistics
        };
    }

    /**
     * 构建技术栈信息
     */
    private buildTechnologyStackInfo(result: HapStaticAnalysisResult): JsonReport['technologyStackInfo'] {
        const items: Array<TechnologyStackInfoItem> = [];

        // 收集所有SO文件的技术栈信息
        for (const soFile of result.soAnalysis.soFiles) {
            // 过滤掉 Unknown 技术栈
            if (soFile.techStack === 'Unknown') {
                continue;
            }

            // 直接使用 SoAnalysisResult 格式
            const item: TechnologyStackInfoItem = {
                folder: soFile.folder,
                file: soFile.file,
                size: soFile.size,
                techStack: soFile.techStack,
                metadata: soFile.metadata
            };

            items.push(item);
        }

        // 计算统计信息
        const statistics = this.getFrameworkStats(result);

        return {
            totalCount: items.length,
            items: this.options.includeDetails !== false ? items : [],
            statistics
        };
    }
}
