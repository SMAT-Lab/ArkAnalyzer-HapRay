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
import Handlebars from 'handlebars';
import type { FormatResult } from './index';
import { BaseFormatter } from './index';
import type { Hap, TechStackDetection } from '../../core/hap/hap_parser';

/**
 * HTML格式化器
 */
export class HtmlFormatter extends BaseFormatter {
    /**
     * 格式化分析结果为HTML
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

            // 构建HTML报告数据
            const templateData = this.buildTemplateData(result);
            
            // 获取模板内容
            const template = this.getTemplate();
            
            // 编译模板
            const compiledTemplate = Handlebars.compile(template);
            const htmlContent = compiledTemplate(templateData);
            
            // 写入文件
            fs.writeFileSync(this.options.outputPath, htmlContent, 'utf8');
            
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
        return '.html';
    }

    /**
     * 获取HTML模板
     */
    private getTemplate(): string {
        // 如果指定了自定义模板路径，使用自定义模板
        if (this.options.templatePath && fs.existsSync(this.options.templatePath)) {
            return fs.readFileSync(this.options.templatePath, 'utf8');
        }
        
        // 使用默认模板
        return this.getDefaultTemplate();
    }

    /**
     * 构建模板数据
     */
    private buildTemplateData(result: Hap): Record<string, unknown> {
        // 过滤掉 Unknown 技术栈
        const filteredDetections = result.techStackDetections.filter(d => d.techStack !== 'Unknown');
        const detectedTechStacks = [...new Set(filteredDetections.map(d => d.techStack))];

        // 构建技术栈信息
        const technologyStackInfo = this.buildTechnologyStackInfoData(filteredDetections);

        // 获取唯一的技术栈列表（用于筛选按钮）
        const uniqueTechStacks = Array.from(new Set(
            technologyStackInfo.items.map(item => item.technologyStack as string)
        )).sort();

        // 计算总文件大小
        const totalFileSize = filteredDetections.reduce((sum, item) => sum + item.size, 0);

        // 构建技术栈分布
        const techStackDistribution = this.buildTechStackDistribution(filteredDetections);

        // 构建分析洞察
        const analysisInsights = this.buildAnalysisInsights(filteredDetections);

        return {
            metadata: {
                hapPath: result.hapPath,
                hapFileName: path.basename(result.hapPath),
                bundleName: result.bundleName,
                appName: result.appName,
                versionName: result.versionName,
                versionCode: result.versionCode,
                timestamp: new Date(),
                analysisDate: this.formatDateTime(new Date()),
                version: '2.0.0'
            },
            summary: {
                totalFiles: filteredDetections.length,
                detectedTechStacks: detectedTechStacks,
                technologyStackCount: technologyStackInfo.items.length,
                totalFileSize: this.formatFileSize(totalFileSize),
                techStackDistribution
            },
            technologyStackInfo: {
                items: technologyStackInfo.items,
                hasItems: technologyStackInfo.items.length > 0,
                uniqueStacks: uniqueTechStacks,
                metadataColumns: technologyStackInfo.metadataColumns
            },
            analysisInsights,
            options: {
                includeDetails: this.options.includeDetails !== false
            }
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
     * 构建技术栈分布
     */
    private buildTechStackDistribution(detections: Array<TechStackDetection>): Record<string, number> {
        const distribution: Record<string, number> = {};
        const totalFiles = detections.length;

        if (totalFiles === 0) {
            return distribution;
        }

        for (const item of detections) {
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
    private buildAnalysisInsights(detections: Array<TechStackDetection>): Record<string, unknown> {
        const techStackCounts: Record<string, number> = {};
        let highConfidence = 0;
        let mediumConfidence = 0;
        let lowConfidence = 0;

        // 统计信息
        for (const item of detections) {
            const techStack = item.techStack;
            techStackCounts[techStack] = (techStackCounts[techStack] || 0) + 1;

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
        const fileSizeDistribution = this.calculateFileSizeDistribution(detections);

        return {
            primaryTechStack,
            techStackDiversity,
            fileSizeDistribution,
            confidenceDistribution: {
                high: highConfidence,
                medium: mediumConfidence,
                low: lowConfidence
            }
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

    /**
     * 构建技术栈信息数据
     */
    private buildTechnologyStackInfoData(detections: Array<TechStackDetection>): {
        items: Array<Record<string, unknown>>;
        metadataColumns: Array<string>;
    } {
        const items: Array<Record<string, unknown>> = [];
        const metadataColumns = new Set<string>();

        // 首先收集所有可能的 metadata 字段
        for (const detection of detections) {
            Object.keys(detection.metadata).forEach(key => {
                metadataColumns.add(key);
            });
        }

        const sortedMetadataColumns = Array.from(metadataColumns).sort();

        // 构建数据项
        for (const detection of detections) {
            const item: Record<string, unknown> = {
                fileName: detection.file,
                filePath: `${detection.folder}/${detection.file}`,
                technologyStack: detection.techStack,
                fileSize: this.formatFileSize(detection.size),
                fileType: detection.fileType ?? '',
                confidence: detection.confidence !== undefined ? `${(detection.confidence * 100).toFixed(0)}%` : ''
            };

            // 添加 metadata 字段
            for (const column of sortedMetadataColumns) {
                const value = detection.metadata[column];
                if (value !== undefined && value !== null) {
                    if (Array.isArray(value)) {
                        item[column] = value.join(', ');
                    } else {
                        item[column] = String(value);
                    }
                } else {
                    item[column] = '';
                }
            }

            items.push(item);
        }

        return {
            items,
            metadataColumns: sortedMetadataColumns
        };
    }


    /**
     * 获取默认HTML模板
     */
    private getDefaultTemplate(): string {
        return `<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>HAP静态分析报告 - {{metadata.hapFileName}}</title>

    <!-- DataTables CSS -->
    <link rel="stylesheet" href="https://cdn.datatables.net/1.13.6/css/jquery.dataTables.min.css">

    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Microsoft YaHei', sans-serif; line-height: 1.6; color: #2c3e50; background: #f8f9fa; }
        .container { max-width: 1400px; margin: 0 auto; padding: 20px; }

        /* Header */
        .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 40px; border-radius: 12px; margin-bottom: 30px; box-shadow: 0 4px 20px rgba(102, 126, 234, 0.3); }
        .header h1 { font-size: 2.5em; margin-bottom: 10px; font-weight: 600; }
        .header .meta { opacity: 0.95; font-size: 1em; }

        /* Card */
        .card { background: white; border-radius: 12px; padding: 30px; margin-bottom: 30px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); border: 1px solid #e9ecef; }
        .card h2 { color: #2c3e50; margin-bottom: 20px; font-size: 1.6em; font-weight: 600; border-bottom: 2px solid #667eea; padding-bottom: 12px; }

        /* Summary */
        .summary-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin-bottom: 20px; }
        .summary-item { text-align: center; padding: 25px 20px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; border-radius: 10px; box-shadow: 0 4px 12px rgba(102, 126, 234, 0.2); transition: transform 0.2s; }
        .summary-item:hover { transform: translateY(-2px); box-shadow: 0 6px 16px rgba(102, 126, 234, 0.3); }
        .summary-item .number { font-size: 2.2em; font-weight: 700; display: block; margin-bottom: 5px; }
        .summary-item .label { font-size: 0.95em; opacity: 0.95; }

        /* Filter Buttons */
        .filter-container { margin: 20px 0; }
        .filter-label { font-size: 0.95em; font-weight: 600; color: #495057; margin-bottom: 10px; display: block; }
        .filter-buttons { display: flex; flex-wrap: wrap; gap: 8px; }
        .filter-btn {
            padding: 8px 16px;
            border: 2px solid #dee2e6;
            background: white;
            border-radius: 6px;
            cursor: pointer;
            font-size: 0.9em;
            font-weight: 500;
            color: #495057;
            transition: all 0.2s;
            user-select: none;
        }
        .filter-btn:hover {
            border-color: #667eea;
            color: #667eea;
            background: #f8f9ff;
        }
        .filter-btn.active {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border-color: #667eea;
            box-shadow: 0 2px 8px rgba(102, 126, 234, 0.3);
        }

        /* DataTables Override */
        .dataTables_wrapper { margin-top: 20px; }
        .dataTables_wrapper .dataTables_length select,
        .dataTables_wrapper .dataTables_filter input {
            border: 1px solid #dee2e6;
            border-radius: 6px;
            padding: 6px 12px;
            font-size: 0.9em;
        }
        .dataTables_wrapper .dataTables_filter input:focus {
            outline: none;
            border-color: #667eea;
            box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
        }
        .dataTables_wrapper .dataTables_paginate .paginate_button {
            border-radius: 6px;
            padding: 6px 12px;
            margin: 0 2px;
        }
        .dataTables_wrapper .dataTables_paginate .paginate_button.current {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white !important;
            border: none;
        }

        /* Table */
        table.dataTable {
            border-collapse: separate !important;
            border-spacing: 0;
            table-layout: fixed;
            width: 100% !important;
        }
        table.dataTable thead th {
            background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
            font-weight: 600;
            color: #2c3e50;
            border-bottom: 2px solid #667eea;
            padding: 14px 12px;
            font-size: 0.9em;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }
        table.dataTable tbody td {
            padding: 12px;
            border-bottom: 1px solid #f1f3f5;
            font-size: 0.9em;
            max-width: 0;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }
        table.dataTable tbody td code {
            display: inline-block;
            max-width: 100%;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
            vertical-align: bottom;
        }
        table.dataTable tbody tr { transition: background-color 0.2s; }
        table.dataTable tbody tr:hover { background-color: #f8f9ff; }
        table.dataTable tbody tr:hover td {
            white-space: normal;
            word-break: break-all;
        }

        /* Badge */
        .badge { display: inline-block; padding: 5px 10px; border-radius: 6px; font-size: 0.85em; font-weight: 500; }
        .badge-primary { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; }
        .badge-info { background: linear-gradient(135deg, #17a2b8 0%, #138496 100%); color: white; }
        .badge-success { background: linear-gradient(135deg, #28a745 0%, #218838 100%); color: white; }
        .badge-warning { background: linear-gradient(135deg, #ffc107 0%, #e0a800 100%); color: white; }
        .badge-danger { background: linear-gradient(135deg, #dc3545 0%, #c82333 100%); color: white; }
        .badge-secondary { background: linear-gradient(135deg, #6c757d 0%, #5a6268 100%); color: white; }
        .badge-light { background: #f8f9fa; color: #6c757d; border: 1px solid #dee2e6; }

        code {
            background: #f8f9fa;
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 0.85em;
            color: #e83e8c;
            font-family: 'Consolas', 'Monaco', monospace;
        }
        .tech-stacks { margin: 15px 0; }
        .tech-stack-tag { display: inline-block; margin: 3px; padding: 6px 12px; background: #3498db; color: white; border-radius: 20px; font-size: 0.9em; max-width: 220px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; vertical-align: top; }
        .flutter-analysis { font-size: 0.9em; }
        .flutter-analysis ul { margin: 5px 0; padding-left: 20px; }
        .flutter-analysis li { margin: 2px 0; }
        .flutter-analysis code { background: #f4f4f4; padding: 2px 4px; border-radius: 3px; font-size: 0.85em; }
        .badge-secondary { background: #6c757d; color: white; }
        .badge-light { background: #f8f9fa; color: #6c757d; border: 1px solid #dee2e6; }

        /* 递归压缩包样式 */
        .archive-tree { margin: 10px 0; }
        .archive-item { margin: 8px 0; padding: 12px; border: 1px solid #e0e0e0; border-radius: 6px; background: #fafafa; word-break: break-word; overflow-wrap: anywhere; }
        .archive-header { display: flex; align-items: center; margin-bottom: 8px; }
        .archive-icon { margin-right: 8px; font-size: 1.2em; }
        .archive-name { font-weight: bold; color: #2c3e50; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
        .archive-info { margin-left: auto; font-size: 0.9em; color: #7f8c8d; }
        .archive-stats { margin: 8px 0; font-size: 0.9em; color: #555; }
        .nested-files { margin-left: 20px; margin-top: 10px; }
        .nested-file { padding: 6px 10px; margin: 3px 0; background: white; border-left: 3px solid #3498db; border-radius: 3px; font-size: 0.9em; word-break: break-word; overflow-wrap: anywhere; }
        .nested-archive { margin-left: 20px; margin-top: 10px; border-left: 2px solid #e74c3c; padding-left: 15px; }
        .depth-indicator { display: inline-block; padding: 2px 6px; background: #e74c3c; color: white; border-radius: 10px; font-size: 0.8em; margin-left: 8px; }
        .extraction-status { display: inline-block; padding: 2px 6px; border-radius: 10px; font-size: 0.8em; margin-left: 8px; }
        .extracted { background: #27ae60; color: white; }
        .not-extracted { background: #e74c3c; color: white; }
        .file-type-tag { display: inline-block; padding: 2px 6px; background: #95a5a6; color: white; border-radius: 3px; font-size: 0.8em; margin-right: 4px; max-width: 220px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; vertical-align: top; }
        .collapsible { cursor: pointer; user-select: none; }
        .collapsible:hover { background: #f0f0f0; }
        .collapsible::before { content: '▼ '; color: #3498db; font-weight: bold; }
        .collapsible.collapsed::before { content: '▶ '; }
        .collapsible-content { display: block; }
        .collapsible-content.collapsed { display: none; }

        /* 搜索和过滤功能 */
        .search-container { margin: 20px 0; }
        .search-box { width: 100%; padding: 12px; border: 2px solid #ddd; border-radius: 6px; font-size: 1em; }
        .search-box:focus { border-color: #3498db; outline: none; }
        .filter-buttons { margin: 10px 0; }
        .filter-btn { padding: 8px 16px; margin: 4px; border: none; border-radius: 20px; cursor: pointer; font-size: 0.9em; transition: all 0.3s; }
        .filter-btn.active { background: #3498db; color: white; }
        .filter-btn:not(.active) { background: #ecf0f1; color: #2c3e50; }
        .filter-btn:hover { transform: translateY(-1px); box-shadow: 0 2px 5px rgba(0,0,0,0.2); }

        /* 统计图表样式 */
        .chart-container { margin: 20px 0; }
        .chart-item { margin: 8px 0; }
        .chart-bar {
            height: 30px;
            background: linear-gradient(90deg, #3498db, #2980b9);
            border-radius: 10px;
            position: relative;
            min-width: 120px;
            transition: all 0.3s ease;
        }
        .chart-bar:hover {
            background: linear-gradient(90deg, #2980b9, #1f4e79);
            transform: translateX(5px);
        }
        .chart-label {
            position: absolute;
            left: 10px;
            top: 50%;
            transform: translateY(-50%);
            color: white;
            font-weight: bold;
            font-size: 0.9em;
            text-shadow: 1px 1px 2px rgba(0,0,0,0.3);
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            right: 70px;
        }
        .chart-value {
            position: absolute;
            right: 10px;
            top: 50%;
            transform: translateY(-50%);
            color: white;
            font-size: 0.8em;
            text-shadow: 1px 1px 2px rgba(0,0,0,0.3);
            white-space: nowrap;
        }

        /* 响应式设计 */
        @media (max-width: 768px) {
            .container { padding: 10px; }
            .summary-grid { grid-template-columns: repeat(2, 1fr); }
            .table { font-size: 0.9em; table-layout: fixed; }
            .nested-files { margin-left: 10px; }
            .nested-archive { margin-left: 10px; }
            .tech-stack-tag, .file-type-tag { max-width: 160px; }
        }

        .no-data { text-align: center; color: #7f8c8d; font-style: italic; padding: 40px; }
        .footer { text-align: center; margin-top: 40px; padding: 20px; color: #7f8c8d; border-top: 1px solid #ddd; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>HAP静态分析报告</h1>
            <div class="meta">
                <div>文件: {{metadata.hapFileName}}</div>
                <div>分析时间: {{metadata.analysisDate}}</div>
                <div>版本: {{metadata.version}}</div>
            </div>
        </div>

        <div class="card">
            <h2>📊 分析摘要</h2>
            <div class="summary-grid">
                <div class="summary-item">
                    <span class="number">{{summary.totalFiles}}</span>
                    <span class="label">技术栈文件</span>
                </div>
                <div class="summary-item">
                    <span class="number">{{summary.totalFileSize}}</span>
                    <span class="label">总大小</span>
                </div>
                <div class="summary-item">
                    <span class="number">{{summary.detectedTechStacks.length}}</span>
                    <span class="label">检测到的技术栈</span>
                </div>
                <div class="summary-item">
                    <span class="number">{{analysisInsights.primaryTechStack}}</span>
                    <span class="label">主要技术栈</span>
                </div>
            </div>
            
            {{#if summary.detectedTechStacks.length}}
            <div class="tech-stacks">
                <strong>检测到的技术栈:</strong>
                {{#each summary.detectedTechStacks}}
                <span class="tech-stack-tag">{{this}}</span>
                {{/each}}
            </div>
            {{/if}}
        </div>

        {{#if options.includeDetails}}
        {{#if technologyStackInfo.hasItems}}
        <div class="card">
            <h2>🔧 技术栈信息</h2>
            <p style="color: #6c757d; margin-bottom: 15px; font-size: 0.95em;">文件名、路径、技术栈、文件大小、文件类型、置信度及元数据信息</p>

            <!-- 技术栈筛选按钮 -->
            <div class="filter-container">
                <span class="filter-label">按技术栈筛选：</span>
                <div class="filter-buttons">
                    <button class="filter-btn active" onclick="filterTechStack('all')">全部</button>
                    {{#each technologyStackInfo.uniqueStacks}}
                    <button class="filter-btn" onclick="filterTechStack('{{this}}')">{{this}}</button>
                    {{/each}}
                </div>
            </div>

            <table id="technologyStackTable" class="table display" style="width:100%">
                <thead>
                    <tr>
                        <th style="width: 18%">文件名</th>
                        <th style="width: 25%">路径</th>
                        <th style="width: 10%">技术栈</th>
                        <th style="width: 10%">文件大小</th>
                        <th style="width: 10%">文件类型</th>
                        <th style="width: 8%">置信度</th>
                        {{#each technologyStackInfo.metadataColumns}}
                        <th style="width: 10%" title="{{this}}">{{this}}</th>
                        {{/each}}
                    </tr>
                </thead>
                <tbody>
                    {{#each technologyStackInfo.items}}
                    <tr data-techstack="{{technologyStack}}">
                        <td title="{{fileName}}"><strong>{{fileName}}</strong></td>
                        <td title="{{filePath}}"><code>{{filePath}}</code></td>
                        <td><span class="badge badge-primary">{{technologyStack}}</span></td>
                        <td>{{fileSize}}</td>
                        <td>{{fileType}}</td>
                        <td>{{confidence}}</td>
                        {{#each ../technologyStackInfo.metadataColumns}}
                        <td title="{{lookup ../this this}}">{{lookup ../this this}}</td>
                    {{/each}}
                    </tr>
                    {{/each}}
                </tbody>
            </table>
        </div>
        {{/if}}
        {{/if}}

        <div class="footer">
            <p>报告由 HAP静态分析器 v{{metadata.version}} 生成</p>
            <p>生成时间: {{metadata.analysisDate}}</p>
        </div>
    </div>

    <!-- jQuery -->
    <script src="https://code.jquery.com/jquery-3.7.0.min.js"></script>
    <!-- DataTables JS -->
    <script src="https://cdn.datatables.net/1.13.6/js/jquery.dataTables.min.js"></script>

    <script>
        // 全局变量存储 DataTables 实例
        let techStackTable;

        // 初始化 DataTables
        $(document).ready(function() {
            // 技术栈信息表格
            if ($('#technologyStackTable').length) {
                techStackTable = $('#technologyStackTable').DataTable({
                    pageLength: 25,
                    lengthMenu: [[10, 25, 50, -1], [10, 25, 50, "全部"]],
                    language: {
                        "sProcessing": "处理中...",
                        "sLengthMenu": "显示 _MENU_ 条记录",
                        "sZeroRecords": "没有匹配的记录",
                        "sInfo": "显示第 _START_ 至 _END_ 条记录，共 _TOTAL_ 条",
                        "sInfoEmpty": "显示第 0 至 0 条记录，共 0 条",
                        "sInfoFiltered": "(由 _MAX_ 条记录过滤)",
                        "sSearch": "搜索:",
                        "oPaginate": {
                            "sFirst": "首页",
                            "sPrevious": "上一页",
                            "sNext": "下一页",
                            "sLast": "末页"
                        }
                    },
                    order: [[0, 'asc']]
                });
            }
        });

        // 技术栈筛选函数
        function filterTechStack(stack) {
            // 更新按钮状态
            const buttons = document.querySelectorAll('.card:has(#technologyStackTable) .filter-btn');
            buttons.forEach(btn => btn.classList.remove('active'));
            event.target.classList.add('active');

            // 应用筛选
            if (stack === 'all') {
                techStackTable.column(2).search('').draw();
            } else {
                techStackTable.column(2).search('^' + stack + '$', true, false).draw();
            }
        }

        function toggleCollapse(element) {
            const content = element.nextElementSibling;
            const isCollapsed = content.classList.contains('collapsed');

            if (isCollapsed) {
                content.classList.remove('collapsed');
                element.classList.remove('collapsed');
            } else {
                content.classList.add('collapsed');
                element.classList.add('collapsed');
            }
        }

        // 搜索功能
        function searchFiles(query) {
            const searchTerm = query.toLowerCase();
            const allFiles = document.querySelectorAll('.nested-file, .archive-item');

            allFiles.forEach(function(file) {
                const text = file.textContent.toLowerCase();
                const shouldShow = text.includes(searchTerm);
                file.style.display = shouldShow ? 'block' : 'none';

                // 如果是搜索结果，展开父级容器
                if (shouldShow && searchTerm) {
                    let parent = file.closest('.collapsible-content');
                    while (parent) {
                        parent.classList.remove('collapsed');
                        const header = parent.previousElementSibling;
                        if (header && header.classList.contains('collapsible')) {
                            header.classList.remove('collapsed');
                        }
                        parent = parent.parentElement.closest('.collapsible-content');
                    }
                }
            });
        }

        // 过滤功能
        function filterFiles(filterType) {
            // 更新按钮状态
            document.querySelectorAll('.filter-btn').forEach(btn => btn.classList.remove('active'));
            event.target.classList.add('active');

            const allFiles = document.querySelectorAll('.nested-file, .archive-item');

            allFiles.forEach(function(file) {
                let shouldShow = true;

                if (filterType === 'all') {
                    shouldShow = true;
                } else if (filterType === 'extracted') {
                    shouldShow = file.querySelector('.extracted') !== null;
                } else if (filterType === 'not-extracted') {
                    shouldShow = file.querySelector('.not-extracted') !== null;
                } else {
                    // 按文件类型过滤
                    const typeTag = file.querySelector('.file-type-tag');
                    shouldShow = typeTag && typeTag.textContent === filterType;
                }

                file.style.display = shouldShow ? 'block' : 'none';

                // 如果是过滤结果，展开父级容器
                if (shouldShow && filterType !== 'all') {
                    let parent = file.closest('.collapsible-content');
                    while (parent) {
                        parent.classList.remove('collapsed');
                        const header = parent.previousElementSibling;
                        if (header && header.classList.contains('collapsible')) {
                            header.classList.remove('collapsed');
                        }
                        parent = parent.parentElement.closest('.collapsible-content');
                    }
                }
            });
        }

        // 搜索所有文件
        function searchAllFiles(query) {
            const searchTerm = query.toLowerCase();
            const allRows = document.querySelectorAll('#all-files-table .file-row');

            allRows.forEach(function(row) {
                const text = row.textContent.toLowerCase();
                const shouldShow = text.includes(searchTerm);
                row.style.display = shouldShow ? 'table-row' : 'none';
            });
        }

        // 过滤所有文件
        function filterAllFiles(filterType) {
            // 更新按钮状态
            const allFilesCard = document.querySelector('.card:has(#all-files-table)');
            if (allFilesCard) {
                const buttons = allFilesCard.querySelectorAll('.filter-btn');
                buttons.forEach(btn => btn.classList.remove('active'));
                event.target.classList.add('active');
            }

            const allRows = document.querySelectorAll('#all-files-table .file-row');

            allRows.forEach(function(row) {
                let shouldShow = true;

                if (filterType === 'all') {
                    shouldShow = true;
                } else if (filterType === 'nested') {
                    shouldShow = row.dataset.source === 'nested';
                } else {
                    // 按技术栈过滤
                    // 多技术栈文件使用逗号分隔，支持包含判断
                    const ts = row.dataset.techStack || '';
                    const arr = ts.split(',').map(s => s.trim()).filter(Boolean);
                    shouldShow = arr.includes(filterType);
                }

                row.style.display = shouldShow ? 'table-row' : 'none';
            });
        }

        // 初始化：默认展开第一层，折叠深层嵌套
        document.addEventListener('DOMContentLoaded', function() {
            const nestedArchives = document.querySelectorAll('.nested-archive .collapsible');
            nestedArchives.forEach(function(element) {
                const content = element.nextElementSibling;
                content.classList.add('collapsed');
                element.classList.add('collapsed');
            });
        });
    </script>
</body>
</html>`;
    }
}
