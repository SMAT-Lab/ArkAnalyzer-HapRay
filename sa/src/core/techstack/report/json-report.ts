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
import type { Hap, TechStackDetection } from '../../hap/hap_parser';

/**
 * JSON报告结构
 */
interface JsonReport {
    metadata: {
        hapPath: string;
        bundleName: string;
        appName: string;
        versionName: string;
        versionCode: number;
        timestamp: string;
        analysisDate: string;
        version: string;
        format: string;
    };
    summary: {
        totalFiles: number;
        detectedTechStacks: Array<string>;
        totalFileSize: number;
        techStackDistribution: Record<string, number>;
    };
    techStackDetections: Array<TechStackDetection>;
    analysisInsights: {
        primaryTechStack: string;
        techStackDiversity: number;
        fileSizeDistribution: {
            small: number; // < 1MB
            medium: number; // 1MB - 10MB
            large: number; // > 10MB
        };
        confidenceDistribution: {
            high: number; // > 0.8
            medium: number; // 0.5 - 0.8
            low: number; // < 0.5
        };
        techStackDetails: Record<string, {
            count: number;
            files: Array<string>;
            totalSize: number;
            avgSize: number;
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
    async format(result: Hap): Promise<FormatResult> {
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
    private buildJsonReport(result: Hap): JsonReport {
        // 计算总文件大小
        const totalFileSize = result.techStackDetections.reduce((sum, item) => sum + item.size, 0);

        // 构建技术栈分布
        const techStackDistribution = this.buildTechStackDistribution(result);

        // 构建分析洞察
        const analysisInsights = this.buildAnalysisInsights(result);

        // 过滤掉 Unknown 技术栈
        const filteredDetections = result.techStackDetections.filter(d => d.techStack !== 'Unknown');
        const detectedTechStacks = [...new Set(filteredDetections.map(d => d.techStack))];

        const report: JsonReport = {
            metadata: {
                hapPath: result.hapPath,
                bundleName: result.bundleName,
                appName: result.appName,
                versionName: result.versionName,
                versionCode: result.versionCode,
                timestamp: new Date().toISOString(),
                analysisDate: this.formatDateTime(new Date()),
                version: '2.0.0',
                format: 'json'
            },
            summary: {
                totalFiles: filteredDetections.length,
                detectedTechStacks,
                totalFileSize,
                techStackDistribution
            },
            techStackDetections: this.options.includeDetails !== false ? filteredDetections : [],
            analysisInsights
        };

        return report;
    }

    /**
     * 构建技术栈分布
     */
    private buildTechStackDistribution(result: Hap): Record<string, number> {
        const distribution: Record<string, number> = {};
        const filteredDetections = result.techStackDetections.filter(d => d.techStack !== 'Unknown');
        const totalFiles = filteredDetections.length;

        if (totalFiles === 0) {
            return distribution;
        }

        for (const item of filteredDetections) {
            const techStack = item.techStack;
            distribution[techStack] = (distribution[techStack] || 0) + 1;
        }

        // 转换为百分比
        for (const techStack in distribution) {
            distribution[techStack] = Math.round((distribution[techStack] / totalFiles) * 100);
        }

        return distribution;
    }

    /**
     * 构建分析洞察
     */
    private buildAnalysisInsights(result: Hap): JsonReport['analysisInsights'] {
        const techStackCounts: Record<string, number> = {};
        const techStackDetails: Record<string, { count: number; files: Array<string>; totalSize: number; avgSize: number }> = {};
        let highConfidence = 0;
        let mediumConfidence = 0;
        let lowConfidence = 0;

        // 过滤掉 Unknown 技术栈
        const filteredDetections = result.techStackDetections.filter(d => d.techStack !== 'Unknown');

        // 统计信息
        for (const item of filteredDetections) {
            const techStack = item.techStack;
            techStackCounts[techStack] = (techStackCounts[techStack] || 0) + 1;

            // 构建技术栈详情
            if (!(techStack in techStackDetails)) {
                techStackDetails[techStack] = {
                    count: 0,
                    files: [],
                    totalSize: 0,
                    avgSize: 0
                };
            }

            techStackDetails[techStack].count++;
            techStackDetails[techStack].files.push(item.file);
            techStackDetails[techStack].totalSize += item.size;

            const confidence = item.confidence ?? 0;
            if (confidence > 0.8) {
                highConfidence++;
            } else if (confidence >= 0.5) {
                mediumConfidence++;
            } else {
                lowConfidence++;
            }
        }

        // 计算平均大小
        for (const techStack in techStackDetails) {
            const details = techStackDetails[techStack];
            details.avgSize = details.count > 0 ? Math.round(details.totalSize / details.count) : 0;
        }

        // 找到主要技术栈
        const primaryTechStack = Object.entries(techStackCounts)
            .sort(([, a], [, b]) => b - a)[0]?.[0] || 'Unknown';

        // 计算技术栈多样性（熵）
        const techStackDiversity = this.calculateDiversity(techStackCounts);

        // 文件大小分布
        const fileSizeDistribution = this.calculateFileSizeDistribution(filteredDetections);

        return {
            primaryTechStack,
            techStackDiversity,
            fileSizeDistribution,
            confidenceDistribution: {
                high: highConfidence,
                medium: mediumConfidence,
                low: lowConfidence
            },
            techStackDetails
        };
    }

    /**
     * 计算技术栈多样性（熵）
     */
    private calculateDiversity(techStackCounts: Record<string, number>): number {
        const total = Object.values(techStackCounts).reduce((sum, count) => sum + count, 0);

        if (total === 0) {
            return 0;
        }

        let entropy = 0;

        for (const count of Object.values(techStackCounts)) {
            const probability = count / total;
            if (probability > 0) {
                entropy -= probability * Math.log2(probability);
            }
        }

        return Math.round(entropy * 100) / 100;
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
