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
import type { HapStaticAnalysisResult } from '../types';

interface JsonReport {
    metadata: {
        hapPath: string;
        timestamp: string;
        analysisDate: string;
        version: string;
        format: string;
    };
    summary: {
        totalSoFiles: number;
        totalResourceFiles: number;
        totalSize: number;
        totalSizeFormatted: string;
        detectedFrameworks: Array<string>;
        jsFilesCount: number;
        hermesFilesCount: number;
        archiveFilesCount: number;
    };
    statistics: {
        fileTypes: Array<{
            type: string;
            count: number;
            percentage: string;
        }>;
        frameworks: Array<{
            framework: string;
            count: number;
            percentage: string;
        }>;
    };
    details?: {
        soFiles: Array<unknown>;
        jsFiles: Array<unknown>;
        hermesFiles: Array<unknown>;
        archiveFiles: Array<unknown>;
    };
    soAnalysis?: {
        detectedFrameworks?: Array<string>;
        totalSoFiles?: number;
        soFiles?: Array<unknown>;
    };
    resourceAnalysis?: {
        totalFiles?: number;
        totalSize?: number;
        totalSizeFormatted?: string;
        filesByType?: Record<string, Array<unknown>>;
        jsFiles?: Array<unknown>;
        hermesFiles?: Array<unknown>;
        archiveFiles?: Array<unknown>;
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
        const report: JsonReport = {
            metadata: {
                hapPath: result.hapPath,
                timestamp: result.timestamp.toISOString(),
                analysisDate: this.formatDateTime(result.timestamp),
                version: '1.1.0',
                format: 'json'
            },
            summary: {
                totalSoFiles: result.soAnalysis.totalSoFiles,
                totalResourceFiles: result.resourceAnalysis.totalFiles,
                totalSize: result.resourceAnalysis.totalSize,
                totalSizeFormatted: this.formatFileSize(result.resourceAnalysis.totalSize),
                detectedFrameworks: result.soAnalysis.detectedFrameworks,
                jsFilesCount: result.resourceAnalysis.jsFiles.length,
                hermesFilesCount: result.resourceAnalysis.hermesFiles.length,
                archiveFilesCount: result.resourceAnalysis.archiveFiles.length
            },
            statistics: {
                fileTypes: this.getFileTypeStats(result),
                frameworks: this.getFrameworkStats(result)
            },
            soAnalysis: {
                detectedFrameworks: result.soAnalysis.detectedFrameworks,
                totalSoFiles: result.soAnalysis.totalSoFiles,
                soFiles: result.soAnalysis.soFiles.map(soFile => ({
                    ...soFile,
                    fileSizeFormatted: this.formatFileSize(soFile.fileSize)
                }))
            },
            resourceAnalysis: {
                totalFiles: result.resourceAnalysis.totalFiles,
                totalSize: result.resourceAnalysis.totalSize,
                totalSizeFormatted: this.formatFileSize(result.resourceAnalysis.totalSize),
                filesByType: Object.fromEntries(
                    Array.from(result.resourceAnalysis.filesByType.entries()).map(([type, files]) => [
                        type,
                        files.map(file => ({
                            ...file,
                            fileSizeFormatted: this.formatFileSize(file.fileSize)
                        }))
                    ])
                ),
                jsFiles: result.resourceAnalysis.jsFiles.map(jsFile => ({
                    ...jsFile,
                    fileSizeFormatted: this.formatFileSize(jsFile.fileSize)
                })),
                hermesFiles: result.resourceAnalysis.hermesFiles.map(hermesFile => ({
                    ...hermesFile,
                    fileSizeFormatted: this.formatFileSize(hermesFile.fileSize)
                })),
                archiveFiles: result.resourceAnalysis.archiveFiles.map(archiveFile => ({
                    ...archiveFile,
                    fileSizeFormatted: this.formatFileSize(archiveFile.fileSize)
                }))
            }
        };

        // 如果不包含详细信息，移除详细的文件列表
        if (!this.options.includeDetails) {
            if (report.soAnalysis) {
                delete report.soAnalysis.soFiles;
            }
            if (report.resourceAnalysis) {
                delete report.resourceAnalysis.filesByType;
                delete report.resourceAnalysis.jsFiles;
                delete report.resourceAnalysis.hermesFiles;
                delete report.resourceAnalysis.archiveFiles;
            }
        }

        return report;
    }
}
