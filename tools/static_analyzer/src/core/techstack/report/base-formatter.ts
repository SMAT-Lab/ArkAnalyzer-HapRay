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

import type { Hap } from '../../hap/hap_parser';
import type { FormatOptions, FormatResult } from './index';

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
    abstract format(result: Hap): Promise<FormatResult>;

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
    protected getFileTypeStats(result: Hap): Array<{type: string, count: number, percentage: string, barWidth: number}> {
        // 简化实现，只返回技术栈统计
        const stats: Array<{type: string, count: number, percentage: string, barWidth: number}> = [];
        const total = result.techStackDetections.length;
        
        if (total === 0) {return stats;}
        
        // 按技术栈分组统计
        const techStackCount = new Map<string, number>();
        for (const detection of result.techStackDetections) {
            const count = techStackCount.get(detection.techStack) ?? 0;
            techStackCount.set(detection.techStack, count + 1);
        }
        
        for (const [techStack, count] of techStackCount) {
            const percentage = ((count / total) * 100).toFixed(1);
            const barWidth = Math.max(5, (count / total) * 100);
            
            stats.push({
                type: techStack,
                count: count,
                percentage: `${percentage}%`,
                barWidth: barWidth
            });
        }
        
        return stats.sort((a, b) => b.count - a.count);
    }

    /**
     * 获取技术栈统计
     */
    protected getTechStackStats(result: Hap): Array<{techStack: string, count: number, percentage: string}> {
        const techStackCount = new Map<string, number>();

        result.techStackDetections.forEach(techStackDetection => {
            // 过滤掉 Unknown 技术栈
            if (techStackDetection.techStack !== 'Unknown') {
                techStackCount.set(techStackDetection.techStack, (techStackCount.get(techStackDetection.techStack) ?? 0) + 1);
            }
        });

        const stats: Array<{techStack: string, count: number, percentage: string}> = [];
        const total = result.techStackDetections.length;

        for (const [techStack, count] of techStackCount) {
            stats.push({
                techStack,
                count,
                percentage: this.calculatePercentage(count, total)
            });
        }

        return stats.sort((a, b) => b.count - a.count);
    }
}

